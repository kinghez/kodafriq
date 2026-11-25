import csv
import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.db.models import Q, Sum, Avg, Count
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from django.utils import timezone
from .models import (
    EmployerLead, LeadContact, HiringSignal, TalentReverseMatch,
    OutreachMessage, CRMOpportunity, CRMActivity, GrowthAutomationLog,
    normalize_company_domain
)
from .forms import (
    EmployerLeadForm, LeadContactForm, HiringSignalForm,
    CRMActivityForm, CRMOpportunityForm, OutreachMessageForm,
    OutreachGenerateForm, PublicShortlistInquiryForm,
    LeadConversionForm, QuickActivityForm
)
from .services.matcher import compute_lead_reverse_matches
from .services.intent import calculate_lead_intent_score
from .services.scraper import inspect_lead_career_page
from .services.discovery import (
    search_healthcare_employers, import_discovered_lead, import_leads_from_csv
)
from .services.connectors import search_all_connectors, CONNECTOR_REGISTRY
from .services.automation import (
    poll_and_age_vacancies, apply_hiring_intent_decay,
    archive_dormant_leads, sync_candidate_availability_to_growth,
    generate_weekly_bd_digest, send_weekly_bd_digest_email
)
from .services.outreach_generator import generate_outreach_pitch
from .services.crm_service import (
    transition_opportunity_stage, convert_lead_to_employer,
    get_kanban_board_data, ensure_opportunities_for_all_leads
)
from apps.accounts.models import User, EmployerProfile, CandidateProfile
from apps.contracts.models import Contract


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restricts view access strictly to authenticated Kodafriq staff/admin users."""
    def test_func(self):
        user = self.request.user
        return bool(user.is_authenticated and getattr(user, 'is_kodafriq_staff', False))

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "Access restricted to Kodafriq Business Development & Platform Staff.")
        return redirect('dashboard:staff')


class GrowthOSDashboardView(StaffRequiredMixin, TemplateView):
    """
    Overview command center for employer discovery, hiring intent metrics,
    priority quadrant breakdown, and revenue pipeline forecasting.
    """
    template_name = 'growth_os/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        leads = EmployerLead.objects.all()

        # Core Metrics
        ctx['total_leads_count'] = leads.count()
        ctx['tier_1_count'] = leads.filter(hiring_intent_score__gte=60, talent_fit_score__gte=60).count()
        ctx['tier_2_count'] = leads.filter(hiring_intent_score__gte=60, talent_fit_score__lt=60).count()
        ctx['tier_3_count'] = leads.filter(hiring_intent_score__lt=60, talent_fit_score__gte=60).count()
        ctx['tier_4_count'] = leads.filter(hiring_intent_score__lt=60, talent_fit_score__lt=60).count()

        # Signals & Vacancies
        ctx['active_vacancies_count'] = HiringSignal.objects.filter(is_active=True).count()
        ctx['persistent_vacancies_count'] = HiringSignal.objects.filter(is_active=True, is_persistent=True).count()

        # Pipeline & Deal Value
        ensure_opportunities_for_all_leads()
        opportunities = CRMOpportunity.objects.select_related('lead')
        active_opps = opportunities.exclude(
            stage__in=[CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON, CRMOpportunity.Stage.CLOSED_LOST]
        )
        ctx['active_opportunities_count'] = active_opps.count()

        pipeline_agg = opportunities.exclude(stage=CRMOpportunity.Stage.CLOSED_LOST).aggregate(
            total=Sum('estimated_monthly_deal_value')
        )
        ctx['pipeline_value_usd'] = pipeline_agg['total'] or Decimal('0.00')

        # Weighted Pipeline Value ($)
        weighted_sum = Decimal('0.00')
        for opp in opportunities.exclude(stage=CRMOpportunity.Stage.CLOSED_LOST):
            weight = Decimal(str(opp.win_probability_percent)) / Decimal('100.00')
            weighted_sum += (opp.estimated_monthly_deal_value * weight)
        ctx['weighted_pipeline_value_usd'] = weighted_sum

        # Placement Won & Win Rate
        won_count = opportunities.filter(stage=CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON).count()
        closed_lost_count = opportunities.filter(stage=CRMOpportunity.Stage.CLOSED_LOST).count()
        total_closed = won_count + closed_lost_count
        ctx['won_deals_count'] = won_count
        ctx['win_rate_percent'] = round((won_count / total_closed * 100), 1) if total_closed > 0 else 0.0

        # Follow-Up Reminders
        today = timezone.localdate()
        ctx['overdue_followups'] = opportunities.filter(
            next_follow_up_date__lt=today
        ).exclude(
            stage__in=[CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON, CRMOpportunity.Stage.CLOSED_LOST]
        ).select_related('lead')[:5]

        ctx['today_followups'] = opportunities.filter(
            next_follow_up_date=today
        ).exclude(
            stage__in=[CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON, CRMOpportunity.Stage.CLOSED_LOST]
        ).select_related('lead')[:5]

        # Multi-Sector Pipeline Breakdown
        sector_breakdown = []
        for code, label in EmployerLead.IndustryVertical.choices:
            s_leads = leads.filter(industry_vertical=code)
            s_count = s_leads.count()
            if s_count > 0:
                s_val = opportunities.filter(lead__in=s_leads).exclude(
                    stage=CRMOpportunity.Stage.CLOSED_LOST
                ).aggregate(v=Sum('estimated_monthly_deal_value'))['v'] or Decimal('0.00')
                sector_breakdown.append({
                    'sector_code': code,
                    'sector_name': label,
                    'lead_count': s_count,
                    'pipeline_value': s_val
                })
        ctx['sector_breakdown'] = sector_breakdown

        # Funnel Conversion Stages
        f_discovered = opportunities.count()
        f_outreach = opportunities.filter(
            stage__in=[
                CRMOpportunity.Stage.STAGE_5_OUTREACH_SENT,
                CRMOpportunity.Stage.STAGE_6_REPLY_RECEIVED,
                CRMOpportunity.Stage.STAGE_7_MEETING_SCHEDULED,
                CRMOpportunity.Stage.STAGE_8_SHORTLIST_DELIVERED,
                CRMOpportunity.Stage.STAGE_9_INTERVIEWS,
                CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON,
            ]
        ).count()
        f_meetings = opportunities.filter(
            stage__in=[
                CRMOpportunity.Stage.STAGE_7_MEETING_SCHEDULED,
                CRMOpportunity.Stage.STAGE_8_SHORTLIST_DELIVERED,
                CRMOpportunity.Stage.STAGE_9_INTERVIEWS,
                CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON,
            ]
        ).count()
        f_shortlists = opportunities.filter(
            stage__in=[
                CRMOpportunity.Stage.STAGE_8_SHORTLIST_DELIVERED,
                CRMOpportunity.Stage.STAGE_9_INTERVIEWS,
                CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON,
            ]
        ).count()
        f_won = won_count

        ctx['funnel_metrics'] = [
            {'name': 'Discovered Leads', 'count': f_discovered, 'pct': 100},
            {'name': 'Outreach Engaged', 'count': f_outreach, 'pct': round((f_outreach / f_discovered * 100), 1) if f_discovered else 0},
            {'name': 'Meetings Scheduled', 'count': f_meetings, 'pct': round((f_meetings / f_discovered * 100), 1) if f_discovered else 0},
            {'name': 'Shortlists Delivered', 'count': f_shortlists, 'pct': round((f_shortlists / f_discovered * 100), 1) if f_discovered else 0},
            {'name': 'Placements Won', 'count': f_won, 'pct': round((f_won / f_discovered * 100), 1) if f_discovered else 0},
        ]

        # Averages
        avg_scores = leads.aggregate(avg_intent=Avg('hiring_intent_score'), avg_fit=Avg('talent_fit_score'))
        ctx['avg_intent_score'] = round(avg_scores['avg_intent'] or 0, 1)
        ctx['avg_fit_score'] = round(avg_scores['avg_fit'] or 0, 1)

        # Stage distribution
        stage_counts = dict(CRMOpportunity.objects.values_list('stage').annotate(c=Count('id')))
        ctx['stage_breakdown'] = [
            {'stage_code': code, 'stage_name': label, 'count': stage_counts.get(code, 0)}
            for code, label in CRMOpportunity.Stage.choices
        ]

        # Recent priority leads
        ctx['top_priority_leads'] = leads.filter(
            hiring_intent_score__gte=60, talent_fit_score__gte=60
        ).prefetch_related('vacancies', 'contacts')[:8]

        # Recent Activities
        ctx['recent_activities'] = CRMActivity.objects.select_related(
            'lead', 'performed_by'
        ).order_by('-created_at')[:10]

        # Recent leads
        ctx['recent_leads'] = leads.order_by('-created_at')[:6]

        return ctx


class EmployerLeadListView(StaffRequiredMixin, ListView):
    """
    Searchable, filterable directory of employer leads with dual-score filtering,
    priority quadrants, and assignment tracking.
    """
    model = EmployerLead
    template_name = 'growth_os/lead_list.html'
    context_object_name = 'leads'
    paginate_by = 20

    def get_queryset(self):
        qs = EmployerLead.objects.select_related('assigned_staff').prefetch_related('vacancies', 'contacts')

        # Search Query (Company, Domain, City, Notes)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(company_name__icontains=q) |
                Q(domain__icontains=q) |
                Q(city__icontains=q) |
                Q(notes__icontains=q)
            )

        # Industry Vertical Filter
        vertical = self.request.GET.get('vertical', '').strip()
        if vertical:
            qs = qs.filter(industry_vertical=vertical)

        # Status Filter
        status = self.request.GET.get('status', '').strip()
        if status:
            qs = qs.filter(status=status)

        # Priority Tier Filter
        tier = self.request.GET.get('tier', '').strip()
        if tier == '1':
            qs = qs.filter(hiring_intent_score__gte=60, talent_fit_score__gte=60)
        elif tier == '2':
            qs = qs.filter(hiring_intent_score__gte=60, talent_fit_score__lt=60)
        elif tier == '3':
            qs = qs.filter(hiring_intent_score__lt=60, talent_fit_score__gte=60)
        elif tier == '4':
            qs = qs.filter(hiring_intent_score__lt=60, talent_fit_score__lt=60)

        # Minimum Intent & Fit Score Filters
        min_intent = self.request.GET.get('min_intent', '').strip()
        if min_intent.isdigit():
            qs = qs.filter(hiring_intent_score__gte=int(min_intent))

        min_fit = self.request.GET.get('min_fit', '').strip()
        if min_fit.isdigit():
            qs = qs.filter(talent_fit_score__gte=int(min_fit))

        # Assigned Staff
        assigned = self.request.GET.get('assigned', '').strip()
        if assigned == 'me':
            qs = qs.filter(assigned_staff=self.request.user)
        elif assigned == 'unassigned':
            qs = qs.filter(assigned_staff__isnull=True)

        # Sorting
        sort = self.request.GET.get('sort', 'priority')
        if sort == 'intent':
            qs = qs.order_by('-hiring_intent_score', '-created_at')
        elif sort == 'fit':
            qs = qs.order_by('-talent_fit_score', '-created_at')
        elif sort == 'name':
            qs = qs.order_by('company_name')
        elif sort == 'recent':
            qs = qs.order_by('-created_at')
        else:
            # Default: Tier 1 (intent + fit) descending
            qs = qs.order_by('-hiring_intent_score', '-talent_fit_score', '-created_at')

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['industry_choices'] = EmployerLead.IndustryVertical.choices
        ctx['status_choices'] = EmployerLead.Status.choices
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['current_vertical'] = self.request.GET.get('vertical', '')
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_tier'] = self.request.GET.get('tier', '')
        ctx['current_min_intent'] = self.request.GET.get('min_intent', '')
        ctx['current_min_fit'] = self.request.GET.get('min_fit', '')
        ctx['current_assigned'] = self.request.GET.get('assigned', '')
        ctx['current_sort'] = self.request.GET.get('sort', 'priority')
        ctx['total_matching_count'] = self.get_queryset().count()
        return ctx


class EmployerLeadDetailView(StaffRequiredMixin, DetailView):
    """
    360-degree employer intelligence dossier featuring dual-score diagnostics,
    open vacancies, decision maker profiles, reverse talent matches,
    and full CRM activity history.
    """
    model = EmployerLead
    template_name = 'growth_os/lead_detail.html'
    context_object_name = 'lead'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        lead = self.object

        ctx['contacts'] = lead.contacts.all()
        ctx['vacancies'] = lead.vacancies.all()
        ctx['talent_matches'] = lead.talent_matches.select_related(
            'candidate', 'candidate__user', 'vacancy'
        ).prefetch_related('candidate__skills__skill').order_by('-match_score')[:15]

        ctx['activities'] = lead.activities.select_related('performed_by').order_by('-created_at')[:30]

        # Ensure CRMOpportunity exists
        opportunity, created = CRMOpportunity.objects.get_or_create(
            lead=lead,
            defaults={
                'stage': CRMOpportunity.Stage.STAGE_1_DISCOVERED,
                'target_roles_count': max(1, lead.vacancies.filter(is_active=True).count()),
                'priority': CRMOpportunity.Priority.HIGH if lead.priority_tier <= 2 else CRMOpportunity.Priority.MEDIUM,
            }
        )
        ctx['opportunity'] = opportunity
        ctx['opportunity_form'] = CRMOpportunityForm(instance=opportunity)

        # Quick action forms
        ctx['contact_form'] = LeadContactForm()
        ctx['vacancy_form'] = HiringSignalForm()
        ctx['activity_form'] = CRMActivityForm()

        # Outreaches
        ctx['outreaches'] = lead.outreaches.select_related('contact').order_by('-created_at')[:10]
        ctx['outreach_form'] = OutreachGenerateForm()

        return ctx


class EmployerLeadCreateView(StaffRequiredMixin, CreateView):
    """Creates a new employer lead record and initializes linked CRM tracking."""
    model = EmployerLead
    form_class = EmployerLeadForm
    template_name = 'growth_os/lead_form.html'

    def form_valid(self, form):
        lead = form.save()
        if not lead.assigned_staff:
            lead.assigned_staff = self.request.user
            lead.save(update_fields=['assigned_staff'])

        # Auto-create CRMOpportunity
        CRMOpportunity.objects.get_or_create(
            lead=lead,
            defaults={'stage': CRMOpportunity.Stage.STAGE_1_DISCOVERED}
        )

        # Recalculate intent and reverse talent matches
        lead.recalculate_intent_score()
        try:
            compute_lead_reverse_matches(lead)
        except Exception:
            pass

        # Audit activity
        CRMActivity.objects.create(
            lead=lead,
            activity_type=CRMActivity.ActivityType.NOTE,
            summary=f"Employer lead added manually by {self.request.user.get_full_name() or self.request.user.email}",
            performed_by=self.request.user
        )

        messages.success(self.request, f"Employer lead '{lead.company_name}' successfully added to GrowthOS.")
        return redirect('growth_os:lead_detail', pk=lead.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_create'] = True
        return ctx


class EmployerLeadUpdateView(StaffRequiredMixin, UpdateView):
    """Updates company metadata and BD assignment for an employer lead."""
    model = EmployerLead
    form_class = EmployerLeadForm
    template_name = 'growth_os/lead_form.html'

    def form_valid(self, form):
        lead = form.save()
        lead.recalculate_intent_score()
        messages.success(self.request, f"Employer lead '{lead.company_name}' successfully updated.")
        return redirect('growth_os:lead_detail', pk=lead.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_create'] = False
        ctx['lead'] = self.object
        return ctx


class LeadContactCreateView(StaffRequiredMixin, View):
    """Quick modal/page action to add a decision maker to a lead."""
    def post(self, request, lead_id):
        lead = get_object_or_404(EmployerLead, id=lead_id)
        form = LeadContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.lead = lead
            contact.save()

            # Recalculate Intent Score with new contact bonus
            new_score = lead.recalculate_intent_score()

            CRMActivity.objects.create(
                lead=lead,
                activity_type=CRMActivity.ActivityType.NOTE,
                summary=f"Decision maker contact added: {contact.full_name} ({contact.job_title or 'No title'})",
                details=f"Email: {contact.email or 'N/A'} | Phone: {contact.phone or 'N/A'}",
                performed_by=request.user
            )

            # Progress opportunity stage if still in STAGE_1 or STAGE_2
            if hasattr(lead, 'crm_opportunity') and lead.crm_opportunity.stage in [
                CRMOpportunity.Stage.STAGE_1_DISCOVERED,
                CRMOpportunity.Stage.STAGE_2_QUALIFIED,
                CRMOpportunity.Stage.STAGE_3_HIRING_SIGNAL
            ]:
                lead.crm_opportunity.stage = CRMOpportunity.Stage.STAGE_4_CONTACT_IDENTIFIED
                lead.crm_opportunity.save(update_fields=['stage'])

            messages.success(request, f"Added contact {contact.full_name}. Hiring Intent updated to {new_score}.")
        else:
            messages.error(request, "Failed to add contact. Please review required fields.")

        return redirect('growth_os:lead_detail', pk=lead.id)


class LeadContactDeleteView(StaffRequiredMixin, View):
    """Deletes a contact and refreshes the lead's intent score."""
    def post(self, request, pk):
        contact = get_object_or_404(LeadContact, id=pk)
        lead = contact.lead
        contact_name = contact.full_name
        contact.delete()
        lead.recalculate_intent_score()

        messages.info(request, f"Contact '{contact_name}' removed.")
        return redirect('growth_os:lead_detail', pk=lead.id)


class HiringSignalCreateView(StaffRequiredMixin, View):
    """Quick modal/page action to record a detected hiring signal or vacancy."""
    def post(self, request, lead_id):
        lead = get_object_or_404(EmployerLead, id=lead_id)
        form = HiringSignalForm(request.POST)
        if form.is_valid():
            vacancy = form.save(commit=False)
            vacancy.lead = lead
            vacancy.save()

            # Recalculate Intent Score and Reverse Matches
            lead.recalculate_intent_score()
            compute_lead_reverse_matches(lead)

            CRMActivity.objects.create(
                lead=lead,
                activity_type=CRMActivity.ActivityType.NOTE,
                summary=f"Vacancy recorded: {vacancy.job_title} ({vacancy.get_role_category_display()})",
                details=f"Days open: {vacancy.days_open} | Persistent (>30d): {vacancy.is_persistent}",
                performed_by=request.user
            )

            messages.success(request, f"Vacancy '{vacancy.job_title}' added. Talent fit matches recalculated.")
        else:
            messages.error(request, "Failed to add vacancy. Please check the form data.")

        return redirect('growth_os:lead_detail', pk=lead.id)


class HiringSignalToggleView(StaffRequiredMixin, View):
    """Toggles active/closed status of a vacancy and refreshes scores."""
    def post(self, request, pk):
        vacancy = get_object_or_404(HiringSignal, id=pk)
        lead = vacancy.lead
        vacancy.is_active = not vacancy.is_active
        vacancy.save(update_fields=['is_active'])

        lead.recalculate_intent_score()
        compute_lead_reverse_matches(lead)

        status_text = "marked active" if vacancy.is_active else "marked closed/filled"
        messages.info(request, f"Vacancy '{vacancy.job_title}' {status_text}.")
        return redirect('growth_os:lead_detail', pk=lead.id)


class CRMActivityCreateView(StaffRequiredMixin, View):
    """Logs a phone call, meeting, email interaction, or strategic note."""
    def post(self, request, lead_id):
        lead = get_object_or_404(EmployerLead, id=lead_id)
        form = CRMActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.lead = lead
            activity.performed_by = request.user
            activity.save()
            messages.success(request, "Activity log updated.")
        else:
            messages.error(request, "Unable to save activity log.")

        return redirect('growth_os:lead_detail', pk=lead.id)


class CRMOpportunityUpdateView(StaffRequiredMixin, View):
    """Updates opportunity deal size, pipeline stage, win probability, and follow-up."""
    def post(self, request, lead_id):
        lead = get_object_or_404(EmployerLead, id=lead_id)
        opportunity, created = CRMOpportunity.objects.get_or_create(lead=lead)
        old_stage = opportunity.stage

        form = CRMOpportunityForm(request.POST, instance=opportunity)
        if form.is_valid():
            opp = form.save()

            if old_stage != opp.stage:
                CRMActivity.objects.create(
                    lead=lead,
                    activity_type=CRMActivity.ActivityType.STAGE_CHANGE,
                    summary=f"Pipeline stage moved from {opportunity.get_stage_display()} to {opp.get_stage_display()}",
                    details=f"Estimated Deal: ${opp.estimated_monthly_deal_value}/mo | Win Prob: {opp.win_probability_percent}%",
                    performed_by=request.user
                )

            messages.success(request, f"Pipeline opportunity updated ({opp.get_stage_display()}).")
        else:
            messages.error(request, "Failed to update pipeline opportunity. Please check values.")

        return redirect('growth_os:lead_detail', pk=lead.id)


class EmployerLeadRecalculateScoresView(StaffRequiredMixin, View):
    """Forces recalculation of hiring intent score, reverse talent matches, and talent fit score."""
    def post(self, request, pk):
        lead = get_object_or_404(EmployerLead, id=pk)
        intent = lead.recalculate_intent_score()
        fit = compute_lead_reverse_matches(lead)

        messages.success(
            request,
            f"Scores recalculated for {lead.company_name}: Intent = {intent}/100, Talent Fit = {fit}/100 (Tier {lead.priority_tier})."
        )
        return redirect('growth_os:lead_detail', pk=lead.id)


class LeadReverseMatchToggleShortlistView(StaffRequiredMixin, View):
    """Toggles shortlist status for a reverse-matched candidate on a lead."""
    def post(self, request, pk):
        match = get_object_or_404(TalentReverseMatch, id=pk)
        match.is_shortlisted = not match.is_shortlisted
        match.save(update_fields=['is_shortlisted'])

        action = "shortlisted" if match.is_shortlisted else "removed from shortlist"
        cand_name = match.candidate.full_name or "Candidate"
        messages.info(request, f"{cand_name} {action} for outreach pitches.")
        return redirect('growth_os:lead_detail', pk=match.lead.id)


class LeadScanCareersView(StaffRequiredMixin, View):
    """
    Crawls and scans the employer's careers page to automatically discover
    open vacancies, extract coding/billing skills, and recalculate Intent & Fit scores.
    """
    def post(self, request, pk):
        lead = get_object_or_404(EmployerLead, id=pk)
        result = inspect_lead_career_page(lead)

        if result.get('success'):
            vac_count = result.get('vacancies_detected', 0)
            new_count = result.get('new_vacancies_added', 0)
            intent = result.get('intent_score', lead.hiring_intent_score)
            fit = result.get('fit_score', lead.talent_fit_score)
            messages.success(
                request,
                f"Web scan completed for {lead.company_name}! Found {vac_count} vacancy signals ({new_count} new). "
                f"Hiring Intent is now {intent}/100, Talent Fit is {fit}/100 (Tier {lead.priority_tier})."
            )
        else:
            messages.warning(request, f"Web scan notice: {result.get('error', 'No active positions detected.')}")

        return redirect('growth_os:lead_detail', pk=lead.id)


class EmployerDiscoveryHubView(StaffRequiredMixin, TemplateView):
    """
    Interactive discovery console for searching and cataloguing prospective
    employers across search engines, LinkedIn, Indeed, and industry directories.
    """
    template_name = 'growth_os/discovery_hub.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '').strip()
        country = self.request.GET.get('country', 'United States').strip()
        business_type = self.request.GET.get('business_type', 'ALL').strip()
        services = self.request.GET.get('services', 'ALL').strip()
        source = self.request.GET.get('source', 'ALL').strip()
        page_num = self.request.GET.get('page', 1)

        ctx['current_q'] = query
        ctx['current_country'] = country
        ctx['current_business_type'] = business_type
        ctx['current_services'] = services
        ctx['current_source'] = source
        ctx['connector_registry'] = CONNECTOR_REGISTRY

        # High-level Metrics (100% live database counts and dynamic trends)
        now = timezone.now()
        month_ago = now - timezone.timedelta(days=30)
        two_months_ago = now - timezone.timedelta(days=60)
        week_ago = now - timezone.timedelta(days=7)
        two_weeks_ago = now - timezone.timedelta(days=14)

        total_in_db = EmployerLead.objects.count()
        ctx['total_employers_count'] = f"{total_in_db:,}"

        # Dynamic month-over-month trend for total employers
        recent_month_leads = EmployerLead.objects.filter(created_at__gte=month_ago).count()
        prev_month_leads = EmployerLead.objects.filter(created_at__gte=two_months_ago, created_at__lt=month_ago).count()
        if prev_month_leads > 0:
            total_trend_pct = round(((recent_month_leads - prev_month_leads) / prev_month_leads) * 100, 1)
        elif total_in_db > 0 and recent_month_leads > 0:
            total_trend_pct = round((recent_month_leads / total_in_db) * 100, 1)
        else:
            total_trend_pct = 0.0
        ctx['total_trend_pct'] = f"{abs(total_trend_pct):.1f}%"
        ctx['total_trend_is_up'] = total_trend_pct >= 0

        # Qualified leads: status == QUALIFIED or talent_fit_score >= 80
        qualified_qs = EmployerLead.objects.filter(
            Q(status=EmployerLead.Status.QUALIFIED) | Q(talent_fit_score__gte=80)
        )
        qualified_count = qualified_qs.count()
        ctx['qualified_leads_count'] = f"{qualified_count:,}"

        recent_qual = qualified_qs.filter(created_at__gte=month_ago).count()
        prev_qual = qualified_qs.filter(created_at__gte=two_months_ago, created_at__lt=month_ago).count()
        if prev_qual > 0:
            qual_trend_pct = round(((recent_qual - prev_qual) / prev_qual) * 100, 1)
        elif qualified_count > 0 and recent_qual > 0:
            qual_trend_pct = round((recent_qual / qualified_count) * 100, 1)
        else:
            qual_trend_pct = 0.0
        ctx['qual_trend_pct'] = f"{abs(qual_trend_pct):.1f}%"
        ctx['qual_trend_is_up'] = qual_trend_pct >= 0

        # Countries covered
        countries_distinct = (
            EmployerLead.objects.exclude(country='')
            .exclude(country__isnull=True)
            .values('country')
            .distinct()
            .count()
        )
        ctx['countries_count'] = countries_distinct

        recent_countries = (
            EmployerLead.objects.filter(created_at__gte=month_ago)
            .exclude(country='')
            .exclude(country__isnull=True)
            .values('country')
            .distinct()
            .count()
        )
        if countries_distinct > 0 and recent_countries > 0:
            country_trend_pct = round((recent_countries / countries_distinct) * 100, 1)
        else:
            country_trend_pct = 0.0
        ctx['country_trend_pct'] = f"{abs(country_trend_pct):.1f}%"
        ctx['country_trend_is_up'] = country_trend_pct >= 0

        # New this week
        new_this_week = EmployerLead.objects.filter(created_at__gte=week_ago).count()
        ctx['new_this_week_count'] = f"{new_this_week:,}"

        prev_week_leads = EmployerLead.objects.filter(created_at__gte=two_weeks_ago, created_at__lt=week_ago).count()
        if prev_week_leads > 0:
            week_trend_pct = round(((new_this_week - prev_week_leads) / prev_week_leads) * 100, 1)
        elif new_this_week > 0:
            week_trend_pct = 100.0
        else:
            week_trend_pct = 0.0
        ctx['week_trend_pct'] = f"{abs(week_trend_pct):.1f}%"
        ctx['week_trend_is_up'] = week_trend_pct >= 0

        ctx['last_synced'] = timezone.now().strftime("%I:%M %p")

        # Business type categories for filter dropdown
        ctx['business_types'] = [
            ('ALL', 'All healthcare'),
            ('RCM_SERVICES', 'Revenue Cycle Management (RCM)'),
            ('MEDICAL_BILLING', 'Medical Billing & AR Follow-Up'),
            ('MEDICAL_CODING', 'Medical Coding & Auditing'),
            ('HEALTHCARE_BPO', 'Healthcare BPO & Outsourcing'),
            ('HOSPITAL_CLINIC', 'Hospital, Network or Specialty Clinic'),
            ('IT_SOFTWARE_DEV', 'Software Engineering & IT'),
            ('IT_CLOUD_DEVOPS', 'Cloud Infrastructure & DevOps'),
            ('FINANCE_ACCOUNTING', 'Fintech, Accounting & Audit'),
        ]

        # Markets for filter dropdown
        ctx['markets'] = [
            ('United States', 'United States'),
            ('United Kingdom', 'United Kingdom'),
            ('Canada', 'Canada'),
            ('Australia', 'Australia'),
            ('United Arab Emirates', 'United Arab Emirates'),
            ('Global', 'Global / All Markets'),
        ]

        # Services for filter dropdown
        ctx['services_options'] = [
            ('ALL', 'Medical Billing, RCM'),
            ('BILLING_CODING', 'Billing, Coding'),
            ('CLAIMS_RCM', 'Claims, RCM'),
            ('MEDICAL_CODING', 'Medical Coding'),
            ('REVENUE_CYCLE', 'Revenue Cycle'),
            ('ALL_SERVICES', 'All Specialized Services'),
        ]

        # Sources for filter dropdown
        ctx['sources_options'] = [
            ('ALL', 'All permitted sources'),
            ('LINKEDIN_JOBS', 'LinkedIn Jobs'),
            ('INDEED_JOBS', 'Indeed Hiring Feeds'),
            ('GOOGLE_SEARCH', 'Google Search & Maps'),
            ('DIRECTORIES', 'Healthcare Directories'),
        ]

        # Preset query buttons across sectors
        ctx['preset_queries'] = [
            "Revenue Cycle Management Companies",
            "Medical Billing Services Hiring Coders",
            "Software Development & Cloud Engineering",
            "DevOps, SRE & Cloud Infrastructure Consultancies",
            "Cybersecurity & SOC Operations",
            "IT Helpdesk & Remote Technical Support",
            "Fintech & Outsourced Accounting Services",
            "Texas Medical Billing & IT Services"
        ]

        # Standard showcase employers matching the exact user design layout
        showcase_companies = [
            {
                'company_name': 'Northstar Revenue Partners',
                'business_type': 'RCM Provider',
                'location': 'Austin, TX, USA',
                'services': 'Medical billing, Claims',
                'domain': 'northstarrevenue.example',
                'website': 'https://northstarrevenue.example',
                'relevance': 96,
                'status': 'Qualified',
                'already_tracked': False,
                'source': 'GOOGLE_SEARCH',
                'country': 'United States',
                'city': 'Austin, TX',
                'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
            },
            {
                'company_name': 'ClearPath Medical Billing',
                'business_type': 'Medical Billing',
                'location': 'Tampa, FL, USA',
                'services': 'Billing, Coding',
                'domain': 'clearpathbilling.example',
                'website': 'https://clearpathbilling.example',
                'relevance': 92,
                'status': 'New',
                'already_tracked': False,
                'source': 'LINKEDIN_JOBS',
                'country': 'United States',
                'city': 'Tampa, FL',
                'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_BILLING,
            },
            {
                'company_name': 'Meridian Health Admin',
                'business_type': 'Healthcare BPO',
                'location': 'Manchester, UK',
                'services': 'Claims, RCM',
                'domain': 'meridianadmin.example',
                'website': 'https://meridianadmin.example',
                'relevance': 89,
                'status': 'Review',
                'already_tracked': False,
                'source': 'GOOGLE_SEARCH',
                'country': 'United Kingdom',
                'city': 'Manchester',
                'industry_vertical': EmployerLead.IndustryVertical.HEALTHCARE_BPO,
            },
            {
                'company_name': 'Pinnacle Coding Solutions',
                'business_type': 'Coding Firm',
                'location': 'Phoenix, AZ, USA',
                'services': 'Medical coding',
                'domain': 'pinnaclecoding.example',
                'website': 'https://pinnaclecoding.example',
                'relevance': 87,
                'status': 'Qualified',
                'already_tracked': False,
                'source': 'INDEED_JOBS',
                'country': 'United States',
                'city': 'Phoenix, AZ',
                'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_CODING,
            },
            {
                'company_name': 'CareAxis Practice Services',
                'business_type': 'Practice Services',
                'location': 'Toronto, Canada',
                'services': 'Revenue cycle',
                'domain': 'careaxis.example',
                'website': 'https://careaxis.example',
                'relevance': 83,
                'status': 'New',
                'already_tracked': False,
                'source': 'GOOGLE_SEARCH',
                'country': 'Canada',
                'city': 'Toronto',
                'industry_vertical': EmployerLead.IndustryVertical.HOSPITAL_CLINIC,
            },
        ]

        table_records = []
        if query:
            source_filter = None if source == 'ALL' else source
            raw_results = search_all_connectors(
                query=query,
                location=country if country not in ('ALL', 'Global') else 'United States',
                limit_per_source=10,
                source_key=source_filter
            )

            domains = [r['domain'] for r in raw_results if r.get('domain')]
            existing_map = {
                lead.domain: lead
                for lead in EmployerLead.objects.filter(domain__in=domains)
            }

            relevance_pool = [96, 92, 89, 87, 83, 80, 78, 75]
            for idx, r in enumerate(raw_results):
                ex = existing_map.get(r.get('domain', '').lower())
                rel = relevance_pool[idx % len(relevance_pool)]
                status = 'Qualified' if (ex and ex.status == EmployerLead.Status.QUALIFIED) or rel >= 90 else ('New' if not ex else 'Review')
                b_type = r.get('industry_vertical_display') or ('RCM Provider' if 'rcm' in r.get('company_name', '').lower() else 'Medical Billing')
                table_records.append({
                    'company_name': r.get('company_name'),
                    'business_type': b_type,
                    'location': f"{r.get('city', '')}, {r.get('country', country)}".strip(', ') or country,
                    'services': 'Medical billing, Claims' if idx % 2 == 0 else 'Billing, Coding',
                    'domain': r.get('domain') or 'company.example',
                    'website': r.get('website') or f"https://{r.get('domain', '')}",
                    'careers_url': r.get('careers_url', ''),
                    'relevance': rel,
                    'status': status,
                    'already_tracked': bool(ex),
                    'lead_id': ex.id if ex else None,
                    'priority_tier': ex.priority_tier if ex else 1,
                    'source': r.get('source', 'GOOGLE_SEARCH'),
                    'snippet': r.get('snippet', ''),
                    'city': r.get('city', ''),
                    'country': r.get('country', country),
                    'industry_vertical': r.get('industry_vertical', EmployerLead.IndustryVertical.RCM_SERVICES),
                })
        else:
            # Query existing database leads first
            db_leads_qs = EmployerLead.objects.all()
            if business_type and business_type != 'ALL':
                db_leads_qs = db_leads_qs.filter(industry_vertical=business_type)
            if country and country not in ('ALL', 'Global'):
                db_leads_qs = db_leads_qs.filter(country__icontains=country)
            if source and source != 'ALL':
                db_leads_qs = db_leads_qs.filter(source=source)

            db_leads = db_leads_qs.order_by('-talent_fit_score', '-created_at')

            services_lookup = {
                EmployerLead.IndustryVertical.RCM_SERVICES: 'Medical billing, Claims',
                EmployerLead.IndustryVertical.MEDICAL_BILLING: 'Billing, AR Follow-Up',
                EmployerLead.IndustryVertical.MEDICAL_CODING: 'Medical coding, Auditing',
                EmployerLead.IndustryVertical.HEALTHCARE_BPO: 'Claims, RCM Outsourcing',
                EmployerLead.IndustryVertical.HOSPITAL_CLINIC: 'Clinical Practice Services',
                EmployerLead.IndustryVertical.IT_SOFTWARE_DEV: 'Software Dev & Cloud',
                EmployerLead.IndustryVertical.IT_CLOUD_DEVOPS: 'DevOps & Cloud Infra',
                EmployerLead.IndustryVertical.FINANCE_ACCOUNTING: 'Fintech & Accounting',
            }

            if db_leads.exists():
                relevance_pool = [96, 92, 89, 87, 83]
                for idx, lead in enumerate(db_leads):
                    rel = lead.talent_fit_score if lead.talent_fit_score > 0 else relevance_pool[idx % len(relevance_pool)]
                    status = 'Qualified' if lead.status == EmployerLead.Status.QUALIFIED or rel >= 90 else ('Review' if lead.status == EmployerLead.Status.IN_PIPELINE else 'New')
                    loc = f"{lead.city}, {lead.country}".strip(', ') or (lead.country or "United States")
                    services_text = services_lookup.get(lead.industry_vertical, "Medical billing, Claims")
                    table_records.append({
                        'company_name': lead.company_name,
                        'business_type': lead.get_industry_vertical_display() or "RCM Provider",
                        'location': loc,
                        'services': services_text,
                        'domain': lead.domain or "company.example",
                        'website': lead.website or f"https://{lead.domain}",
                        'careers_url': lead.careers_url,
                        'relevance': rel,
                        'status': status,
                        'already_tracked': True,
                        'lead_id': lead.id,
                        'priority_tier': lead.priority_tier,
                        'source': lead.source,
                        'snippet': lead.notes,
                        'city': lead.city,
                        'country': lead.country,
                        'industry_vertical': lead.industry_vertical,
                    })
            elif total_in_db == 0:
                # Fallback only when the entire database is completely empty
                table_records.extend(showcase_companies)

        # Pagination (10 items per page)
        paginator = Paginator(table_records, 10)
        try:
            page_obj = paginator.page(page_num)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)

        ctx['page_obj'] = page_obj
        ctx['results'] = page_obj.object_list
        ctx['paginator'] = paginator
        ctx['total_results_count'] = f"{paginator.count:,}"
        ctx['total_found'] = paginator.count

        # Top Categories for Insights Card (dynamically aggregated from live DB)
        cat_counts = (
            EmployerLead.objects.exclude(industry_vertical='')
            .values('industry_vertical')
            .annotate(c=Count('id'))
            .order_by('-c')[:4]
        )
        colors = ['#0f766e', '#14b8a6', '#10b981', '#2dd4bf']
        vertical_labels = dict(EmployerLead.IndustryVertical.choices)
        top_categories = []
        if total_in_db > 0 and cat_counts:
            for idx, item in enumerate(cat_counts):
                v_code = item['industry_vertical']
                v_label = vertical_labels.get(v_code, v_code.replace('_', ' ').title())
                short_label = (
                    'Medical Billing' if 'Billing' in v_label else
                    ('Medical Coding' if 'Coding' in v_label else
                     ('RCM Providers' if 'RCM' in v_label else
                      ('Healthcare BPO' if 'BPO' in v_label else v_label[:18])))
                )
                pct = max(1, round((item['c'] / total_in_db) * 100))
                top_categories.append({
                    'name': short_label,
                    'percentage': pct,
                    'color': colors[idx % len(colors)],
                })
        else:
            top_categories = [
                {'name': 'Medical Billing', 'percentage': 38, 'color': '#0f766e'},
                {'name': 'RCM Providers', 'percentage': 27, 'color': '#14b8a6'},
                {'name': 'Healthcare BPO', 'percentage': 19, 'color': '#10b981'},
                {'name': 'Coding Firms', 'percentage': 16, 'color': '#2dd4bf'},
            ]
        ctx['top_categories'] = top_categories

        # Geographic Coverage for Insights Card (dynamically aggregated from live DB)
        FLAG_MAP = {
            'United States': '🇺🇸', 'USA': '🇺🇸', 'US': '🇺🇸',
            'United Kingdom': '🇬🇧', 'UK': '🇬🇧',
            'Canada': '🇨🇦',
            'Australia': '🇦🇺',
            'United Arab Emirates': '🇦🇪', 'UAE': '🇦🇪',
            'Ghana': '🇬🇭', 'Nigeria': '🇳🇬', 'Kenya': '🇰🇪', 'South Africa': '🇿🇦',
            'India': '🇮🇳', 'Germany': '🇩🇪', 'France': '🇫🇷', 'Philippines': '🇵🇭',
        }
        geo_counts = (
            EmployerLead.objects.exclude(country='')
            .exclude(country__isnull=True)
            .values('country')
            .annotate(c=Count('id'))
            .order_by('-c')[:4]
        )
        geographic_coverage = []
        if total_in_db > 0 and geo_counts:
            for item in geo_counts:
                c_name = item['country']
                flag = FLAG_MAP.get(c_name, '🌐')
                geographic_coverage.append({
                    'country': c_name,
                    'flag': flag,
                    'count': f"{item['c']:,}"
                })
        else:
            geographic_coverage = [
                {'country': 'United States', 'flag': '🇺🇸', 'count': '1,204'},
                {'country': 'United Kingdom', 'flag': '🇬🇧', 'count': '386'},
                {'country': 'Canada', 'flag': '🇨🇦', 'count': '244'},
                {'country': 'Australia', 'flag': '🇦🇺', 'count': '198'},
            ]
        ctx['geographic_coverage'] = geographic_coverage

        return ctx


class DiscoveryLeadImportView(StaffRequiredMixin, View):
    """
    Imports single or bulk discovered company records into the GrowthOS database.
    """
    def post(self, request):
        mode = request.POST.get('mode', 'single')

        if mode == 'bulk':
            # Import all matching results from query
            query = request.POST.get('q', '').strip()
            country = request.POST.get('country', 'United States').strip()
            source = request.POST.get('source', 'ALL').strip()

            if not query:
                messages.error(request, "Search query is required for bulk ingestion.")
                return redirect('growth_os:discovery_hub')

            source_filter = None if source == 'ALL' else source
            raw_results = search_all_connectors(
                query=query,
                location=country,
                limit_per_source=8,
                source_key=source_filter
            )
            created_count = 0
            for r in raw_results:
                try:
                    _, created = import_discovered_lead(r, assigned_staff=request.user)
                    if created:
                        created_count += 1
                except Exception:
                    pass

            messages.success(request, f"Bulk discovery imported {created_count} new employer leads across selected channels!")
            return redirect(f"{reverse('growth_os:discovery_hub')}?q={query}&country={country}&source={source}")
        else:
            # Single company import
            data = {
                'company_name': request.POST.get('company_name', '').strip(),
                'domain': request.POST.get('domain', '').strip(),
                'website': request.POST.get('website', '').strip(),
                'careers_url': request.POST.get('careers_url', '').strip(),
                'city': request.POST.get('city', '').strip(),
                'country': request.POST.get('country', 'United States').strip(),
                'industry_vertical': request.POST.get('industry_vertical', EmployerLead.IndustryVertical.RCM_SERVICES),
                'snippet': request.POST.get('snippet', ''),
                'source': request.POST.get('source', EmployerLead.Source.GOOGLE_SEARCH)
            }
            try:
                lead, created = import_discovered_lead(data, assigned_staff=request.user)
                if created:
                    messages.success(request, f"'{lead.company_name}' successfully added to GrowthOS!")
                else:
                    messages.info(request, f"'{lead.company_name}' was already tracked in GrowthOS.")
                return redirect('growth_os:lead_detail', pk=lead.id)
            except Exception as e:
                messages.error(request, f"Failed to import organization: {e}")
                return redirect('growth_os:discovery_hub')


class EmployerLeadCSVImportView(StaffRequiredMixin, View):
    """
    Interface for uploading and parsing CSV spreadsheets of healthcare employers.
    """
    template_name = 'growth_os/lead_import_csv.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, "Please choose a valid CSV file to upload.")
            return render(request, self.template_name)

        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Uploaded file must have a .csv extension.")
            return render(request, self.template_name)

        results = import_leads_from_csv(csv_file, assigned_staff=request.user)
        messages.success(
            request,
            f"CSV Import Finished! {results['created']} new leads created, {results['updated']} updated, {results['skipped']} skipped."
        )

        return render(request, self.template_name, {'results': results})


class DownloadSampleCSVView(StaffRequiredMixin, View):
    """
    Generates a pre-formatted sample CSV template for bulk employer lead uploads.
    """
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="kodafriq_growth_os_leads_template.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'company_name', 'domain', 'website', 'careers_url', 'city', 'country',
            'industry_vertical', 'company_size', 'contact_name', 'contact_email',
            'contact_title', 'notes'
        ])
        writer.writerow([
            'Apex Revenue Solutions', 'apexrev.com', 'https://apexrev.com',
            'https://apexrev.com/careers', 'Dallas, TX', 'United States',
            'RCM_SERVICES', '51_200', 'Sarah Connor', 's.connor@apexrev.com',
            'VP of Revenue Cycle', 'Urgent need for 5 remote inpatient medical coders'
        ])
        writer.writerow([
            'CarePoint Medical Billing', 'carepointbilling.com', 'https://carepointbilling.com',
            'https://carepointbilling.com/jobs', 'Miami, FL', 'United States',
            'MEDICAL_BILLING', '11_50', 'David Miller', 'dmiller@carepointbilling.com',
            'Head of Talent', 'Seeking denial resolution and accounts receivable specialists'
        ])
        return response


# ==============================================================================
# PHASE 3: OUTREACH GENERATOR, QUEUE, AND PUBLIC SHORTLIST VIEWS
# ==============================================================================

class OutreachQueueView(StaffRequiredMixin, ListView):
    """
    Staff review & approval queue for AI-generated outreach copy.
    Enforces human-in-the-loop review before any email or LinkedIn message is dispatched.
    """
    model = OutreachMessage
    template_name = 'growth_os/outreach_queue.html'
    context_object_name = 'outreaches'
    paginate_by = 20

    def get_queryset(self):
        qs = OutreachMessage.objects.select_related('lead', 'contact').order_by('-created_at')

        # Status filter
        status_filter = self.request.GET.get('status', 'DRAFT_PENDING_APPROVAL').upper()
        if status_filter and status_filter != 'ALL':
            qs = qs.filter(status=status_filter)

        # Channel filter
        channel_filter = self.request.GET.get('channel', '').upper()
        if channel_filter and channel_filter != 'ALL':
            qs = qs.filter(channel=channel_filter)

        # Search query
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(lead__company_name__icontains=q) |
                Q(contact__full_name__icontains=q) |
                Q(subject__icontains=q)
            )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_count'] = OutreachMessage.objects.filter(status=OutreachMessage.Status.DRAFT_PENDING_APPROVAL).count()
        context['sent_count'] = OutreachMessage.objects.filter(status=OutreachMessage.Status.SENT).count()
        context['replied_count'] = OutreachMessage.objects.filter(status=OutreachMessage.Status.REPLIED).count()
        context['rejected_count'] = OutreachMessage.objects.filter(status=OutreachMessage.Status.REJECTED).count()
        context['all_count'] = OutreachMessage.objects.count()

        context['current_status'] = self.request.GET.get('status', 'DRAFT_PENDING_APPROVAL').upper()
        context['current_channel'] = self.request.GET.get('channel', '').upper()
        context['search_query'] = self.request.GET.get('q', '')
        return context


class OutreachGenerateView(StaffRequiredMixin, View):
    """
    Triggers AI-powered pitch generation for an EmployerLead.
    """
    def post(self, request, lead_id):
        lead = get_object_or_404(EmployerLead, id=lead_id)
        form = OutreachGenerateForm(request.POST)

        if form.is_valid():
            channel = form.cleaned_data['channel']
            sequence_step = int(form.cleaned_data['sequence_step'])
            contact_id = form.cleaned_data.get('contact_id')

            contact = None
            if contact_id:
                contact = lead.contacts.filter(id=contact_id).first()
            if not contact:
                contact = lead.contacts.filter(is_primary=True).first() or lead.contacts.first()

            outreach = generate_outreach_pitch(
                lead=lead,
                contact=contact,
                channel=channel,
                sequence_step=sequence_step,
                request=request
            )

            messages.success(
                request,
                f"Generated Step {sequence_step} {channel.upper()} pitch for {lead.company_name} and queued for approval."
            )
        else:
            messages.error(request, "Failed to generate outreach pitch: invalid parameters.")

        next_url = request.POST.get('next') or reverse('growth_os:lead_detail', kwargs={'pk': lead.id})
        return redirect(next_url)


class OutreachApproveSendView(StaffRequiredMixin, View):
    """
    Staff action to approve and mark an outreach message as dispatched.
    Advances pipeline stage to STAGE_5_OUTREACH_SENT and logs CRM activity.
    """
    def post(self, request, pk):
        outreach = get_object_or_404(OutreachMessage, id=pk)

        # Allow inline copy edits during approval
        subject = request.POST.get('subject', '').strip()
        body_text = request.POST.get('body_text', '').strip()
        if subject:
            outreach.subject = subject
        if body_text:
            outreach.body_text = body_text

        outreach.status = OutreachMessage.Status.SENT
        outreach.sent_at = timezone.now()
        outreach.save()

        # Advance CRM Opportunity stage if early stage
        lead = outreach.lead
        opp, _ = CRMOpportunity.objects.get_or_create(lead=lead)
        early_stages = [
            CRMOpportunity.Stage.STAGE_1_DISCOVERED,
            CRMOpportunity.Stage.STAGE_2_QUALIFIED,
            CRMOpportunity.Stage.STAGE_3_HIRING_SIGNAL,
            CRMOpportunity.Stage.STAGE_4_CONTACT_IDENTIFIED,
        ]
        if opp.stage in early_stages:
            opp.stage = CRMOpportunity.Stage.STAGE_5_OUTREACH_SENT
            opp.save(update_fields=['stage', 'updated_at'])

        # Log CRM Activity
        recipient = outreach.contact.full_name if outreach.contact else lead.company_name
        CRMActivity.objects.create(
            lead=lead,
            activity_type=CRMActivity.ActivityType.EMAIL_SENT,
            performed_by=request.user,
            summary=f"Step {outreach.sequence_step} Outreach Approved & Dispatched",
            details=f"Channel: {outreach.get_channel_display()}\nRecipient: {recipient}\nSubject: {outreach.subject}\n\nContent:\n{outreach.body_text[:400]}..."
        )

        messages.success(request, f"Outreach message to {lead.company_name} approved and recorded as sent.")
        next_url = request.POST.get('next') or reverse('growth_os:outreach_queue')
        return redirect(next_url)


class OutreachRejectView(StaffRequiredMixin, View):
    """
    Rejects or archives a draft outreach message.
    """
    def post(self, request, pk):
        outreach = get_object_or_404(OutreachMessage, id=pk)
        outreach.status = OutreachMessage.Status.REJECTED
        outreach.save(update_fields=['status'])

        messages.info(request, f"Draft pitch for {outreach.lead.company_name} rejected.")
        next_url = request.POST.get('next') or reverse('growth_os:outreach_queue')
        return redirect(next_url)


class OutreachRecordReplyView(StaffRequiredMixin, View):
    """
    Records an inbound response from a prospect, updating outreach status and CRM stage.
    """
    def post(self, request, pk):
        outreach = get_object_or_404(OutreachMessage, id=pk)
        sentiment = request.POST.get('sentiment', 'positive')
        notes = request.POST.get('reply_notes', '').strip()

        outreach.status = OutreachMessage.Status.REPLIED
        outreach.reply_notes = notes
        outreach.save(update_fields=['status', 'reply_notes'])

        lead = outreach.lead
        opp, _ = CRMOpportunity.objects.get_or_create(lead=lead)
        if sentiment in ['positive', 'meeting_booked']:
            opp.stage = (
                CRMOpportunity.Stage.STAGE_7_MEETING_SCHEDULED
                if sentiment == 'meeting_booked'
                else CRMOpportunity.Stage.STAGE_6_REPLY_RECEIVED
            )
            opp.save(update_fields=['stage', 'updated_at'])

        CRMActivity.objects.create(
            lead=lead,
            activity_type=CRMActivity.ActivityType.NOTE,
            performed_by=request.user,
            summary=f"Inbound Reply Recorded ({sentiment.title()})",
            details=f"Reply to Step {outreach.sequence_step} outreach via {outreach.get_channel_display()}.\nNotes: {notes}"
        )

        messages.success(request, f"Reply recorded for {lead.company_name}. Lead advanced in CRM.")
        next_url = request.POST.get('next') or reverse('growth_os:lead_detail', kwargs={'pk': lead.id})
        return redirect(next_url)


class PublicCandidateShortlistView(DetailView):
    """
    Employer-facing, high-conversion candidate showcase dossier.
    Publicly accessible via secure UUID link without authentication so prospective
    employers clicking outreach links can inspect pre-screened talent immediately.
    Candidate personally identifiable information (PII) is anonymized.
    """
    model = EmployerLead
    template_name = 'growth_os/shortlist_public.html'
    context_object_name = 'lead'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lead = self.object

        # Retrieve matched candidates (generate if not yet present)
        matches = list(
            TalentReverseMatch.objects.filter(lead=lead)
            .select_related('candidate', 'candidate__user')
            .order_by('-is_shortlisted', '-match_score')
        )

        if not matches:
            compute_lead_reverse_matches(lead)
            matches = list(
                TalentReverseMatch.objects.filter(lead=lead)
                .select_related('candidate', 'candidate__user')
                .order_by('-is_shortlisted', '-match_score')
            )

        context['matches'] = matches
        context['inquiry_form'] = PublicShortlistInquiryForm()
        context['active_vacancies'] = lead.vacancies.filter(is_active=True).order_by('-created_at')[:5]
        return context


class PublicShortlistInquireView(View):
    """
    Public endpoint for employers viewing the candidate shortlist to request
    interviews, discuss rates, or schedule a discovery call.
    """
    def post(self, request, pk):
        lead = get_object_or_404(EmployerLead, id=pk)
        form = PublicShortlistInquiryForm(request.POST)

        if form.is_valid():
            full_name = form.cleaned_data['full_name']
            work_email = form.cleaned_data['work_email']
            phone = form.cleaned_data.get('phone', '')
            requested_roles = form.cleaned_data.get('requested_roles', '')
            message_text = form.cleaned_data.get('message', '')

            # Create or update contact record
            contact, created = LeadContact.objects.get_or_create(
                lead=lead,
                email=work_email,
                defaults={
                    'full_name': full_name,
                    'phone': phone,
                    'job_title': 'Hiring Contact (Self-Submitted)',
                    'is_primary': not lead.contacts.filter(is_primary=True).exists(),
                }
            )

            # Advance CRM opportunity stage to STAGE_6_REPLY_RECEIVED
            opp, _ = CRMOpportunity.objects.get_or_create(lead=lead)
            early_stages = [
                CRMOpportunity.Stage.STAGE_1_DISCOVERED,
                CRMOpportunity.Stage.STAGE_2_QUALIFIED,
                CRMOpportunity.Stage.STAGE_3_HIRING_SIGNAL,
                CRMOpportunity.Stage.STAGE_4_CONTACT_IDENTIFIED,
                CRMOpportunity.Stage.STAGE_5_OUTREACH_SENT,
            ]
            if opp.stage in early_stages:
                opp.stage = CRMOpportunity.Stage.STAGE_6_REPLY_RECEIVED
                opp.save(update_fields=['stage', 'updated_at'])

            # Log CRM Activity
            CRMActivity.objects.create(
                lead=lead,
                activity_type=CRMActivity.ActivityType.NOTE,
                summary=f"Shortlist Interview Request: {full_name}",
                details=(
                    f"Prospect submitted an interview request via public shortlist.\n"
                    f"Name: {full_name}\n"
                    f"Email: {work_email}\n"
                    f"Phone: {phone or 'Not provided'}\n"
                    f"Requested Roles: {requested_roles or 'General'}\n"
                    f"Message: {message_text or 'None'}"
                )
            )

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
                return JsonResponse({
                    'success': True,
                    'message': 'Thank you! Your interview request has been received. A Kodafriq Talent Director will contact you within 4 business hours.'
                })

            messages.success(
                request,
                "Thank you! Your request has been received. A Kodafriq Talent Director will contact you shortly with candidate availability."
            )
            return redirect(reverse('growth_os:public_shortlist', kwargs={'pk': lead.id}) + '?submitted=1')

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        messages.error(request, "Please fill in all required fields to submit your request.")
        return redirect('growth_os:public_shortlist', pk=lead.id)


# ==============================================================================
# PHASE 4: Interactive Kanban Pipeline, Conversion Engine & KPI Analytics
# ==============================================================================

class PipelineKanbanView(StaffRequiredMixin, TemplateView):
    """
    10-Stage Interactive Drag-and-Drop Sales Pipeline Kanban Board.
    Visualizes deal flow, monthly pipeline values, and stage distributions.
    """
    template_name = 'growth_os/pipeline_kanban.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sector = self.request.GET.get('sector', '').strip()
        priority = self.request.GET.get('priority', '').strip()
        staff = self.request.GET.get('staff', '').strip()
        search_q = self.request.GET.get('q', '').strip()

        board_data = get_kanban_board_data(
            sector=sector or None,
            priority=priority or None,
            staff=staff or None,
            search_query=search_q or None
        )

        ctx.update(board_data)
        ctx['sectors'] = EmployerLead.IndustryVertical.choices
        ctx['priorities'] = CRMOpportunity.Priority.choices
        ctx['staff_list'] = User.objects.filter(role__in=[User.Role.STAFF, User.Role.ADMIN]).order_by('first_name', 'username')
        ctx['current_sector'] = sector
        ctx['current_priority'] = priority
        ctx['current_staff'] = staff
        ctx['current_q'] = search_q
        ctx['quick_activity_form'] = QuickActivityForm()
        return ctx


class PipelineUpdateStageAjaxView(StaffRequiredMixin, View):
    """
    AJAX endpoint invoked by Kanban drag-and-drop to transition an opportunity's stage.
    Synchronizes parent lead status, win probability, and logs immutable audit activities.
    """
    def post(self, request):
        opp_id = request.POST.get('opportunity_id') or request.POST.get('opp_id')
        new_stage = request.POST.get('stage')
        notes = request.POST.get('notes', '').strip()

        # Handle raw JSON payload if sent via fetch
        if not opp_id and request.body:
            try:
                body_data = json.loads(request.body.decode('utf-8'))
                opp_id = body_data.get('opportunity_id') or body_data.get('opp_id')
                new_stage = body_data.get('stage')
                notes = body_data.get('notes', '').strip()
            except Exception:
                pass

        if not opp_id or not new_stage:
            return JsonResponse({'success': False, 'error': 'Opportunity ID and Stage are required.'}, status=400)

        opp = get_object_or_404(CRMOpportunity, id=opp_id)
        if new_stage not in CRMOpportunity.Stage.values:
            return JsonResponse({'success': False, 'error': f"Invalid stage: '{new_stage}'"}, status=400)

        try:
            transition_opportunity_stage(opp, new_stage, performed_by=request.user, notes=notes)
            return JsonResponse({
                'success': True,
                'opportunity_id': str(opp.id),
                'company_name': opp.lead.company_name,
                'new_stage': opp.stage,
                'new_stage_display': opp.get_stage_display(),
                'win_probability': opp.win_probability_percent,
                'is_won': opp.stage == CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON,
                'is_lost': opp.stage == CRMOpportunity.Stage.CLOSED_LOST,
                'lead_status': opp.lead.get_status_display(),
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class LeadConvertView(StaffRequiredMixin, View):
    """
    1-Click Conversion Controller:
    Converts EmployerLead into an active Kodafriq EmployerProfile, provisions initial Contract,
    and advances opportunity to Stage 10 Placement Won.
    """
    def _build_candidate_choices(self, lead):
        matches = lead.talent_matches.select_related('candidate', 'candidate__user').all()[:15]
        choices = [('', '-- Select candidate for contract (optional) --')]
        for m in matches:
            cand = m.candidate
            name = cand.full_name or cand.user.username
            headline = f" ({cand.headline})" if cand.headline else ""
            choices.append((str(cand.id), f"{name}{headline} - Match: {m.match_score}%"))
        
        # If no specific matches, offer employer-ready candidate pool
        if len(choices) == 1:
            pool = CandidateProfile.objects.select_related('user').filter(is_employer_ready=True)[:15]
            if not pool:
                pool = CandidateProfile.objects.select_related('user').all()[:15]
            for cand in pool:
                name = cand.full_name or cand.user.username
                headline = f" ({cand.headline})" if cand.headline else ""
                choices.append((str(cand.id), f"{name}{headline}"))
        return choices, matches

    def get(self, request, pk):
        lead = get_object_or_404(EmployerLead, id=pk)

        if lead.converted_employer_profile:
            messages.info(request, f"'{lead.company_name}' has already been converted into an official Kodafriq Employer.")
            return redirect('growth_os:lead_detail', pk=lead.id)

        primary_contact = lead.contacts.filter(is_primary=True).first() or lead.contacts.first()
        vac = lead.vacancies.filter(is_active=True).first()

        email = primary_contact.email if primary_contact and primary_contact.email else f"contact@{lead.domain or 'employer.com'}"
        initial = {
            'email': email,
            'company_name': lead.company_name,
            'contact_person_name': primary_contact.full_name if primary_contact else '',
            'contact_person_title': primary_contact.job_title if primary_contact else '',
            'phone': primary_contact.phone if primary_contact else '',
            'website': lead.website,
            'country': lead.country,
            'city': lead.city,
            'industry': lead.get_industry_vertical_display(),
            'create_contract': True,
            'contract_title': f"{lead.company_name} - {vac.job_title}" if vac else f"{lead.company_name} - Operations Specialist",
            'contract_type': Contract.ContractType.HOURLY,
            'rate_per_hour': Decimal('25.00'),
            'weekly_hour_limit': 40,
            'scope_of_work': vac.raw_description[:300] if vac and vac.raw_description else f"Healthcare and operational support services for {lead.company_name}.",
        }

        candidate_choices, matches = self._build_candidate_choices(lead)
        form = LeadConversionForm(initial=initial, candidate_choices=candidate_choices)

        return render(request, 'growth_os/lead_convert.html', {
            'lead': lead,
            'form': form,
            'matches': matches,
            'primary_contact': primary_contact,
        })

    def post(self, request, pk):
        lead = get_object_or_404(EmployerLead, id=pk)

        if lead.converted_employer_profile:
            messages.info(request, f"'{lead.company_name}' has already been converted.")
            return redirect('growth_os:lead_detail', pk=lead.id)

        candidate_choices, matches = self._build_candidate_choices(lead)
        form = LeadConversionForm(request.POST, candidate_choices=candidate_choices)

        if form.is_valid():
            cd = form.cleaned_data
            user_data = {
                'email': cd.get('email'),
                'company_name': cd.get('company_name'),
                'website': cd.get('website'),
                'country': cd.get('country'),
                'city': cd.get('city'),
                'industry': cd.get('industry'),
                'contact_person_title': cd.get('contact_person_title'),
                'contact_phone': cd.get('phone'),
            }
            if cd.get('contact_person_name'):
                parts = cd.get('contact_person_name').split()
                user_data['first_name'] = parts[0]
                user_data['last_name'] = ' '.join(parts[1:]) if len(parts) > 1 else ''

            contract_data = None
            if cd.get('create_contract') and cd.get('candidate_id'):
                contract_data = {
                    'candidate_id': cd.get('candidate_id'),
                    'title': cd.get('contract_title') or f"{lead.company_name} - Placement",
                    'contract_type': cd.get('contract_type'),
                    'rate_per_hour': cd.get('rate_per_hour'),
                    'total_milestone_amount': cd.get('total_milestone_amount'),
                    'weekly_hour_limit': cd.get('weekly_hour_limit'),
                    'scope_of_work': cd.get('scope_of_work'),
                }

            result = convert_lead_to_employer(
                lead=lead,
                user_data=user_data,
                contract_data=contract_data,
                performed_by=request.user
            )

            contract_msg = f" Contract '{result['contract'].contract_ref}' drafted successfully." if result.get('contract') else ""
            messages.success(
                request,
                f"🎉 Success! '{lead.company_name}' is officially converted to a Kodafriq Employer Profile! "
                f"Employer Account created for {result['user'].email}. Pipeline stage advanced to 10. Placement Won.{contract_msg}"
            )
            return redirect('growth_os:lead_detail', pk=lead.id)

        messages.error(request, "Failed to convert lead. Please correct highlighted errors.")
        return render(request, 'growth_os/lead_convert.html', {
            'lead': lead,
            'form': form,
            'matches': matches,
        })


class QuickActivityLogView(StaffRequiredMixin, View):
    """
    Quick activity and follow-up logging view accessible from the Kanban board or Lead Dossier.
    """
    def post(self, request, lead_id):
        lead = get_object_or_404(EmployerLead, id=lead_id)
        form = QuickActivityForm(request.POST)

        if form.is_valid():
            activity = form.save(commit=False)
            activity.lead = lead
            activity.performed_by = request.user
            activity.save()

            follow_up = form.cleaned_data.get('next_follow_up_date')
            if follow_up:
                opp, _ = CRMOpportunity.objects.get_or_create(lead=lead)
                opp.next_follow_up_date = follow_up
                opp.save(update_fields=['next_follow_up_date', 'updated_at'])

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
                return JsonResponse({
                    'success': True,
                    'message': 'Activity recorded successfully.',
                    'summary': activity.summary,
                    'created_at': activity.created_at.strftime('%b %d, %Y %H:%M')
                })

            messages.success(request, f"Activity recorded for {lead.company_name}.")
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
            messages.error(request, "Unable to record activity. Please check required fields.")

        return redirect(request.META.get('HTTP_REFERER') or reverse('growth_os:lead_detail', kwargs={'pk': lead.id}))


class GrowthAutomationDashboardView(StaffRequiredMixin, TemplateView):
    """
    Phase 5 Automation Command Center:
    Displays background jobs, system health, execution audit logs, and allows staff
    to manually trigger vacancy polling, hiring intent degradation, dormant lead archiving,
    or candidate availability synchronization.
    """
    template_name = 'growth_os/automation_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['logs'] = GrowthAutomationLog.objects.all().select_related('executed_by').order_by('-executed_at')[:30]

        ctx['total_runs'] = GrowthAutomationLog.objects.count()
        ctx['successful_runs'] = GrowthAutomationLog.objects.filter(status=GrowthAutomationLog.Status.SUCCESS).count()
        ctx['items_evaluated_total'] = GrowthAutomationLog.objects.aggregate(total=Sum('items_evaluated'))['total'] or 0
        ctx['items_updated_total'] = GrowthAutomationLog.objects.aggregate(total=Sum('items_updated'))['total'] or 0
        ctx['last_run'] = GrowthAutomationLog.objects.order_by('-executed_at').first()

        ctx['total_leads_count'] = EmployerLead.objects.count()
        ctx['archived_leads_count'] = EmployerLead.objects.filter(status=EmployerLead.Status.ARCHIVED).count()
        ctx['active_vacancies_count'] = HiringSignal.objects.filter(is_active=True).count()
        ctx['persistent_vacancies_count'] = HiringSignal.objects.filter(is_active=True, is_persistent=True).count()

        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')

        if action == 'poll_vacancies':
            crawl = request.POST.get('crawl') == '1'
            res = poll_and_age_vacancies(crawl=crawl, performed_by=request.user)
            messages.success(request, f"Vacancy Polling completed: {res['persistent_count']} marked persistent, {res['closed_count']} expired.")

        elif action == 'decay_intent':
            res = apply_hiring_intent_decay(performed_by=request.user)
            messages.success(request, f"Hiring Intent Degradation completed: {res['decayed_count']} stale leads decayed.")

        elif action == 'archive_dormant':
            res = archive_dormant_leads(performed_by=request.user)
            messages.success(request, f"Housekeeping completed: {res['archived_count']} dormant leads archived.")

        elif action == 'sync_availability':
            candidates = CandidateProfile.objects.all()
            total_adj = 0
            for cand in candidates:
                res_cand = sync_candidate_availability_to_growth(cand, performed_by=request.user)
                total_adj += res_cand.get('updated_matches', 0)
            messages.success(request, f"Candidate pool synchronized: {total_adj} shortlist matches updated.")

        elif action == 'run_all':
            res_v = poll_and_age_vacancies(crawl=False, performed_by=request.user)
            res_d = apply_hiring_intent_decay(performed_by=request.user)
            res_a = archive_dormant_leads(performed_by=request.user)
            messages.success(request, (
                f"Full Ecosystem Maintenance completed! Vacancies aged: {res_v['persistent_count']} persistent. "
                f"Leads decayed: {res_d['decayed_count']}. Archived: {res_a['archived_count']}."
            ))

        else:
            messages.warning(request, "Unrecognized automation action requested.")

        return redirect('growth_os:automation_dashboard')


class GrowthExecutiveDigestReportView(StaffRequiredMixin, TemplateView):
    """
    Phase 5 Executive Commercial & BD Performance Report:
    Renders 7-day acquisition KPIs, multi-sector breakdown, persistent hiring signals,
    pipeline velocity, and provides one-click executive email dispatch and printable view.
    """
    template_name = 'growth_os/reports_digest.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        digest = generate_weekly_bd_digest(performed_by=self.request.user)
        ctx['digest'] = digest
        ctx['recent_activities'] = CRMActivity.objects.select_related('lead', 'performed_by').order_by('-created_at')[:10]
        ctx['high_intent_leads'] = EmployerLead.objects.filter(
            status__in=[EmployerLead.Status.LEAD, EmployerLead.Status.QUALIFIED, EmployerLead.Status.IN_PIPELINE]
        ).order_by('-hiring_intent_score')[:8]
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')

        if action == 'send_email':
            custom_email = request.POST.get('email', '').strip()
            recipients = [custom_email] if custom_email else None
            res = send_weekly_bd_digest_email(recipients=recipients, performed_by=request.user)

            if res.get('success'):
                messages.success(request, f"Executive BD Digest successfully sent to: {', '.join(res['recipients'])}.")
            else:
                messages.error(request, f"Failed to send digest email: {res.get('error')}")

        return redirect('growth_os:reports_digest')



