from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.utils import timezone
from django.db import models
from django.http import HttpResponseForbidden

from .models import Contract, Timesheet, TimesheetEntry, Milestone, DisputeCase
from .forms import (
    ContractCreateForm, TimesheetSubmitForm, TimesheetReviewForm,
    MilestoneSubmitForm, DisputeCaseForm, StaffDisputeAdjudicateForm
)
from apps.accounts.models import CandidateProfile, EmployerProfile
from apps.employers.models import Job, Application
from apps.dashboard.models import send_notification, Notification, log_staff_action, AuditLog
from apps.billing.models import ContractInvoice, PlatformFeeConfig
from apps.billing.services.invoicing import generate_invoice_for_timesheet, generate_invoice_for_milestone


class ContractListView(LoginRequiredMixin, View):
    """
    Overview of all engagement contracts for either an Employer or a Candidate.
    """
    def get(self, request):
        user = request.user
        is_staff = bool(user.is_superuser or user.is_kodafriq_staff or user.role in [user.Role.STAFF, user.Role.ADMIN])
        is_employer = bool(user.is_employer and not is_staff)
        is_candidate = bool(user.is_candidate and not is_staff)

        if is_staff:
            if not (user.is_superuser or user.has_perm('dashboard.access_contracts')):
                messages.error(request, "You do not have administrative permission to access the Client Contracts docket. Please contact a superuser.")
                return redirect('dashboard:staff')
            contracts = Contract.objects.all().select_related('employer', 'candidate__user', 'job')
        elif is_employer:
            profile = getattr(user, 'employer_profile', None)
            if not profile:
                messages.error(request, "Please set up your employer profile first.")
                return redirect('employers:company_profile')
            contracts = Contract.objects.filter(employer=profile).select_related('candidate__user', 'job')
        elif is_candidate:
            profile = getattr(user, 'candidate_profile', None)
            if not profile:
                messages.error(request, "Please complete your candidate profile first.")
                return redirect('dashboard:candidate_profile_edit')
            contracts = Contract.objects.filter(candidate=profile).select_related('employer', 'job')
        else:
            return redirect('dashboard:index')

        # Filter by status if provided in GET
        status_filter = request.GET.get('status')
        if status_filter:
            contracts = contracts.filter(status=status_filter)

        # Calculate high level metrics
        total_contracts = contracts.count()
        active_contracts = contracts.filter(status=Contract.Status.ACTIVE).count()
        pending_contracts = contracts.filter(status=Contract.Status.PENDING).count()
        completed_contracts = contracts.filter(status=Contract.Status.COMPLETED).count()

        context = {
            'contracts': contracts,
            'total_contracts': total_contracts,
            'active_contracts': active_contracts,
            'pending_contracts': pending_contracts,
            'completed_contracts': completed_contracts,
            'is_employer': is_employer,
            'is_candidate': is_candidate,
            'selected_status': status_filter,
            'contract_statuses': Contract.Status.choices,
        }
        return render(request, 'contracts/contract_list.html', context)


class ContractDetailView(LoginRequiredMixin, View):
    """
    Full view of a contract agreement, financial rate structure, timesheets, and milestones.
    """
    def get(self, request, pk):
        contract = get_object_or_404(
            Contract.objects.select_related('employer', 'candidate__user', 'job'),
            pk=pk
        )
        user = request.user
        is_staff = bool(user.is_superuser or user.is_kodafriq_staff or user.role in [user.Role.STAFF, user.Role.ADMIN])
        is_employer = bool(user.is_employer and (contract.employer.user == user) and not is_staff)
        is_candidate = bool(user.is_candidate and (contract.candidate.user == user) and not is_staff)

        if is_staff:
            if not (user.is_superuser or user.has_perm('dashboard.access_contracts')):
                messages.error(request, "You do not have administrative permission to access this contract. Please contact a superuser.")
                return redirect('dashboard:staff')
        elif not (is_employer or is_candidate):
            return HttpResponseForbidden("You do not have access to view this engagement contract.")

        timesheets = contract.timesheets.all().prefetch_related('entries').order_by('-week_start_date')
        milestones = contract.milestones.all().order_by('order', 'created_at')
        disputes = contract.disputes.all()

        current_timesheet = None
        if contract.contract_type == Contract.ContractType.HOURLY and contract.status == Contract.Status.ACTIVE:
            current_timesheet = contract.get_or_create_current_timesheet()

        context = {
            'contract': contract,
            'timesheets': timesheets,
            'milestones': milestones,
            'disputes': disputes,
            'current_timesheet': current_timesheet,
            'is_employer': is_employer,
            'is_candidate': is_candidate,
            'is_staff': is_staff,
        }
        return render(request, 'contracts/contract_detail.html', context)


class ContractCreateView(LoginRequiredMixin, View):
    """
    Healthcare Employer creates a new engagement contract for a talent.
    """
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_employer or request.user.is_kodafriq_staff):
            messages.error(request, "Only employers can create engagement contracts.")
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        employer = getattr(request.user, 'employer_profile', None)
        if not employer:
            messages.error(request, "Please set up your employer profile first.")
            return redirect('employers:company_profile')

        initial_data = {}
        candidate_id = request.GET.get('candidate_id')
        job_id = request.GET.get('job_id')
        app_id = request.GET.get('application_id')

        if app_id:
            try:
                application = Application.objects.select_related('candidate', 'job').get(id=app_id, job__employer=employer)
                initial_data['candidate'] = application.candidate
                initial_data['job'] = application.job
                initial_data['title'] = application.job.title
            except Application.DoesNotExist:
                pass

        if candidate_id and not initial_data.get('candidate'):
            try:
                initial_data['candidate'] = CandidateProfile.objects.get(id=candidate_id)
            except CandidateProfile.DoesNotExist:
                pass

        if job_id and not initial_data.get('job'):
            try:
                initial_data['job'] = Job.objects.get(id=job_id, employer=employer)
                if not initial_data.get('title'):
                    initial_data['title'] = initial_data['job'].title
            except Job.DoesNotExist:
                pass

        form = ContractCreateForm(initial=initial_data, employer=employer)
        return render(request, 'contracts/contract_form.html', {'form': form, 'employer': employer})

    def post(self, request):
        employer = getattr(request.user, 'employer_profile', None)
        form = ContractCreateForm(request.POST, employer=employer)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.employer = employer
            contract.status = Contract.Status.PENDING
            contract.save()

            # Dispatch notification to talent
            send_notification(
                recipient=contract.candidate.user,
                title="New Contract Offer Received",
                message=f"{employer.company_name} has extended an engagement offer: '{contract.title}'. Review terms and accept to begin.",
                notification_type=Notification.NotificationType.SYSTEM,
                link=contract.get_absolute_url()
            )

            messages.success(request, f"Contract offer {contract.contract_ref} successfully created and sent to {contract.candidate.full_name}.")
            return redirect(contract.get_absolute_url())

        return render(request, 'contracts/contract_form.html', {'form': form, 'employer': employer})


class ContractActionView(LoginRequiredMixin, View):
    """
    Accept, decline, pause, or terminate contracts.
    """
    def post(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        action = request.POST.get('action')
        user = request.user
        is_employer = user.is_employer and (contract.employer.user == user)
        is_candidate = user.is_candidate and (contract.candidate.user == user)
        is_staff = user.is_kodafriq_staff

        if action == 'accept' and (is_candidate or is_staff):
            contract.status = Contract.Status.ACTIVE
            if not contract.start_date:
                contract.start_date = timezone.localdate()
            contract.save()

            # Pre-generate first week's timesheet if hourly
            if contract.contract_type == Contract.ContractType.HOURLY:
                contract.get_or_create_current_timesheet()

            send_notification(
                recipient=contract.employer.user,
                title="Contract Offer Accepted",
                message=f"{contract.candidate.full_name} has accepted the contract '{contract.title}'. Engagement is now Active.",
                notification_type=Notification.NotificationType.SYSTEM,
                link=contract.get_absolute_url()
            )
            messages.success(request, f"You have accepted contract {contract.contract_ref}! Work engagement is now Active.")

        elif action == 'decline' and (is_candidate or is_staff):
            contract.status = Contract.Status.DECLINED
            contract.save()
            send_notification(
                recipient=contract.employer.user,
                title="Contract Offer Declined",
                message=f"{contract.candidate.full_name} has declined the contract offer '{contract.title}'.",
                notification_type=Notification.NotificationType.SYSTEM,
                link=contract.get_absolute_url()
            )
            messages.info(request, f"Contract {contract.contract_ref} offer has been declined.")

        elif action == 'pause' and (is_employer or is_staff):
            contract.status = Contract.Status.PAUSED
            contract.save()
            messages.info(request, f"Contract {contract.contract_ref} has been paused.")

        elif action == 'resume' and (is_employer or is_staff):
            contract.status = Contract.Status.ACTIVE
            contract.save()
            messages.success(request, f"Contract {contract.contract_ref} has been resumed.")

        elif action == 'terminate' and (is_employer or is_staff):
            contract.status = Contract.Status.TERMINATED
            contract.end_date = timezone.localdate()
            contract.save()
            messages.warning(request, f"Contract {contract.contract_ref} has been terminated.")

        return redirect(contract.get_absolute_url())


class CandidateTimesheetLogView(LoginRequiredMixin, View):
    """
    Candidate interactive weekly timesheet logging interface (Mon-Sun).
    Allows recording daily billable hours, charts coded count, and clinical work notes.
    """
    def get(self, request, pk):
        timesheet = get_object_or_404(
            Timesheet.objects.select_related('contract__candidate__user', 'contract__employer'),
            pk=pk
        )
        user = request.user
        contract = timesheet.contract
        is_candidate = user.is_candidate and (contract.candidate.user == user)
        is_staff = user.is_kodafriq_staff

        if not (is_candidate or is_staff):
            return HttpResponseForbidden("You are not authorized to log hours for this timesheet.")

        entries = timesheet.entries.all().order_by('date')
        submit_form = TimesheetSubmitForm(instance=timesheet)

        context = {
            'timesheet': timesheet,
            'contract': contract,
            'entries': entries,
            'submit_form': submit_form,
            'is_editable': timesheet.status in [Timesheet.Status.DRAFT, Timesheet.Status.DISPUTED],
        }
        return render(request, 'contracts/timesheet_log.html', context)

    def post(self, request, pk):
        timesheet = get_object_or_404(
            Timesheet.objects.select_related('contract__candidate__user', 'contract__employer'),
            pk=pk
        )
        user = request.user
        contract = timesheet.contract
        is_candidate = user.is_candidate and (contract.candidate.user == user)
        is_staff = user.is_kodafriq_staff

        if not (is_candidate or is_staff):
            return HttpResponseForbidden("Unauthorized.")

        if timesheet.status not in [Timesheet.Status.DRAFT, Timesheet.Status.DISPUTED]:
            messages.error(request, "This timesheet has already been submitted or approved and is locked.")
            return redirect(timesheet.get_absolute_url())

        action = request.POST.get('form_action', 'save_draft')

        # Update all 7 daily entries
        for entry in timesheet.entries.all():
            hours_str = request.POST.get(f'hours_{entry.id}', '0.00')
            charts_str = request.POST.get(f'charts_{entry.id}', '0')
            desc = request.POST.get(f'desc_{entry.id}', '').strip()

            try:
                entry.hours_worked = max(Decimal('0.00'), min(Decimal('24.00'), Decimal(hours_str)))
            except Exception:
                entry.hours_worked = Decimal('0.00')

            try:
                entry.charts_coded_count = max(0, int(charts_str))
            except Exception:
                entry.charts_coded_count = 0

            entry.work_description = desc
            entry.save()

        # Update candidate notes
        candidate_notes = request.POST.get('candidate_notes', '').strip()
        timesheet.candidate_notes = candidate_notes

        if action == 'submit':
            timesheet.status = Timesheet.Status.SUBMITTED
            timesheet.submitted_at = timezone.now()
            timesheet.save()

            # Notify employer
            send_notification(
                recipient=contract.employer.user,
                title="Weekly Timesheet Submitted for Review",
                message=f"{contract.candidate.full_name} submitted timesheet for week of {timesheet.week_start_date} ({timesheet.total_hours} hrs, {timesheet.total_charts_coded} charts coded). Please review.",
                notification_type=Notification.NotificationType.SYSTEM,
                link=reverse('contracts:employer_timesheet_review', kwargs={'pk': str(timesheet.pk)})
            )
            messages.success(request, f"Timesheet for week of {timesheet.week_start_date} submitted successfully to {contract.employer.company_name}!")
        else:
            timesheet.save()
            messages.success(request, "Timesheet draft saved successfully.")

        return redirect(timesheet.get_absolute_url())


class EmployerTimesheetReviewView(LoginRequiredMixin, View):
    """
    Healthcare Employer timesheet audit, approval, and dispute interface.
    """
    def get(self, request, pk):
        timesheet = get_object_or_404(
            Timesheet.objects.select_related('contract__employer__user', 'contract__candidate__user'),
            pk=pk
        )
        user = request.user
        contract = timesheet.contract
        is_employer = user.is_employer and (contract.employer.user == user)
        is_staff = user.is_kodafriq_staff

        if not (is_employer or is_staff):
            return HttpResponseForbidden("You are not authorized to review this timesheet.")

        entries = timesheet.entries.all().order_by('date')
        review_form = TimesheetReviewForm(initial={'employer_review_notes': timesheet.employer_review_notes})

        context = {
            'timesheet': timesheet,
            'contract': contract,
            'entries': entries,
            'review_form': review_form,
        }
        return render(request, 'contracts/timesheet_review.html', context)

    def post(self, request, pk):
        timesheet = get_object_or_404(
            Timesheet.objects.select_related('contract__employer__user', 'contract__candidate__user'),
            pk=pk
        )
        user = request.user
        contract = timesheet.contract
        is_employer = user.is_employer and (contract.employer.user == user)
        is_staff = user.is_kodafriq_staff

        if not (is_employer or is_staff):
            return HttpResponseForbidden("Unauthorized.")

        form = TimesheetReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            notes = form.cleaned_data['employer_review_notes']

            timesheet.employer_review_notes = notes

            if action == 'approve':
                timesheet.status = Timesheet.Status.APPROVED
                timesheet.reviewed_at = timezone.now()
                timesheet.save()
                # Generate Billing Invoice & update Candidate Earnings Ledger
                generate_invoice_for_timesheet(timesheet)

                send_notification(
                    recipient=contract.candidate.user,
                    title="Weekly Timesheet Approved!",
                    message=f"{contract.employer.company_name} approved your timesheet for week of {timesheet.week_start_date} ({timesheet.total_hours} hrs, ${timesheet.talent_gross_earnings} net earnings).",
                    notification_type=Notification.NotificationType.SYSTEM,
                    link=timesheet.get_absolute_url()
                )
                messages.success(request, f"Timesheet for week of {timesheet.week_start_date} approved successfully!")

            elif action == 'dispute':
                timesheet.status = Timesheet.Status.DISPUTED
                timesheet.save()

                DisputeCase.objects.create(
                    contract=contract,
                    timesheet=timesheet,
                    raised_by=user,
                    reason=notes or "Employer flagged timesheet hours/records for adjustment."
                )

                send_notification(
                    recipient=contract.candidate.user,
                    title="Timesheet Under Dispute / Adjustment Request",
                    message=f"{contract.employer.company_name} requested adjustments to your timesheet for week of {timesheet.week_start_date}. Notes: {notes}",
                    notification_type=Notification.NotificationType.SYSTEM,
                    link=timesheet.get_absolute_url()
                )
                messages.warning(request, "Timesheet has been flagged for adjustment.")

            return redirect(contract.get_absolute_url())

        entries = timesheet.entries.all().order_by('date')
        return render(request, 'contracts/timesheet_review.html', {
            'timesheet': timesheet,
            'contract': contract,
            'entries': entries,
            'review_form': form,
        })


class MilestoneSubmitView(LoginRequiredMixin, View):
    """
    Talent uploads milestone deliverables and clinical audit notes.
    """
    def post(self, request, pk):
        milestone = get_object_or_404(
            Milestone.objects.select_related('contract__candidate__user', 'contract__employer__user'),
            pk=pk
        )
        user = request.user
        contract = milestone.contract
        if not (user.is_candidate and contract.candidate.user == user or user.is_kodafriq_staff):
            return HttpResponseForbidden("Unauthorized.")

        form = MilestoneSubmitForm(request.POST, request.FILES, instance=milestone)
        if form.is_valid():
            m = form.save(commit=False)
            m.status = Milestone.Status.SUBMITTED
            m.submitted_at = timezone.now()
            m.save()

            send_notification(
                recipient=contract.employer.user,
                title="Milestone Deliverable Submitted",
                message=f"{contract.candidate.full_name} submitted deliverable for '{m.title}'. Please review and approve.",
                notification_type=Notification.NotificationType.SYSTEM,
                link=contract.get_absolute_url()
            )
            messages.success(request, f"Milestone '{m.title}' submitted for employer review.")
        else:
            messages.error(request, "Failed to submit milestone. Please verify details.")

        return redirect(contract.get_absolute_url())


class MilestoneApproveView(LoginRequiredMixin, View):
    """
    Employer signs off on milestone deliverable.
    """
    def post(self, request, pk):
        milestone = get_object_or_404(
            Milestone.objects.select_related('contract__employer__user', 'contract__candidate__user'),
            pk=pk
        )
        user = request.user
        contract = milestone.contract
        if not (user.is_employer and contract.employer.user == user or user.is_kodafriq_staff):
            return HttpResponseForbidden("Unauthorized.")

        feedback = request.POST.get('employer_feedback', '').strip()
        milestone.employer_feedback = feedback
        milestone.status = Milestone.Status.APPROVED
        milestone.approved_at = timezone.now()
        milestone.save()
        # Generate Billing Invoice & update Candidate Earnings Ledger
        generate_invoice_for_milestone(milestone)

        send_notification(
            recipient=contract.candidate.user,
            title="Milestone Deliverable Approved!",
            message=f"{contract.employer.company_name} approved milestone '{milestone.title}' (${milestone.amount} net compensation).",
            notification_type=Notification.NotificationType.SYSTEM,
            link=contract.get_absolute_url()
        )
        messages.success(request, f"Milestone '{milestone.title}' approved successfully!")
        return redirect(contract.get_absolute_url())


class StaffDisputeListView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Staff Dispute Mediation Center - Master audit and mediation docket.
    """
    def test_func(self):
        user = self.request.user
        return bool(user.is_authenticated and (user.is_superuser or user.has_perm('dashboard.access_disputes')))

    def handle_no_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return redirect('accounts:login')
        if not getattr(user, 'is_kodafriq_staff', False) and not user.is_staff:
            return HttpResponseForbidden("Access restricted to platform administrative staff.")
        messages.error(self.request, "You do not have administrative permission to access the Dispute Mediation Center. Please contact a superuser.")
        return redirect('dashboard:staff')

    def get(self, request):
        status_filter = request.GET.get('status', '').upper()
        search_query = request.GET.get('q', '').strip()

        disputes = DisputeCase.objects.select_related(
            'contract', 'contract__employer', 'contract__candidate',
            'contract__candidate__user', 'contract__employer__user',
            'timesheet', 'milestone', 'raised_by'
        ).order_by('-created_at')

        if status_filter in [s[0] for s in DisputeCase.Status.choices]:
            disputes = disputes.filter(status=status_filter)

        if search_query:
            disputes = disputes.filter(
                models.Q(contract__contract_ref__icontains=search_query) |
                models.Q(contract__title__icontains=search_query) |
                models.Q(contract__employer__company_name__icontains=search_query) |
                models.Q(contract__candidate__user__first_name__icontains=search_query) |
                models.Q(contract__candidate__user__last_name__icontains=search_query) |
                models.Q(reason__icontains=search_query)
            )

        # Aggregate Dispute Center Metrics
        all_disputes = DisputeCase.objects.all()
        total_count = all_disputes.count()
        open_count = all_disputes.filter(status=DisputeCase.Status.OPEN).count()
        resolved_count = all_disputes.filter(status=DisputeCase.Status.RESOLVED).count()
        cancelled_count = all_disputes.filter(status=DisputeCase.Status.CANCELLED).count()

        # Disputed Funds at Stake ($)
        open_cases = all_disputes.filter(status=DisputeCase.Status.OPEN).select_related('contract', 'timesheet', 'milestone')
        total_funds_at_stake = sum((d.disputed_amount for d in open_cases), Decimal('0.00'))

        context = {
            'disputes': disputes,
            'selected_status': status_filter,
            'search_query': search_query,
            'total_count': total_count,
            'open_count': open_count,
            'resolved_count': resolved_count,
            'cancelled_count': cancelled_count,
            'total_funds_at_stake': total_funds_at_stake,
        }
        return render(request, 'contracts/dispute_list.html', context)


class StaffDisputeDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Staff Detailed Dispute Dossier with timecard audit, deliverable inspection, and evidence.
    """
    def test_func(self):
        user = self.request.user
        return bool(user.is_authenticated and (user.is_superuser or user.has_perm('dashboard.access_disputes')))

    def handle_no_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return redirect('accounts:login')
        if not getattr(user, 'is_kodafriq_staff', False) and not user.is_staff:
            return HttpResponseForbidden("Access restricted to platform administrative staff.")
        messages.error(self.request, "You do not have administrative permission to access this dispute dossier. Please contact a superuser.")
        return redirect('dashboard:staff')

    def get(self, request, pk):
        dispute = get_object_or_404(
            DisputeCase.objects.select_related(
                'contract', 'contract__employer', 'contract__candidate',
                'contract__candidate__user', 'contract__employer__user',
                'timesheet', 'milestone', 'raised_by'
            ),
            pk=pk
        )
        contract = dispute.contract
        timesheet = dispute.timesheet
        milestone = dispute.milestone
        timesheet_entries = timesheet.entries.all().order_by('date') if timesheet else []

        adjudicate_form = StaffDisputeAdjudicateForm(initial={
            'adjusted_hours': timesheet.total_hours if timesheet else None,
            'adjusted_amount': milestone.amount if milestone else None
        })

        context = {
            'dispute': dispute,
            'contract': contract,
            'timesheet': timesheet,
            'timesheet_entries': timesheet_entries,
            'milestone': milestone,
            'adjudicate_form': adjudicate_form,
        }
        return render(request, 'contracts/dispute_detail.html', context)


class StaffDisputeAdjudicateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Staff binding mediation and ruling executor.
    """
    def test_func(self):
        user = self.request.user
        return bool(user.is_authenticated and (user.is_superuser or user.has_perm('dashboard.access_disputes')))

    def handle_no_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return redirect('accounts:login')
        if not getattr(user, 'is_kodafriq_staff', False) and not user.is_staff:
            return HttpResponseForbidden("Access restricted to platform administrative staff.")
        messages.error(self.request, "You do not have administrative permission to adjudicate disputes. Please contact a superuser.")
        return redirect('dashboard:staff')

    def post(self, request, pk):
        dispute = get_object_or_404(
            DisputeCase.objects.select_related(
                'contract', 'contract__employer', 'contract__candidate',
                'contract__candidate__user', 'contract__employer__user',
                'timesheet', 'milestone'
            ),
            pk=pk
        )
        if dispute.status != DisputeCase.Status.OPEN:
            messages.warning(request, "This dispute has already been adjudicated or closed.")
            return redirect('contracts:dispute_detail', pk=dispute.pk)

        form = StaffDisputeAdjudicateForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please provide complete adjudication notes and ruling choice.")
            return redirect('contracts:dispute_detail', pk=dispute.pk)

        decision = form.cleaned_data['decision']
        notes = form.cleaned_data['mediator_notes']
        adjusted_hours = form.cleaned_data.get('adjusted_hours')
        adjusted_amount = form.cleaned_data.get('adjusted_amount')

        contract = dispute.contract
        timesheet = dispute.timesheet
        milestone = dispute.milestone

        if decision == 'FAVOR_CANDIDATE':
            # Release full escrow funds to talent
            if timesheet:
                timesheet.status = Timesheet.Status.APPROVED
                timesheet.reviewed_at = timezone.now()
                timesheet.employer_review_notes = f"[Mediator Approved]: {notes}"
                timesheet.save()
                generate_invoice_for_timesheet(timesheet)
            elif milestone:
                milestone.status = Milestone.Status.APPROVED
                milestone.approved_at = timezone.now()
                milestone.employer_feedback = f"[Mediator Approved]: {notes}"
                milestone.save()
                generate_invoice_for_milestone(milestone)

            outcome_label = "Ruled in Favor of Candidate (Funds Released)"

        elif decision == 'FAVOR_EMPLOYER':
            # Cancel / Void payment obligation
            if timesheet:
                timesheet.status = Timesheet.Status.DRAFT
                timesheet.employer_review_notes = f"[Mediator Rejected/Voided]: {notes}"
                timesheet.save()
            elif milestone:
                milestone.status = Milestone.Status.PENDING
                milestone.employer_feedback = f"[Mediator Rejected/Voided]: {notes}"
                milestone.save()

            outcome_label = "Ruled in Favor of Employer (Charge Voided)"

        elif decision == 'COMPROMISE':
            # Mediated split / adjustment
            if timesheet and adjusted_hours is not None:
                timesheet.status = Timesheet.Status.APPROVED
                timesheet.reviewed_at = timezone.now()
                timesheet.employer_review_notes = f"[Mediated Compromise ({adjusted_hours} hrs)]: {notes}"
                timesheet.save()
                # Generate invoice
                inv = generate_invoice_for_timesheet(timesheet)
                if inv and adjusted_hours != timesheet.total_hours:
                    inv.talent_earnings = (adjusted_hours * contract.rate_per_hour).quantize(Decimal('0.01'))
                    inv.kodafriq_fee = (inv.talent_earnings * (contract.kodafriq_fee_percent / Decimal('100.00'))).quantize(Decimal('0.01'))
                    sub = inv.talent_earnings + inv.kodafriq_fee
                    from apps.billing.models import PlatformFeeConfig
                    fee_cfg = PlatformFeeConfig.get_active()
                    inv.processing_fee = ((sub * (fee_cfg.gateway_processing_fee_percent / Decimal('100.00'))) + fee_cfg.gateway_flat_fee).quantize(Decimal('0.01'))
                    inv.gross_amount = (sub + inv.processing_fee).quantize(Decimal('0.01'))
                    inv.payment_status = ContractInvoice.PaymentStatus.ISSUED
                    inv.save()
            elif milestone and adjusted_amount is not None:
                milestone.status = Milestone.Status.APPROVED
                milestone.approved_at = timezone.now()
                milestone.employer_feedback = f"[Mediated Compromise (${adjusted_amount})]: {notes}"
                milestone.save()
                inv = generate_invoice_for_milestone(milestone)
                if inv and adjusted_amount != milestone.amount:
                    inv.talent_earnings = adjusted_amount
                    inv.kodafriq_fee = (inv.talent_earnings * (contract.kodafriq_fee_percent / Decimal('100.00'))).quantize(Decimal('0.01'))
                    sub = inv.talent_earnings + inv.kodafriq_fee
                    from apps.billing.models import PlatformFeeConfig
                    fee_cfg = PlatformFeeConfig.get_active()
                    inv.processing_fee = ((sub * (fee_cfg.gateway_processing_fee_percent / Decimal('100.00'))) + fee_cfg.gateway_flat_fee).quantize(Decimal('0.01'))
                    inv.gross_amount = (sub + inv.processing_fee).quantize(Decimal('0.01'))
                    inv.payment_status = ContractInvoice.PaymentStatus.ISSUED
                    inv.save()

            outcome_label = f"Mediated Compromise ({adjusted_hours or adjusted_amount} units)"

        # Mark dispute resolved
        dispute.status = DisputeCase.Status.RESOLVED
        dispute.resolution_notes = f"[{outcome_label}] Adjudicated by {request.user.get_full_name() or request.user.username}: {notes}"
        dispute.resolved_at = timezone.now()
        dispute.save()

        # Audit Log
        log_staff_action(
            actor=request.user,
            action=f"Adjudicated dispute #{dispute.id}: {outcome_label}",
            action_category=AuditLog.Category.MODERATION,
            target_user=contract.candidate.user,
            target_entity='DisputeCase',
            target_id=str(dispute.id),
            request=request
        )

        # Notify Candidate
        send_notification(
            recipient=contract.candidate.user,
            title=f"Dispute Adjudicated: {outcome_label}",
            message=f"Kodafriq Staff has adjudicated the dispute for {contract.title}. Ruling: {outcome_label}. Mediator Notes: {notes}",
            notification_type=Notification.NotificationType.SYSTEM,
            link=contract.get_absolute_url()
        )

        # Notify Employer
        send_notification(
            recipient=contract.employer.user,
            title=f"Dispute Adjudicated: {outcome_label}",
            message=f"Kodafriq Staff has completed arbitration for {contract.title}. Ruling: {outcome_label}. Mediator Notes: {notes}",
            notification_type=Notification.NotificationType.SYSTEM,
            link=contract.get_absolute_url()
        )

        messages.success(request, f"Dispute successfully adjudicated: {outcome_label}")
        return redirect('contracts:dispute_detail', pk=dispute.pk)


class MilestoneDisputeView(LoginRequiredMixin, View):
    """
    Employer flags milestone deliverable for arbitration / dispute.
    """
    def post(self, request, pk):
        milestone = get_object_or_404(
            Milestone.objects.select_related('contract__employer__user', 'contract__candidate__user'),
            pk=pk
        )
        user = request.user
        contract = milestone.contract
        is_employer = user.is_employer and (contract.employer.user == user)
        is_staff = user.is_kodafriq_staff

        if not (is_employer or is_staff):
            return HttpResponseForbidden("Unauthorized.")

        form = DisputeCaseForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            milestone.status = Milestone.Status.DISPUTED
            milestone.save()

            dispute = DisputeCase.objects.create(
                contract=contract,
                milestone=milestone,
                raised_by=user,
                reason=reason
            )

            send_notification(
                recipient=contract.candidate.user,
                title="Milestone Flagged for Dispute / Mediation",
                message=f"{contract.employer.company_name} flagged milestone '{milestone.title}' for dispute. Kodafriq Staff will arbitrate.",
                notification_type=Notification.NotificationType.SYSTEM,
                link=contract.get_absolute_url()
            )
            messages.warning(request, f"Milestone '{milestone.title}' submitted to Dispute Mediation Center.")
        else:
            messages.error(request, "Please provide a valid reason for disputing this deliverable.")

        return redirect(contract.get_absolute_url())
