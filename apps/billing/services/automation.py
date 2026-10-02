import uuid
import logging
from decimal import Decimal
from datetime import timedelta, date
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.db import transaction

from apps.contracts.models import Contract, Timesheet, TimesheetEntry
from apps.billing.models import (
    ContractInvoice,
    PaymentTransaction,
    CandidatePayoutProfile,
    AutomationExecutionLog
)
from apps.billing.services.invoicing import generate_invoice_for_timesheet
from apps.billing.services.paystack_ghana import PaystackGhanaService
from apps.billing.services.flutterwave import FlutterwaveService
from apps.dashboard.models import send_notification, Notification

logger = logging.getLogger(__name__)


def lock_closing_timesheets(as_of_date=None, dry_run=False, actor=None, force=False):
    """
    Weekly Timesheet Lock Engine (Sunday 23:59 Cron / Staff Automation Hub).
    Evaluates all active hourly contracts:
    1. Identifies draft timesheets closing on or before `as_of_date`.
    2. Locks non-zero timesheets into SUBMITTED status.
    3. Generates/updates the corresponding ContractInvoice (transitions to ISSUED).
    4. Dispatches real-time in-app notifications to candidate and employer.
    5. Pre-populates next week's empty timesheet with 7 daily entries (Mon-Sun).
    6. Logs the execution run in AutomationExecutionLog.
    """
    if as_of_date is None:
        target_date = timezone.localdate()
    elif isinstance(as_of_date, str):
        target_date = date.fromisoformat(as_of_date)
    else:
        target_date = as_of_date

    active_contracts = Contract.objects.filter(
        contract_type=Contract.ContractType.HOURLY,
        status=Contract.Status.ACTIVE
    ).select_related('employer__user', 'candidate__user')

    timesheets_locked = 0
    invoices_generated = 0
    total_hours_locked = Decimal('0.00')
    total_amount_invoiced = Decimal('0.00')
    next_week_initialized = 0
    details = []

    # Calculate next Monday relative to target_date
    days_to_next_mon = (7 - target_date.weekday()) if target_date.weekday() != 0 else 7
    next_week_monday = target_date + timedelta(days=days_to_next_mon)

    for contract in active_contracts:
        # Search for draft timesheets for this contract closing on or before target_date
        query = {
            'contract': contract,
            'status': Timesheet.Status.DRAFT,
        }
        if not force:
            query['week_end_date__lte'] = target_date

        draft_timesheets = Timesheet.objects.filter(**query)

        for timesheet in draft_timesheets:
            total_hours = timesheet.total_hours
            if total_hours > Decimal('0.00'):
                talent_earnings = timesheet.talent_gross_earnings
                invoice_ref = "PENDING_DRY_RUN"
                gross_amount = timesheet.total_employer_charge

                if not dry_run:
                    with transaction.atomic():
                        timesheet.status = Timesheet.Status.SUBMITTED
                        timesheet.submitted_at = timezone.now()
                        timesheet.save(update_fields=['status', 'submitted_at'])

                        invoice = generate_invoice_for_timesheet(timesheet)
                        if invoice:
                            if invoice.payment_status == ContractInvoice.PaymentStatus.DRAFT:
                                invoice.payment_status = ContractInvoice.PaymentStatus.ISSUED
                                invoice.save(update_fields=['payment_status'])
                            invoice_ref = invoice.invoice_ref
                            gross_amount = invoice.gross_amount

                        # Notify Employer
                        employer_link = reverse('billing:invoice_detail', kwargs={'pk': str(invoice.pk)}) if invoice else reverse('contracts:contract_detail', kwargs={'pk': str(contract.pk)})
                        send_notification(
                            recipient=contract.employer.user,
                            title="Weekly Timesheet Locked & Invoice Issued",
                            message=f"Timesheet for {contract.candidate.full_name} (week ending {timesheet.week_end_date}) locked with {total_hours} hrs. Invoice {invoice_ref} for ${gross_amount} is ready for review.",
                            notification_type=Notification.NotificationType.SYSTEM,
                            link=employer_link
                        )

                        # Notify Candidate
                        send_notification(
                            recipient=contract.candidate.user,
                            title="Weekly Timesheet Submitted",
                            message=f"Your timesheet for week ending {timesheet.week_end_date} has been automatically locked ({total_hours} hrs, ${talent_earnings}). Invoice issued to {contract.employer.company_name}.",
                            notification_type=Notification.NotificationType.SYSTEM,
                            link=reverse('billing:candidate_earnings')
                        )

                timesheets_locked += 1
                invoices_generated += 1
                total_hours_locked += total_hours
                total_amount_invoiced += gross_amount

                details.append({
                    'contract_ref': contract.contract_ref,
                    'candidate': contract.candidate.full_name,
                    'employer': contract.employer.company_name,
                    'week_ending': str(timesheet.week_end_date),
                    'hours': float(total_hours),
                    'amount': float(gross_amount),
                    'invoice_ref': invoice_ref,
                    'action': 'LOCKED_AND_INVOICED' if not dry_run else 'PREVIEW_LOCK'
                })
            else:
                details.append({
                    'contract_ref': contract.contract_ref,
                    'candidate': contract.candidate.full_name,
                    'employer': contract.employer.company_name,
                    'week_ending': str(timesheet.week_end_date),
                    'hours': 0.0,
                    'amount': 0.0,
                    'invoice_ref': 'NONE (0 hrs)',
                    'action': 'SKIPPED_ZERO_HOURS'
                })

        # Pre-populate next week's empty timesheet with 7 entries
        if not dry_run:
            contract.get_or_create_current_timesheet(target_date=next_week_monday)
        next_week_initialized += 1

    summary_message = (
        f"Evaluated {active_contracts.count()} active hourly contracts. "
        f"Locked {timesheets_locked} timesheets ({total_hours_locked} hrs, ${total_amount_invoiced}). "
        f"Prepared {next_week_initialized} next-week timesheets."
    )

    log_entry = AutomationExecutionLog.objects.create(
        task_type=AutomationExecutionLog.TaskType.TIMESHEET_LOCK,
        executed_by=actor if getattr(actor, 'is_authenticated', False) else None,
        is_dry_run=dry_run,
        target_date=target_date,
        status=AutomationExecutionLog.Status.SUCCESS,
        items_evaluated=active_contracts.count(),
        items_processed=timesheets_locked,
        total_amount=total_amount_invoiced,
        summary_message=summary_message,
        details_json={
            'target_date': str(target_date),
            'next_week_monday': str(next_week_monday),
            'dry_run': dry_run,
            'timesheets_locked': timesheets_locked,
            'total_hours': float(total_hours_locked),
            'total_amount': float(total_amount_invoiced),
            'next_week_initialized': next_week_initialized,
            'records': details
        }
    )

    return {
        'success': True,
        'log_id': str(log_entry.id),
        'task_type': 'TIMESHEET_LOCK',
        'is_dry_run': dry_run,
        'target_date': str(target_date),
        'contracts_evaluated': active_contracts.count(),
        'timesheets_locked': timesheets_locked,
        'invoices_generated': invoices_generated,
        'total_hours': float(total_hours_locked),
        'total_amount': float(total_amount_invoiced),
        'next_week_initialized': next_week_initialized,
        'summary': summary_message,
        'records': details
    }


def execute_friday_payout_run(as_of_date=None, dry_run=False, actor=None, force=False):
    """
    Friday Batch Payout Engine (Friday 09:00 Cron / Staff Automation Hub).
    Evaluates all settled invoices queued for payout:
    1. Queries ContractInvoice where payment_status == SETTLED and payout_status == QUEUED.
    2. Groups invoices by candidate.
    3. Validates verified CandidatePayoutProfile (Paystack Ghana MoMo or Flutterwave Bank).
    4. Executes payment disbursement via gateway service or sandbox simulation.
    5. Transitions invoice payout_status to COMPLETED and creates immutable PaymentTransaction (PAYOUT).
    6. Dispatches candidate payout notifications.
    7. Logs run in AutomationExecutionLog.
    """
    if as_of_date is None:
        target_date = timezone.localdate()
    elif isinstance(as_of_date, str):
        target_date = date.fromisoformat(as_of_date)
    else:
        target_date = as_of_date

    queued_invoices = ContractInvoice.objects.filter(
        payment_status=ContractInvoice.PaymentStatus.SETTLED,
        payout_status=ContractInvoice.PayoutStatus.QUEUED
    ).select_related('contract__candidate__user', 'contract__employer')

    # Group by candidate
    candidate_map = {}
    for inv in queued_invoices:
        cand = inv.contract.candidate
        candidate_map.setdefault(cand, []).append(inv)

    total_disbursed = Decimal('0.00')
    candidates_paid = 0
    candidates_skipped = 0
    invoices_completed_count = 0
    details = []

    paystack_svc = PaystackGhanaService()
    flw_svc = FlutterwaveService()

    for candidate, inv_list in candidate_map.items():
        candidate_total = sum((inv.talent_earnings for inv in inv_list), Decimal('0.00'))
        payout_profile = getattr(candidate, 'payout_profile', None)

        if not payout_profile or not payout_profile.is_configured:
            candidates_skipped += 1
            reason = "Payout profile not configured or unverified"
            details.append({
                'candidate': candidate.full_name,
                'invoices': [inv.invoice_ref for inv in inv_list],
                'amount': float(candidate_total),
                'destination': 'MISSING_OR_UNVERIFIED',
                'status': 'SKIPPED_ON_HOLD',
                'message': reason
            })
            if not dry_run:
                send_notification(
                    recipient=candidate.user,
                    title="Action Required: Payout On Hold",
                    message="You have settled clinical earnings queued for Friday payout, but your payout method is missing or unverified. Please configure your MoMo or Bank details.",
                    notification_type=Notification.NotificationType.SYSTEM,
                    link=reverse('billing:candidate_earnings')
                )
            continue

        payout_ref = f"SIM-PAYOUT-{uuid.uuid4().hex[:10].upper()}"
        gateway_name = "PAYSTACK" if payout_profile.payout_method == CandidatePayoutProfile.PayoutMethod.PAYSTACK_MOMO else "FLUTTERWAVE"

        if not dry_run:
            with transaction.atomic():
                if payout_profile.payout_method == CandidatePayoutProfile.PayoutMethod.PAYSTACK_MOMO:
                    recipient_code = payout_profile.paystack_recipient_code or paystack_svc.create_transfer_recipient(payout_profile)
                    if recipient_code and not payout_profile.paystack_recipient_code:
                        payout_profile.paystack_recipient_code = recipient_code
                        payout_profile.save(update_fields=['paystack_recipient_code'])

                    # Standard GHS FX peg (approx 15.5 GHS per USD)
                    ghs_amount = (candidate_total * Decimal('15.50')).quantize(Decimal('0.01'))
                    res = paystack_svc.initiate_transfer(
                        amount_ghs=float(ghs_amount),
                        recipient_code=recipient_code,
                        reason=f"Kodafriq Weekly Payout ({candidate.full_name})"
                    )
                    payout_ref = res.get('data', {}).get('reference') or f"pstk_trf_{uuid.uuid4().hex[:10]}"
                    gateway_type = PaymentTransaction.Gateway.PAYSTACK
                else:
                    res = flw_svc.initiate_bank_transfer(
                        amount=candidate_total,
                        bank_code=payout_profile.bank_code,
                        account_number=payout_profile.account_number,
                        currency=payout_profile.currency or 'USD',
                        narration=f"Kodafriq Weekly Payout ({candidate.full_name})"
                    )
                    payout_ref = res.get('data', {}).get('reference') or f"flw_trf_{uuid.uuid4().hex[:10]}"
                    gateway_type = PaymentTransaction.Gateway.FLUTTERWAVE

                for inv in inv_list:
                    inv.mark_disbursed(gateway_payout_ref=payout_ref)
                    invoices_completed_count += 1

                    PaymentTransaction.objects.create(
                        reference=f"TX-PAYOUT-{uuid.uuid4().hex[:10].upper()}",
                        invoice=inv,
                        amount=inv.talent_earnings,
                        currency=inv.currency,
                        transaction_type=PaymentTransaction.TransactionType.PAYOUT,
                        gateway=gateway_type,
                        status=PaymentTransaction.Status.SUCCESS,
                        raw_payload={'gateway_payout_ref': payout_ref, 'gateway_response': res}
                    )

                send_notification(
                    recipient=candidate.user,
                    title="Weekly Earnings Disbursed!",
                    message=f"Your weekly payout of ${candidate_total} has been disbursed to {payout_profile.masked_destination}. Reference: {payout_ref}.",
                    notification_type=Notification.NotificationType.SYSTEM,
                    link=reverse('billing:candidate_earnings')
                )
        else:
            invoices_completed_count += len(inv_list)

        candidates_paid += 1
        total_disbursed += candidate_total

        details.append({
            'candidate': candidate.full_name,
            'invoices': [inv.invoice_ref for inv in inv_list],
            'amount': float(candidate_total),
            'destination': payout_profile.masked_destination,
            'gateway': gateway_name,
            'reference': payout_ref if not dry_run else 'PREVIEW_SIM_REF',
            'status': 'DISBURSED' if not dry_run else 'PREVIEW_READY'
        })

    exec_status = AutomationExecutionLog.Status.SUCCESS if candidates_skipped == 0 else AutomationExecutionLog.Status.PARTIAL
    summary_message = (
        f"Evaluated {queued_invoices.count()} settled invoices across {len(candidate_map)} candidates. "
        f"Disbursed ${total_disbursed} to {candidates_paid} candidates. "
        f"{candidates_skipped} candidates skipped due to unconfigured payout profiles."
    )

    log_entry = AutomationExecutionLog.objects.create(
        task_type=AutomationExecutionLog.TaskType.FRIDAY_PAYOUT,
        executed_by=actor if getattr(actor, 'is_authenticated', False) else None,
        is_dry_run=dry_run,
        target_date=target_date,
        status=exec_status,
        items_evaluated=queued_invoices.count(),
        items_processed=invoices_completed_count,
        total_amount=total_disbursed,
        summary_message=summary_message,
        details_json={
            'target_date': str(target_date),
            'dry_run': dry_run,
            'invoices_evaluated': queued_invoices.count(),
            'candidates_paid': candidates_paid,
            'candidates_skipped': candidates_skipped,
            'total_disbursed': float(total_disbursed),
            'records': details
        }
    )

    return {
        'success': True,
        'log_id': str(log_entry.id),
        'task_type': 'FRIDAY_PAYOUT',
        'is_dry_run': dry_run,
        'target_date': str(target_date),
        'invoices_evaluated': queued_invoices.count(),
        'candidates_count': len(candidate_map),
        'candidates_paid': candidates_paid,
        'candidates_skipped': candidates_skipped,
        'invoices_completed': invoices_completed_count,
        'total_disbursed': float(total_disbursed),
        'summary': summary_message,
        'records': details
    }
