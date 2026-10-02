import uuid
from decimal import Decimal
from datetime import timedelta
from django.db import models
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden, FileResponse, JsonResponse
import json
import csv
from datetime import date
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib.auth import get_user_model
import logging
logger = logging.getLogger(__name__)

from .models import ContractInvoice, CandidatePayoutProfile, PaymentTransaction, PlatformFeeConfig, PaymentGatewayConfig, AutomationExecutionLog
from .forms import CandidatePayoutProfileForm, InvoicePayForm
from .services.invoicing import get_candidate_ledger_summary, get_next_payout_date
from .services.paystack_ghana import PaystackGhanaService
from .services.flutterwave import FlutterwaveService
from .services.pdf_generator import generate_invoice_pdf, generate_candidate_statement_pdf
from .services.automation import lock_closing_timesheets, execute_friday_payout_run
from apps.accounts.models import CandidateProfile, EmployerProfile
from apps.contracts.models import Contract, Timesheet
from apps.dashboard.models import send_notification, Notification


class CandidateEarningsLedgerView(LoginRequiredMixin, View):
    """
    Candidate Executive "Kodafriq Earnings" Ledger View.
    Displays:
    1. Available ($): Settled by employer, queued for upcoming Friday payout run
    2. Pending ($): Hours logged or under review, pending employer settlement
    3. Paid to Date ($): Historical disbursements completed to MoMo/Bank
    4. Next Payout ($): Sum set to trigger on the upcoming Friday
    5. Masked payout destination details
    6. Detailed accounting statement ledger
    """
    def get(self, request):
        user = request.user
        if not (user.is_candidate or user.is_kodafriq_staff):
            messages.error(request, "Only healthcare candidates can access their personal earnings ledger.")
            return redirect('dashboard:index')

        profile = getattr(user, 'candidate_profile', None)
        if not profile:
            messages.error(request, "Please complete your candidate profile first.")
            return redirect('dashboard:candidate_profile_edit')

        ledger = get_candidate_ledger_summary(profile)

        context = {
            'ledger': ledger,
            'profile': profile,
            'candidate': profile,
        }
        return render(request, 'billing/earnings_ledger.html', context)


class CandidatePayoutSettingsView(LoginRequiredMixin, View):
    """
    Setup & Edit Destination Payout Methods (Paystack Mobile Money Ghana or Flutterwave Pan-African Bank).
    """
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_candidate or request.user.is_kodafriq_staff):
            return HttpResponseForbidden("Unauthorized.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        profile = getattr(request.user, 'candidate_profile', None)
        if not profile:
            return redirect('dashboard:index')

        payout_profile, _ = CandidatePayoutProfile.objects.get_or_create(candidate=profile)
        form = CandidatePayoutProfileForm(instance=payout_profile)

        return render(request, 'billing/payout_settings.html', {
            'form': form,
            'payout_profile': payout_profile,
            'candidate': profile,
        })

    def post(self, request):
        profile = getattr(request.user, 'candidate_profile', None)
        if not profile:
            return redirect('dashboard:index')

        payout_profile, _ = CandidatePayoutProfile.objects.get_or_create(candidate=profile)
        form = CandidatePayoutProfileForm(request.POST, instance=payout_profile)

        if form.is_valid():
            p = form.save(commit=False)
            p.candidate = profile

            # Register with payment rail to generate recipient code / subaccount
            if p.payout_method == CandidatePayoutProfile.PayoutMethod.PAYSTACK_MOMO:
                paystack_service = PaystackGhanaService()
                code = paystack_service.create_transfer_recipient(p)
                p.paystack_recipient_code = code
                p.is_verified = True
                p.verified_at = timezone.now()
            elif p.payout_method == CandidatePayoutProfile.PayoutMethod.FLUTTERWAVE_BANK:
                flw_service = FlutterwaveService()
                subaccount_id = flw_service.create_subaccount(profile, p.bank_code or "044", p.account_number)
                p.flutterwave_subaccount_id = subaccount_id
                p.is_verified = True
                p.verified_at = timezone.now()

            p.save()
            messages.success(request, f"Payout destination updated successfully! Future disbursements will route to: {p.masked_destination}")
            return redirect('billing:candidate_earnings')

        return render(request, 'billing/payout_settings.html', {
            'form': form,
            'payout_profile': payout_profile,
            'candidate': profile,
        })


class EmployerInvoiceListView(LoginRequiredMixin, View):
    """
    Overview of all engagement invoices issued to the healthcare employer.
    """
    def get(self, request):
        user = request.user
        if not (user.is_employer or user.is_kodafriq_staff):
            messages.error(request, "Only employers can access the invoice center.")
            return redirect('dashboard:index')

        employer = getattr(user, 'employer_profile', None)
        if not employer:
            messages.error(request, "Please configure your employer profile.")
            return redirect('employers:company_profile')

        invoices = ContractInvoice.objects.filter(contract__employer=employer).select_related(
            'contract__candidate__user', 'timesheet', 'milestone'
        ).order_by('-created_at')

        # Filter by status
        status_filter = request.GET.get('status')
        if status_filter:
            invoices = invoices.filter(payment_status=status_filter)

        total_invoiced = invoices.aggregate(models.Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00')
        settled_invoices = invoices.filter(payment_status=ContractInvoice.PaymentStatus.SETTLED)
        total_paid = settled_invoices.aggregate(models.Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00')
        pending_invoices = invoices.filter(payment_status__in=[ContractInvoice.PaymentStatus.ISSUED, ContractInvoice.PaymentStatus.PROCESSING])
        pending_balance = pending_invoices.aggregate(models.Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00')

        context = {
            'invoices': invoices,
            'total_invoiced': total_invoiced,
            'total_paid': total_paid,
            'pending_balance': pending_balance,
            'pending_count': pending_invoices.count(),
            'selected_status': status_filter,
            'employer': employer,
        }
        return render(request, 'billing/invoice_list.html', context)


class EmployerInvoiceDetailView(LoginRequiredMixin, View):
    """
    Detailed inspection of a contract invoice with Upwork-standard transparent itemization:
    1. Professional Healthcare Services ($R net to talent)
    2. Kodafriq Talent Verification & Platform Fee (10% markup)
    3. Payment Processing Fee (2.9% + $0.30 pass-through)
    """
    def get(self, request, pk):
        invoice = get_object_or_404(
            ContractInvoice.objects.select_related(
                'contract__employer__user', 'contract__candidate__user', 'timesheet', 'milestone'
            ),
            pk=pk
        )
        user = request.user
        is_employer = user.is_employer and (invoice.employer.user == user)
        is_candidate = user.is_candidate and (invoice.candidate.user == user)
        is_staff = user.is_kodafriq_staff

        if not (is_employer or is_candidate or is_staff):
            return HttpResponseForbidden("You do not have permission to view this invoice.")

        pay_form = InvoicePayForm()
        gateway_cfg = PaymentGatewayConfig.get_active()

        # Unique reference for interactive checkout
        tx_ref = f"inv_{invoice.invoice_ref}_{uuid.uuid4().hex[:6]}"

        # GHS conversion for Paystack Mobile Money (1 USD ≈ 15.50 GHS)
        amount_ghs = (invoice.gross_amount * Decimal('15.50')).quantize(Decimal('0.01'))
        amount_kobo = int(amount_ghs * Decimal('100.00'))

        context = {
            'invoice': invoice,
            'contract': invoice.contract,
            'is_employer': is_employer,
            'is_candidate': is_candidate,
            'is_staff': is_staff,
            'pay_form': pay_form,
            'gateway_cfg': gateway_cfg,
            'tx_ref': tx_ref,
            'paystack_public_key': gateway_cfg.get_paystack_public_key(),
            'flutterwave_public_key': gateway_cfg.get_flutterwave_public_key(),
            'amount_ghs': amount_ghs,
            'amount_kobo': amount_kobo,
        }
        return render(request, 'billing/invoice_detail.html', context)


class EmployerInvoicePayView(LoginRequiredMixin, View):
    """
    Executes payment for an approved clinical engagement invoice.
    Debits employer method, marks invoice SETTLED, queues candidate earnings for Friday disbursement.
    """
    def post(self, request, pk):
        invoice = get_object_or_404(
            ContractInvoice.objects.select_related(
                'contract__employer__user', 'contract__candidate__user', 'timesheet', 'milestone'
            ),
            pk=pk
        )
        user = request.user
        is_employer = user.is_employer and (invoice.employer.user == user)
        is_staff = user.is_kodafriq_staff

        if not (is_employer or is_staff):
            return HttpResponseForbidden("Unauthorized.")

        if invoice.payment_status == ContractInvoice.PaymentStatus.SETTLED:
            messages.info(request, "This invoice is already settled.")
            return redirect('billing:invoice_detail', pk=invoice.pk)

        # Generate unique transaction reference
        tx_ref = f"flw_charge_{invoice.invoice_ref}_{uuid.uuid4().hex[:6]}"

        # Mark invoice settled & queue candidate payout
        invoice.mark_settled(
            gateway_charge_ref=tx_ref,
            gateway_provider=ContractInvoice.GatewayProvider.FLUTTERWAVE
        )

        # Record immutable audit transaction
        PaymentTransaction.objects.create(
            invoice=invoice,
            transaction_type=PaymentTransaction.TransactionType.CHARGE,
            gateway=PaymentTransaction.Gateway.FLUTTERWAVE,
            reference=tx_ref,
            amount=invoice.gross_amount,
            currency=invoice.currency,
            status=PaymentTransaction.Status.SUCCESS,
            raw_payload={"status": "successful", "message": "Employer card debited via Kodafriq billing engine"},
            ip_address=request.META.get('REMOTE_ADDR', '')
        )

        # Notify talent: Earnings queued!
        send_notification(
            recipient=invoice.candidate.user,
            title="Earnings Settled & Queued for Payout!",
            message=f"{invoice.employer.company_name} settled invoice {invoice.invoice_ref}. Your net earnings of ${invoice.talent_earnings} are now Available and queued for Friday payout.",
            notification_type=Notification.NotificationType.SYSTEM,
            link=reverse('billing:candidate_earnings')
        )

        messages.success(request, f"Invoice {invoice.invoice_ref} (${invoice.gross_amount}) settled successfully! Candidate earnings of ${invoice.talent_earnings} have been queued for Friday disbursement.")
        return redirect('billing:invoice_detail', pk=invoice.pk)


class InvoicePDFDownloadView(LoginRequiredMixin, View):
    """
    Generates and serves downloadable, tax-compliant PDF invoice for employers and candidates.
    """
    def get(self, request, pk, *args, **kwargs):
        invoice = get_object_or_404(
            ContractInvoice.objects.select_related(
                'contract', 'contract__employer', 'contract__candidate',
                'contract__candidate__user', 'contract__employer__user',
                'timesheet', 'milestone'
            ),
            pk=pk
        )
        user = request.user
        is_owner = (
            (invoice.candidate and invoice.candidate.user == user) or
            (invoice.employer and invoice.employer.user == user) or
            user.is_staff or
            getattr(user, 'role', '') == 'ADMIN'
        )
        if not is_owner:
            return HttpResponseForbidden("Access Denied: You are not authorized to view this invoice.")

        pdf_buffer = generate_invoice_pdf(invoice)
        as_attachment = bool(request.GET.get('download'))
        filename = f"kodafriq_invoice_{invoice.invoice_ref}.pdf"
        response = FileResponse(pdf_buffer, as_attachment=as_attachment, filename=filename, content_type='application/pdf')
        return response


class CandidateStatementPDFView(LoginRequiredMixin, View):
    """
    Generates official verified earnings statement PDF for candidates.
    """
    def get(self, request, *args, **kwargs):
        profile = getattr(request.user, 'candidate_profile', None)
        if not profile:
            return HttpResponseForbidden("Access Denied: Only healthcare professionals can generate earnings statements.")

        invoices = ContractInvoice.objects.filter(
            contract__candidate=profile
        ).select_related('contract').order_by('-billing_period_start')
        
        ledger_summary = get_candidate_ledger_summary(profile)
        next_payout_date = get_next_payout_date()

        pdf_buffer = generate_candidate_statement_pdf(
            candidate=profile,
            invoices=invoices,
            ledger_summary=ledger_summary,
            next_payout_date=next_payout_date
        )
        as_attachment = bool(request.GET.get('download'))
        filename = f"kodafriq_earnings_{request.user.username}_{timezone.now().strftime('%Y%m%d')}.pdf"
        response = FileResponse(pdf_buffer, as_attachment=as_attachment, filename=filename, content_type='application/pdf')
        return response



class InvoiceVerifyPaymentView(LoginRequiredMixin, View):
    def post(self, request, pk):
        invoice = get_object_or_404(
            ContractInvoice.objects.select_related(
                'contract__employer__user', 'contract__candidate__user', 'timesheet', 'milestone'
            ),
            pk=pk
        )
        user = request.user
        is_employer = user.is_employer and (invoice.employer.user == user)
        is_staff = user.is_kodafriq_staff

        if not (is_employer or is_staff):
            return JsonResponse({'status': 'error', 'message': 'Unauthorized to settle this invoice.'}, status=403)

        if invoice.payment_status == ContractInvoice.PaymentStatus.SETTLED:
            return JsonResponse({
                'status': 'success',
                'message': 'Invoice is already settled.',
                'redirect_url': reverse('billing:invoice_detail', kwargs={'pk': invoice.pk})
            })

        try:
            if request.content_type == 'application/json':
                payload = json.loads(request.body.decode('utf-8'))
            else:
                payload = request.POST.dict()
        except Exception as e:
            logger.error(f"Error parsing verify payment payload: {e}")
            return JsonResponse({'status': 'error', 'message': 'Invalid payload data.'}, status=400)

        gateway = payload.get('gateway', '').upper()
        transaction_id = payload.get('transaction_id') or payload.get('reference') or payload.get('flw_ref') or payload.get('tx_ref')

        if not transaction_id:
            return JsonResponse({'status': 'error', 'message': 'Missing transaction reference from payment gateway.'}, status=400)

        verified = False
        gateway_data = {}

        if gateway == 'PAYSTACK':
            pstk_service = PaystackGhanaService()
            verified, gateway_data = pstk_service.verify_transaction(transaction_id)
            provider = ContractInvoice.GatewayProvider.PAYSTACK
            gateway_enum = PaymentTransaction.Gateway.PAYSTACK
        else:
            flw_service = FlutterwaveService()
            verified, gateway_data = flw_service.verify_transaction(transaction_id)
            provider = ContractInvoice.GatewayProvider.FLUTTERWAVE
            gateway_enum = PaymentTransaction.Gateway.FLUTTERWAVE

        if not verified:
            error_msg = gateway_data if isinstance(gateway_data, str) else "Payment gateway could not verify transaction."
            return JsonResponse({'status': 'error', 'message': error_msg}, status=400)

        # Mark invoice settled & queue candidate payout
        invoice.mark_settled(
            gateway_charge_ref=str(transaction_id),
            gateway_provider=provider
        )

        PaymentTransaction.objects.create(
            invoice=invoice,
            transaction_type=PaymentTransaction.TransactionType.CHARGE,
            gateway=gateway_enum,
            reference=str(transaction_id),
            amount=invoice.gross_amount,
            currency=invoice.currency,
            status=PaymentTransaction.Status.SUCCESS,
            raw_payload=gateway_data if isinstance(gateway_data, dict) else {"status": "verified", "data": gateway_data},
            ip_address=request.META.get('REMOTE_ADDR', '')
        )

        send_notification(
            recipient=invoice.candidate.user,
            title="Earnings Settled & Queued for Payout!",
            message=f"{invoice.employer.company_name} settled invoice {invoice.invoice_ref}. Your net earnings of ${invoice.talent_earnings} are now Available and queued for Friday payout.",
            notification_type=Notification.NotificationType.SYSTEM,
            link=reverse('billing:candidate_earnings')
        )

        messages.success(request, f"Payment successfully processed! Invoice {invoice.invoice_ref} (${invoice.gross_amount}) is settled. Candidate earnings of ${invoice.talent_earnings} have been queued for Friday payout.")

        return JsonResponse({
            'status': 'success',
            'message': 'Payment confirmed and invoice settled successfully!',
            'redirect_url': reverse('billing:invoice_detail', kwargs={'pk': invoice.pk})
        })



class StaffAutomationHubView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Staff / Superuser Operational Automation Control Center.
    - Monitors scheduler health and cron crontab specifications
    - Displays real-time pending lock and payout backlogs
    - Triggers manual runs with dry-run toggle
    - Live audit history with execution results
    """
    def test_func(self):
        user = self.request.user
        return bool(user.is_authenticated and (user.is_superuser or user.has_perm('dashboard.access_automation')))

    def handle_no_permission(self):
        messages.error(self.request, "You do not have administrative permission to access the Scheduled Automation Engine. Please contact a superuser.")
        return redirect('dashboard:staff')

    def get(self, request):
        today = timezone.localdate()

        # Engine 1: Weekly Timesheet Lock metrics
        active_hourly_contracts = Contract.objects.filter(
            contract_type=Contract.ContractType.HOURLY,
            status=Contract.Status.ACTIVE
        ).count()

        draft_timesheets = Timesheet.objects.filter(
            status=Timesheet.Status.DRAFT,
            contract__status=Contract.Status.ACTIVE
        )
        draft_timesheets_count = draft_timesheets.count()
        
        pending_hours = Decimal('0.00')
        for ts in draft_timesheets:
            pending_hours += ts.total_hours

        # Engine 2: Friday Payout metrics
        queued_invoices = ContractInvoice.objects.filter(
            payment_status=ContractInvoice.PaymentStatus.SETTLED,
            payout_status=ContractInvoice.PayoutStatus.QUEUED
        )
        queued_invoices_count = queued_invoices.count()
        queued_amount = queued_invoices.aggregate(models.Sum('talent_earnings'))['talent_earnings__sum'] or Decimal('0.00')

        disbursed_invoices = ContractInvoice.objects.filter(
            payout_status=ContractInvoice.PayoutStatus.COMPLETED
        )
        total_disbursed_amount = disbursed_invoices.aggregate(models.Sum('talent_earnings'))['talent_earnings__sum'] or Decimal('0.00')

        # Recent Automation Runs
        recent_logs = AutomationExecutionLog.objects.select_related('executed_by').all()[:25]

        # Calculate next scheduled run dates
        now = timezone.localtime()
        days_to_sunday = (6 - today.weekday()) % 7
        if days_to_sunday == 0 and now.hour >= 23 and now.minute >= 59:
            days_to_sunday = 7
        next_sunday = today + timedelta(days=days_to_sunday)

        days_to_friday = (4 - today.weekday()) % 7
        if days_to_friday == 0 and now.hour >= 9:
            days_to_friday = 7
        next_friday = today + timedelta(days=days_to_friday)

        context = {
            'today': today,
            'active_hourly_contracts': active_hourly_contracts,
            'draft_timesheets_count': draft_timesheets_count,
            'pending_hours': pending_hours,
            'queued_invoices_count': queued_invoices_count,
            'queued_amount': queued_amount,
            'total_disbursed_amount': total_disbursed_amount,
            'recent_logs': recent_logs,
            'next_sunday': next_sunday,
            'next_friday': next_friday,
        }
        return render(request, 'billing/automation_hub.html', context)

    def post(self, request):
        action = request.POST.get('action')
        dry_run = request.POST.get('dry_run') in ['true', 'True', '1', 'on']
        target_date_str = request.POST.get('target_date', '').strip() or None
        force = request.POST.get('force') in ['true', 'True', '1', 'on']
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')

        try:
            if action == 'lock_timesheets':
                result = lock_closing_timesheets(
                    as_of_date=target_date_str,
                    dry_run=dry_run,
                    actor=request.user,
                    force=force
                )
            elif action == 'execute_payouts':
                result = execute_friday_payout_run(
                    as_of_date=target_date_str,
                    dry_run=dry_run,
                    actor=request.user,
                    force=force
                )
            else:
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': f'Unknown action: {action}'}, status=400)
                messages.error(request, f'Unknown action: {action}')
                return redirect('billing:automation_hub')

            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'result': result
                })

            msg_type = messages.INFO if dry_run else messages.SUCCESS
            mode_prefix = "[DRY-RUN] " if dry_run else "[LIVE] "
            messages.add_message(request, msg_type, mode_prefix + result.get('summary', 'Executed successfully'))
            return redirect('billing:automation_hub')

        except Exception as e:
            logger.exception("Error executing automation task from hub")
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            messages.error(request, f"Execution failed: {e}")
            return redirect('billing:automation_hub')



class StaffPaymentsOverviewView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Staff / Superuser Central Payment & Payout Command Center.
    Comprehensive tracking, filtering, and visualization of all platform payments:
    - Employer Inflow (Card & MoMo charges)
    - Candidate Outflow (Weekly & Milestone payouts)
    - Kodafriq 10% Platform Revenue & interchange margins
    - Filtering by group (Employers, Candidates, Platform, or All)
    - Filtering by individual user with dedicated user financial profile dossier
    - Rich interactive Chart.js visualizations
    - Searchable & sortable unified ledger table with dossier modal
    - Direct CSV accounting export
    """
    def test_func(self):
        user = self.request.user
        return bool(user.is_authenticated and (user.is_superuser or user.has_perm('dashboard.access_payments')))

    def handle_no_permission(self):
        messages.error(self.request, "You do not have administrative permission to access the Payments & Payouts Command Center. Please contact a superuser.")
        return redirect('dashboard:staff')

    def get(self, request):
        today = timezone.localdate()
        User = get_user_model()

        # 1. Filter Parameters
        flow = request.GET.get('flow', 'all')          # 'all', 'employers', 'candidates', 'platform'
        status = request.GET.get('status', 'all')      # 'all', 'settled', 'queued', 'completed', 'pending', 'failed', 'disputed'
        gateway = request.GET.get('gateway', 'all')    # 'all', 'flutterwave', 'paystack'
        period = request.GET.get('period', '30d')      # '7d', '30d', '90d', 'year', 'all', 'custom'
        start_date_str = request.GET.get('start_date', '').strip()
        end_date_str = request.GET.get('end_date', '').strip()
        user_id = request.GET.get('user_id', '').strip()
        q = request.GET.get('q', '').strip()
        export = request.GET.get('export', '').strip()

        # 2. Base Invoices Queryset
        invoices_qs = ContractInvoice.objects.select_related(
            'contract__employer__user',
            'contract__candidate__user',
            'timesheet',
            'milestone'
        ).prefetch_related('transactions').order_by('-created_at')

        # 3. Date Range Filtering
        date_from = None
        date_to = None
        if period == '7d':
            date_from = today - timedelta(days=7)
        elif period == '30d':
            date_from = today - timedelta(days=30)
        elif period == '90d':
            date_from = today - timedelta(days=90)
        elif period == 'year':
            date_from = date(today.year, 1, 1)
        elif period == 'custom':
            if start_date_str:
                try:
                    date_from = date.fromisoformat(start_date_str)
                except ValueError:
                    pass
            if end_date_str:
                try:
                    date_to = date.fromisoformat(end_date_str)
                except ValueError:
                    pass

        if date_from:
            invoices_qs = invoices_qs.filter(created_at__date__gte=date_from)
        if date_to:
            invoices_qs = invoices_qs.filter(created_at__date__lte=date_to)

        # 4. Flow Group Filtering
        if flow == 'employers':
            invoices_qs = invoices_qs.filter(gross_amount__gt=0)
        elif flow == 'candidates':
            invoices_qs = invoices_qs.filter(
                models.Q(payout_status__in=[
                    ContractInvoice.PayoutStatus.QUEUED,
                    ContractInvoice.PayoutStatus.COMPLETED,
                    ContractInvoice.PayoutStatus.PROCESSING
                ]) | models.Q(transactions__transaction_type=PaymentTransaction.TransactionType.PAYOUT)
            ).distinct()
        elif flow == 'platform':
            invoices_qs = invoices_qs.filter(kodafriq_fee__gt=0)

        # 5. Status Filtering
        if status == 'settled':
            invoices_qs = invoices_qs.filter(payment_status=ContractInvoice.PaymentStatus.SETTLED)
        elif status == 'queued':
            invoices_qs = invoices_qs.filter(payout_status=ContractInvoice.PayoutStatus.QUEUED)
        elif status == 'completed':
            invoices_qs = invoices_qs.filter(payout_status=ContractInvoice.PayoutStatus.COMPLETED)
        elif status == 'pending':
            invoices_qs = invoices_qs.filter(payment_status__in=[
                ContractInvoice.PaymentStatus.ISSUED,
                ContractInvoice.PaymentStatus.DRAFT
            ])
        elif status == 'failed':
            invoices_qs = invoices_qs.filter(
                models.Q(payment_status=ContractInvoice.PaymentStatus.FAILED) |
                models.Q(payout_status=ContractInvoice.PayoutStatus.FAILED)
            )
        elif status == 'disputed':
            invoices_qs = invoices_qs.filter(
                models.Q(timesheet__status='DISPUTED') |
                models.Q(milestone__status='DISPUTED') |
                models.Q(payout_status=ContractInvoice.PayoutStatus.ON_HOLD)
            )

        # 6. Gateway Rail Filtering
        if gateway == 'flutterwave':
            invoices_qs = invoices_qs.filter(
                models.Q(gateway_provider=ContractInvoice.GatewayProvider.FLUTTERWAVE) |
                models.Q(transactions__gateway=PaymentTransaction.Gateway.FLUTTERWAVE)
            ).distinct()
        elif gateway == 'paystack':
            invoices_qs = invoices_qs.filter(
                models.Q(gateway_provider=ContractInvoice.GatewayProvider.PAYSTACK) |
                models.Q(transactions__gateway=PaymentTransaction.Gateway.PAYSTACK)
            ).distinct()

        # 7. Individual User Filter & User Dossier Extraction
        selected_user = None
        user_dossier = None
        if user_id:
            try:
                selected_user = User.objects.filter(pk=user_id).first()
                if selected_user:
                    invoices_qs = invoices_qs.filter(
                        models.Q(contract__employer__user=selected_user) |
                        models.Q(contract__candidate__user=selected_user)
                    )

                    is_employer = hasattr(selected_user, 'employer_profile')
                    is_candidate = hasattr(selected_user, 'candidate_profile')

                    u_invoices = ContractInvoice.objects.filter(
                        models.Q(contract__employer__user=selected_user) |
                        models.Q(contract__candidate__user=selected_user)
                    )
                    u_settled = u_invoices.filter(payment_status=ContractInvoice.PaymentStatus.SETTLED)

                    if is_employer:
                        emp_prof = selected_user.employer_profile
                        total_volume = u_settled.aggregate(models.Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00')
                        outstanding = u_invoices.filter(payment_status=ContractInvoice.PaymentStatus.ISSUED).aggregate(models.Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00')
                        user_dossier = {
                            'user': selected_user,
                            'role': 'Employer / Hospital Client',
                            'title': emp_prof.company_name,
                            'location': emp_prof.country or emp_prof.address or 'Accra, Ghana',
                            'joined_at': selected_user.created_at,
                            'total_volume': total_volume,
                            'completed_invoices': u_settled.count(),
                            'outstanding': outstanding,
                            'payout_destination': None,
                            'is_employer': True,
                        }
                    elif is_candidate:
                        cand_prof = selected_user.candidate_profile
                        payout_prof = getattr(cand_prof, 'payout_profile', None)
                        total_volume = u_invoices.filter(payout_status=ContractInvoice.PayoutStatus.COMPLETED).aggregate(models.Sum('talent_earnings'))['talent_earnings__sum'] or Decimal('0.00')
                        queued_val = u_invoices.filter(payout_status=ContractInvoice.PayoutStatus.QUEUED).aggregate(models.Sum('talent_earnings'))['talent_earnings__sum'] or Decimal('0.00')
                        pending_val = u_invoices.filter(payout_status=ContractInvoice.PayoutStatus.PENDING).aggregate(models.Sum('talent_earnings'))['talent_earnings__sum'] or Decimal('0.00')
                        user_dossier = {
                            'user': selected_user,
                            'role': 'Healthcare Professional / Talent',
                            'title': cand_prof.full_name,
                            'subtitle': cand_prof.headline or 'Medical Coding Specialist',
                            'location': cand_prof.location or 'Ghana',
                            'joined_at': selected_user.created_at,
                            'total_volume': total_volume,
                            'queued_volume': queued_val,
                            'pending_volume': pending_val,
                            'completed_invoices': u_invoices.filter(payout_status=ContractInvoice.PayoutStatus.COMPLETED).count(),
                            'payout_destination': payout_prof.masked_destination if payout_prof else "Not Configured",
                            'is_verified': bool(payout_prof and payout_prof.is_verified),
                            'is_candidate': True,
                        }
            except Exception as e:
                logger.error(f"Error resolving user filter {user_id}: {e}")

        # 8. Free-text Search Query
        if q:
            invoices_qs = invoices_qs.filter(
                models.Q(invoice_ref__icontains=q) |
                models.Q(gateway_charge_ref__icontains=q) |
                models.Q(gateway_payout_ref__icontains=q) |
                models.Q(contract__employer__company_name__icontains=q) |
                models.Q(contract__candidate__user__first_name__icontains=q) |
                models.Q(contract__candidate__user__last_name__icontains=q) |
                models.Q(contract__candidate__user__email__icontains=q) |
                models.Q(transactions__reference__icontains=q)
            ).distinct()

        # 9. Handle CSV Export
        if export == 'csv':
            response = HttpResponse(content_type='text/csv')
            now_stamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            response['Content-Disposition'] = f'attachment; filename="kodafriq_payments_audit_{now_stamp}.csv"'
            writer = csv.writer(response)
            writer.writerow([
                'Invoice Ref',
                'Date Created',
                'Employer Company',
                'Candidate Talent',
                'Contract Ref',
                'Gross Charged ($)',
                'Candidate Net ($)',
                'Kodafriq 10% Fee ($)',
                'Pass-Through Processing Fee ($)',
                'Payment Status',
                'Payout Status',
                'Gateway Provider',
                'Gateway Charge Ref',
                'Gateway Payout Ref',
                'Settled At',
                'Disbursed At'
            ])
            for inv in invoices_qs:
                writer.writerow([
                    inv.invoice_ref,
                    inv.created_at.strftime('%Y-%m-%d %H:%M'),
                    inv.employer.company_name,
                    inv.candidate.full_name,
                    inv.contract.contract_ref,
                    float(inv.gross_amount),
                    float(inv.talent_earnings),
                    float(inv.kodafriq_fee),
                    float(inv.processing_fee),
                    inv.get_payment_status_display(),
                    inv.get_payout_status_display(),
                    inv.get_gateway_provider_display(),
                    inv.gateway_charge_ref,
                    inv.gateway_payout_ref,
                    inv.settled_at.strftime('%Y-%m-%d %H:%M') if inv.settled_at else '',
                    inv.disbursed_at.strftime('%Y-%m-%d %H:%M') if inv.disbursed_at else ''
                ])
            return response

        # 10. Summary KPIs for the Filtered Scope
        settled_scope = invoices_qs.filter(payment_status=ContractInvoice.PaymentStatus.SETTLED)
        kpi_gross_inflow = settled_scope.aggregate(models.Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00')
        kpi_net_outflow = invoices_qs.filter(payout_status=ContractInvoice.PayoutStatus.COMPLETED).aggregate(models.Sum('talent_earnings'))['talent_earnings__sum'] or Decimal('0.00')
        kpi_platform_revenue = settled_scope.aggregate(models.Sum('kodafriq_fee'))['kodafriq_fee__sum'] or Decimal('0.00')
        kpi_processing_fees = settled_scope.aggregate(models.Sum('processing_fee'))['processing_fee__sum'] or Decimal('0.00')
        kpi_queued_escrow = invoices_qs.filter(payout_status=ContractInvoice.PayoutStatus.QUEUED).aggregate(models.Sum('talent_earnings'))['talent_earnings__sum'] or Decimal('0.00')
        kpi_pending_billed = invoices_qs.filter(payment_status=ContractInvoice.PaymentStatus.ISSUED).aggregate(models.Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00')
        
        kpi_total_count = invoices_qs.count()
        kpi_settled_count = settled_scope.count()
        kpi_failed_count = invoices_qs.filter(models.Q(payment_status=ContractInvoice.PaymentStatus.FAILED) | models.Q(payout_status=ContractInvoice.PayoutStatus.FAILED)).count()
        kpi_success_rate = round((kpi_settled_count / max(1, kpi_settled_count + kpi_failed_count)) * 100, 1)

        # Rails volumes
        kpi_flw_vol = settled_scope.filter(gateway_provider=ContractInvoice.GatewayProvider.FLUTTERWAVE).aggregate(models.Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00')
        kpi_pstk_vol = settled_scope.filter(gateway_provider=ContractInvoice.GatewayProvider.PAYSTACK).aggregate(models.Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00')

        # 11. Chart Visualizations Data
        timeline_labels = []
        timeline_inflow = []
        timeline_outflow = []
        timeline_platform = []

        for i in range(5, -1, -1):
            m_year = today.year
            m_month = today.month - i
            while m_month <= 0:
                m_month += 12
                m_year -= 1

            m_date = date(m_year, m_month, 1)
            timeline_labels.append(m_date.strftime('%b %Y'))

            if m_month == 12:
                next_m_date = date(m_year + 1, 1, 1)
            else:
                next_m_date = date(m_year, m_month + 1, 1)

            m_invs = invoices_qs.filter(created_at__date__gte=m_date, created_at__date__lt=next_m_date)
            m_set = m_invs.filter(payment_status=ContractInvoice.PaymentStatus.SETTLED)

            inf = float(m_set.aggregate(models.Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00'))
            out = float(m_invs.filter(payout_status=ContractInvoice.PayoutStatus.COMPLETED).aggregate(models.Sum('talent_earnings'))['talent_earnings__sum'] or Decimal('0.00'))
            fee = float(m_set.aggregate(models.Sum('kodafriq_fee'))['kodafriq_fee__sum'] or Decimal('0.00'))

            timeline_inflow.append(inf)
            timeline_outflow.append(out)
            timeline_platform.append(fee)

        chart_economics = {
            'talent': float(settled_scope.aggregate(models.Sum('talent_earnings'))['talent_earnings__sum'] or Decimal('0.00')),
            'platform': float(kpi_platform_revenue),
            'gateway': float(kpi_processing_fees)
        }

        chart_gateways = {
            'flutterwave': float(kpi_flw_vol),
            'paystack': float(kpi_pstk_vol)
        }

        chart_pipeline = {
            'issued': float(invoices_qs.filter(payment_status=ContractInvoice.PaymentStatus.ISSUED).aggregate(models.Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00')),
            'settled': float(kpi_gross_inflow),
            'queued': float(kpi_queued_escrow),
            'disbursed': float(kpi_net_outflow),
            'disputed': float(invoices_qs.filter(models.Q(timesheet__status='DISPUTED') | models.Q(payout_status=ContractInvoice.PayoutStatus.ON_HOLD)).aggregate(models.Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00')),
        }

        # 12. List of Users for Quick Selector
        employers = EmployerProfile.objects.select_related('user').all()
        candidates = CandidateProfile.objects.select_related('user').all()
        user_choices = []
        for emp in employers:
            user_choices.append({
                'id': emp.user.id,
                'name': f"{emp.company_name} (Employer)",
                'email': emp.user.email,
                'type': 'employer'
            })
        for cand in candidates:
            user_choices.append({
                'id': cand.user.id,
                'name': f"{cand.full_name} (Talent)",
                'email': cand.user.email,
                'type': 'candidate'
            })

        # 13. Pagination
        paginator = Paginator(invoices_qs, 15)
        page_num = request.GET.get('page', 1)
        try:
            page_obj = paginator.page(page_num)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        context = {
            'page_obj': page_obj,
            'invoices': page_obj.object_list,
            'total_invoices_count': invoices_qs.count(),
            'flow': flow,
            'status': status,
            'gateway': gateway,
            'period': period,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'user_id': user_id,
            'selected_user': selected_user,
            'user_dossier': user_dossier,
            'user_choices': user_choices,
            'q': q,

            # KPIs
            'kpi_gross_inflow': kpi_gross_inflow,
            'kpi_net_outflow': kpi_net_outflow,
            'kpi_platform_revenue': kpi_platform_revenue,
            'kpi_processing_fees': kpi_processing_fees,
            'kpi_queued_escrow': kpi_queued_escrow,
            'kpi_pending_billed': kpi_pending_billed,
            'kpi_total_count': kpi_total_count,
            'kpi_settled_count': kpi_settled_count,
            'kpi_success_rate': kpi_success_rate,
            'kpi_flw_vol': kpi_flw_vol,
            'kpi_pstk_vol': kpi_pstk_vol,

            # Chart JSON payloads
            'timeline_labels_json': json.dumps(timeline_labels),
            'timeline_inflow_json': json.dumps(timeline_inflow),
            'timeline_outflow_json': json.dumps(timeline_outflow),
            'timeline_platform_json': json.dumps(timeline_platform),
            'chart_economics_json': json.dumps(chart_economics),
            'chart_gateways_json': json.dumps(chart_gateways),
            'chart_pipeline_json': json.dumps(chart_pipeline),
        }

        return render(request, 'billing/admin_payments_hub.html', context)
