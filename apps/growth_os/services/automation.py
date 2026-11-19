"""
GrowthOS Autonomous Continuous Acquisition & Ecosystem Automation Service
Handles:
- Automated recurring vacancy polling, ageing and closure
- Hiring intent score degradation / decay for stale leads
- Dynamic candidate availability sync across reverse matches
- Dormant / inactive lead archiving
- Automated Weekly BD Executive Digest generation and email delivery
"""
import logging
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q, Avg

from apps.growth_os.models import (
    EmployerLead, LeadContact, HiringSignal, TalentReverseMatch,
    OutreachMessage, CRMOpportunity, CRMActivity, GrowthAutomationLog
)
from apps.growth_os.services.intent import calculate_lead_intent_score
from apps.growth_os.services.matcher import compute_lead_reverse_matches
from apps.growth_os.services.scraper import inspect_lead_career_page
from apps.accounts.models import CandidateProfile
from apps.contracts.models import Contract

logger = logging.getLogger(__name__)
User = get_user_model()


def poll_and_age_vacancies(crawl=False, performed_by=None):
    """
    Evaluates all active vacancies across employer leads:
    - Increments days_open based on elapsed time since date_detected
    - Marks persistent = True if days_open >= 30
    - Closes vacancies advertised for >90 days without live confirmation
    - Optionally crawls careers pages for live active leads
    - Recalculates Hiring Intent Scores for affected leads
    """
    today = timezone.localdate()
    active_vacancies = HiringSignal.objects.filter(is_active=True).select_related('lead')
    total_evaluated = active_vacancies.count()
    updated_count = 0
    closed_count = 0
    affected_leads = set()

    for vac in active_vacancies:
        modified = False
        days_elapsed = (today - vac.date_detected).days
        current_days_open = max(1, days_elapsed + 1)

        if vac.days_open != current_days_open:
            vac.days_open = current_days_open
            modified = True

        if vac.days_open >= 30 and not vac.is_persistent:
            vac.is_persistent = True
            modified = True

        # Close stale vacancies that have exceeded 90 days without live refresh
        if vac.days_open > 90:
            vac.is_active = False
            closed_count += 1
            modified = True

        if modified:
            vac.save(update_fields=['days_open', 'is_persistent', 'is_active'])
            affected_leads.add(vac.lead)
            updated_count += 1

    # Optional live web crawl
    crawled_count = 0
    if crawl:
        leads_to_crawl = EmployerLead.objects.filter(
            status__in=[EmployerLead.Status.LEAD, EmployerLead.Status.QUALIFIED, EmployerLead.Status.IN_PIPELINE]
        ).exclude(careers_url='').exclude(careers_url__isnull=True)[:25]

        for lead in leads_to_crawl:
            try:
                res = inspect_lead_career_page(lead)
                if res.get('success'):
                    crawled_count += 1
                    affected_leads.add(lead)
            except Exception as e:
                logger.warning(f"Error crawling {lead.company_name}: {e}")

    # Recalculate Intent and Reverse Matches for all affected leads
    for lead in affected_leads:
        calculate_lead_intent_score(lead)
        compute_lead_reverse_matches(lead)

    summary = f"Evaluated {total_evaluated} vacancies: {updated_count} aged, {closed_count} expired/closed, {crawled_count} careers crawled."
    log = GrowthAutomationLog.objects.create(
        task_type=GrowthAutomationLog.TaskType.VACANCY_POLL,
        executed_by=performed_by,
        status=GrowthAutomationLog.Status.SUCCESS,
        items_evaluated=total_evaluated,
        items_updated=updated_count + closed_count,
        summary=summary,
        details_json={
            'total_evaluated': total_evaluated,
            'aged_count': updated_count,
            'closed_count': closed_count,
            'crawled_count': crawled_count,
            'affected_leads_count': len(affected_leads)
        }
    )

    return {
        'success': True,
        'log_id': str(log.id),
        'total_evaluated': total_evaluated,
        'updated_count': updated_count,
        'persistent_count': updated_count,
        'closed_count': closed_count,
        'affected_leads_count': len(affected_leads),
        'summary': summary
    }


def apply_hiring_intent_decay(days_stale: int = 30, performed_by=None):
    """
    Applies time-decay degradation to Hiring Intent Scores for leads with no recent active hiring signals.
    - If a lead has zero active vacancies and was last updated >30 days ago, decays intent score by 10% (minimum 10 pts if website exists, else 0).
    - Prevents stale leads from permanently clogging Tier 1 and Tier 2 priority quadrants.
    """
    cutoff_date = timezone.now() - timedelta(days=days_stale)
    candidates = EmployerLead.objects.filter(
        status__in=[EmployerLead.Status.LEAD, EmployerLead.Status.QUALIFIED, EmployerLead.Status.IN_PIPELINE],
        hiring_intent_score__gt=10,
        updated_at__lt=cutoff_date
    ).annotate(
        active_vac_count=Count('vacancies', filter=Q(vacancies__is_active=True))
    ).filter(active_vac_count=0)

    total_evaluated = candidates.count()
    decayed_count = 0

    for lead in candidates:
        old_score = lead.hiring_intent_score
        # 10% or minimum 5-point degradation
        reduction = max(5, int(old_score * 0.10))
        floor = 10 if lead.website else 0
        new_score = max(floor, old_score - reduction)

        if new_score != old_score:
            lead.hiring_intent_score = new_score
            lead.save(update_fields=['hiring_intent_score', 'updated_at'])
            decayed_count += 1

    summary = f"Evaluated {total_evaluated} stale leads: degraded intent scores for {decayed_count} leads."
    log = GrowthAutomationLog.objects.create(
        task_type=GrowthAutomationLog.TaskType.INTENT_DECAY,
        executed_by=performed_by,
        status=GrowthAutomationLog.Status.SUCCESS,
        items_evaluated=total_evaluated,
        items_updated=decayed_count,
        summary=summary,
        details_json={
            'total_evaluated': total_evaluated,
            'decayed_count': decayed_count,
            'cutoff_days': 30
        }
    )

    return {
        'success': True,
        'log_id': str(log.id),
        'total_evaluated': total_evaluated,
        'decayed_count': decayed_count,
        'summary': summary
    }


def archive_dormant_leads(days_threshold=90, performed_by=None):
    """
    Automatically archives inactive prospective leads:
    - Created >90 days ago in LEAD or QUALIFIED status
    - Zero active vacancies
    - Zero CRM activities logged in the last 60 days
    - Intent score < 25
    Sets status to ARCHIVED and logs an immutable CRM audit record.
    """
    cutoff_created = timezone.now() - timedelta(days=days_threshold)
    cutoff_activity = timezone.now() - timedelta(days=60)

    dormant_candidates = EmployerLead.objects.filter(
        status__in=[EmployerLead.Status.LEAD, EmployerLead.Status.QUALIFIED],
        created_at__lt=cutoff_created,
        hiring_intent_score__lt=25
    ).annotate(
        active_vac_count=Count('vacancies', filter=Q(vacancies__is_active=True)),
        recent_act_count=Count('activities', filter=Q(activities__created_at__gte=cutoff_activity))
    ).filter(active_vac_count=0, recent_act_count=0)

    total_evaluated = dormant_candidates.count()
    archived_count = 0

    for lead in dormant_candidates:
        lead.status = EmployerLead.Status.ARCHIVED
        lead.save(update_fields=['status', 'updated_at'])

        CRMActivity.objects.create(
            lead=lead,
            activity_type=CRMActivity.ActivityType.NOTE,
            summary="Automated Housekeeping: Lead Archived",
            details=f"Lead auto-archived after {days_threshold}+ days of dormancy, zero open vacancies, and low intent score ({lead.hiring_intent_score}%).",
            performed_by=performed_by
        )
        archived_count += 1

    summary = f"Housekeeping evaluated {total_evaluated} dormant leads: archived {archived_count} records."
    log = GrowthAutomationLog.objects.create(
        task_type=GrowthAutomationLog.TaskType.DORMANT_ARCHIVE,
        executed_by=performed_by,
        status=GrowthAutomationLog.Status.SUCCESS,
        items_evaluated=total_evaluated,
        items_updated=archived_count,
        summary=summary,
        details_json={
            'total_evaluated': total_evaluated,
            'archived_count': archived_count,
            'days_threshold': days_threshold
        }
    )

    return {
        'success': True,
        'log_id': str(log.id),
        'total_evaluated': total_evaluated,
        'archived_count': archived_count,
        'summary': summary
    }


def sync_candidate_availability_to_growth(candidate_profile, performed_by=None):
    """
    Synchronizes candidate status changes with GrowthOS TalentReverseMatches:
    - If a candidate is NOT_LOOKING or on an ACTIVE full-time contract:
      de-shortlists matches and re-evaluates lead talent fit scores.
    - If a candidate becomes IMMEDIATELY available or receives certification:
      recalculates reverse matches across relevant open vacancies.
    """
    is_unavailable = (
        candidate_profile.availability_status == CandidateProfile.Availability.NOT_LOOKING or
        Contract.objects.filter(candidate=candidate_profile, status=Contract.Status.ACTIVE).exists()
    )

    affected_matches = TalentReverseMatch.objects.filter(candidate=candidate_profile).select_related('lead')
    total_evaluated = affected_matches.count()
    updated_matches = 0
    affected_leads = set()

    if is_unavailable:
        for match in affected_matches:
            if match.is_shortlisted:
                match.is_shortlisted = False
                match.save(update_fields=['is_shortlisted'])
                updated_matches += 1
            affected_leads.add(match.lead)
    else:
        # Candidate is available -> scan relevant active leads for matches
        roles_filter = Q(status__in=[EmployerLead.Status.LEAD, EmployerLead.Status.QUALIFIED, EmployerLead.Status.IN_PIPELINE])
        active_leads = EmployerLead.objects.filter(roles_filter)[:50]
        for lead in active_leads:
            compute_lead_reverse_matches(lead)
            affected_leads.add(lead)

    # Recalculate talent fit score for affected employer leads
    for lead in affected_leads:
        lead.recalculate_intent_score()
        compute_lead_reverse_matches(lead)

    cand_name = candidate_profile.full_name or "Candidate"
    status_str = "Unavailable (Placed/Not Looking)" if is_unavailable else "Available"
    summary = f"Candidate '{cand_name}' synced as {status_str}: {updated_matches} matches adjusted across {len(affected_leads)} leads."

    log = GrowthAutomationLog.objects.create(
        task_type=GrowthAutomationLog.TaskType.AVAILABILITY_SYNC,
        executed_by=performed_by,
        status=GrowthAutomationLog.Status.SUCCESS,
        items_evaluated=total_evaluated,
        items_updated=updated_matches,
        summary=summary,
        details_json={
            'candidate_id': candidate_profile.id,
            'candidate_name': cand_name,
            'is_unavailable': is_unavailable,
            'availability_status': candidate_profile.availability_status,
            'affected_leads_count': len(affected_leads)
        }
    )

    return {
        'success': True,
        'log_id': str(log.id),
        'is_unavailable': is_unavailable,
        'updated_matches': updated_matches,
        'affected_leads_count': len(affected_leads),
        'summary': summary
    }


def generate_weekly_bd_digest(target_date=None, performed_by=None):
    """
    Computes a comprehensive commercial performance digest covering the last 7 days:
    - New leads catalogued by sector (Healthcare, IT/Software, Finance)
    - Vacancies detected and persistent hiring signals
    - High-intent leads promoted to Tier 1 Prime Targets
    - Outreach messages dispatched and reply sentiment rate
    - Pipeline transitions and Won Placements / MRR additions
    - Overdue follow-up reminders needing BD attention
    """
    end_date = target_date or timezone.now()
    start_date = end_date - timedelta(days=7)

    leads_window = EmployerLead.objects.filter(created_at__gte=start_date, created_at__lte=end_date)
    new_leads_count = leads_window.count()

    # Sector Breakdown
    sectors_data = {}
    for code, label in EmployerLead.IndustryVertical.choices:
        c = leads_window.filter(industry_vertical=code).count()
        if c > 0:
            sectors_data[label] = c

    # Vacancy signals detected in window
    vacancies_window = HiringSignal.objects.filter(created_at__gte=start_date, created_at__lte=end_date)
    new_vacancies_count = vacancies_window.count()
    persistent_signals_count = HiringSignal.objects.filter(is_active=True, is_persistent=True).count()

    # Tier 1 Leads
    tier_1_count = EmployerLead.objects.filter(
        hiring_intent_score__gte=60, talent_fit_score__gte=60
    ).count()

    # Outreach Metrics
    outreaches_window = OutreachMessage.objects.filter(sent_at__gte=start_date, sent_at__lte=end_date)
    outreach_sent_count = outreaches_window.count()
    replies_count = OutreachMessage.objects.filter(
        status=OutreachMessage.Status.REPLIED,
        created_at__gte=start_date
    ).count()
    response_rate = round((replies_count / outreach_sent_count * 100), 1) if outreach_sent_count > 0 else 0.0

    # Pipeline & Commercial Placements Won
    won_opps = CRMOpportunity.objects.filter(
        stage=CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON,
        updated_at__gte=start_date,
        updated_at__lte=end_date
    )
    deals_won_count = won_opps.count()
    won_mrr_added = float(won_opps.aggregate(total=Sum('estimated_monthly_deal_value'))['total'] or 0.0)

    # Total Pipeline Value
    active_pipeline_val = float(CRMOpportunity.objects.exclude(
        stage=CRMOpportunity.Stage.CLOSED_LOST
    ).aggregate(total=Sum('estimated_monthly_deal_value'))['total'] or 0.0)

    # Overdue Follow-ups
    today = timezone.localdate()
    overdue_followups_count = CRMOpportunity.objects.filter(
        next_follow_up_date__lt=today
    ).exclude(stage__in=[CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON, CRMOpportunity.Stage.CLOSED_LOST]).count()

    # Recent High-Priority Leads
    priority_leads = EmployerLead.objects.filter(
        hiring_intent_score__gte=60, talent_fit_score__gte=60
    ).order_by('-hiring_intent_score')[:5]

    digest_data = {
        'period_start': start_date.strftime('%B %d, %Y'),
        'period_end': end_date.strftime('%B %d, %Y'),
        'new_leads_count': new_leads_count,
        'sectors_breakdown': sectors_data,
        'new_vacancies_count': new_vacancies_count,
        'persistent_signals_count': persistent_signals_count,
        'tier_1_count': tier_1_count,
        'outreach_sent_count': outreach_sent_count,
        'replies_count': replies_count,
        'response_rate': response_rate,
        'deals_won_count': deals_won_count,
        'won_mrr_added': won_mrr_added,
        'active_pipeline_value': active_pipeline_val,
        'overdue_followups_count': overdue_followups_count,
        'top_leads': [
            {
                'name': lead.company_name,
                'domain': lead.domain,
                'intent': lead.hiring_intent_score,
                'fit': float(lead.talent_fit_score),
                'sector': lead.get_industry_vertical_display()
            }
            for lead in priority_leads
        ]
    }

    return digest_data


def send_weekly_bd_digest_email(recipients=None, target_date=None, performed_by=None):
    """
    Renders and dispatches the Weekly BD Executive Digest to Kodafriq management staff.
    """
    digest = generate_weekly_bd_digest(target_date=target_date, performed_by=performed_by)

    if not recipients:
        staff_emails = list(User.objects.filter(
            role__in=[User.Role.STAFF, User.Role.ADMIN],
            is_active=True
        ).exclude(email='').values_list('email', flat=True))
        recipients = staff_emails or ['bd-team@kodafriq.com']

    subject = f"📊 Kodafriq GrowthOS Weekly BD Digest ({digest['period_start']} – {digest['period_end']})"

    html_message = f"""
    <div style="font-family: 'Plus Jakarta Sans', Arial, sans-serif; max-width: 650px; margin: 0 auto; color: #091e42; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
        <div style="background: linear-gradient(135deg, #091e42 0%, #006fe6 100%); color: #ffffff; padding: 24px;">
            <h1 style="margin: 0; font-size: 1.4rem; font-weight: 800;">Kodafriq GrowthOS Commercial Digest</h1>
            <p style="margin: 6px 0 0 0; font-size: 0.85rem; opacity: 0.9;">Weekly Executive Acquisition & Pipeline Performance</p>
            <div style="font-size: 0.78rem; opacity: 0.8; margin-top: 8px;">{digest['period_start']} to {digest['period_end']}</div>
        </div>

        <div style="padding: 24px;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px;">
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px;">
                    <div style="font-size: 0.75rem; color: #64748b; font-weight: 700;">NEW LEADS SOURCED</div>
                    <div style="font-size: 1.6rem; font-weight: 800; color: #091e42;">{digest['new_leads_count']}</div>
                </div>
                <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px;">
                    <div style="font-size: 0.75rem; color: #059669; font-weight: 700;">NEW MRR ADDED</div>
                    <div style="font-size: 1.6rem; font-weight: 800; color: #059669;">${digest['won_mrr_added']:,.2f}/mo</div>
                </div>
            </div>

            <h3 style="font-size: 1rem; font-weight: 800; color: #091e42; border-bottom: 1.5px solid #f1f5f9; padding-bottom: 8px; margin-top: 20px;">
                Commercial Milestones This Week
            </h3>
            <ul style="font-size: 0.85rem; color: #334155; line-height: 1.7; padding-left: 20px;">
                <li><strong>{digest['tier_1_count']}</strong> Tier 1 Prime Targets currently engaged across sectors.</li>
                <li><strong>{digest['outreach_sent_count']}</strong> Personalized outreach pitches dispatched.</li>
                <li><strong>{digest['replies_count']}</strong> Client responses received (<strong>{digest['response_rate']}%</strong> response rate).</li>
                <li><strong>{digest['deals_won_count']}</strong> Commercial placement contracts signed and won.</li>
                <li><strong>${digest['active_pipeline_value']:,.2f}/mo</strong> Total active pipeline deal value.</li>
                <li><strong>{digest['overdue_followups_count']}</strong> Overdue client follow-ups requiring immediate staff contact.</li>
            </ul>

            <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #f1f5f9; text-align: center;">
                <a href="https://kodafriq.com/growth-os/" style="background: #006fe6; color: #ffffff; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 0.85rem; font-weight: 700; display: inline-block;">
                    Open GrowthOS Command Center &rarr;
                </a>
            </div>
        </div>
    </div>
    """

    plain_message = f"""
    Kodafriq GrowthOS Weekly BD Digest ({digest['period_start']} – {digest['period_end']})
    ----------------------------------------------------------------------------------
    - New Leads Sourced: {digest['new_leads_count']}
    - New MRR Added: ${digest['won_mrr_added']:,.2f}/mo ({digest['deals_won_count']} deals won)
    - Active Pipeline: ${digest['active_pipeline_value']:,.2f}/mo
    - Outreach Dispatched: {digest['outreach_sent_count']} (Response Rate: {digest['response_rate']}%)
    - Active Tier 1 Targets: {digest['tier_1_count']}
    - Overdue Follow-ups: {digest['overdue_followups_count']}
    """

    sent = False
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'growth-os@kodafriq.com'),
            recipient_list=recipients,
            html_message=html_message,
            fail_silently=False
        )
        sent = True
    except Exception as e:
        logger.error(f"Failed to dispatch weekly digest email: {e}")

    summary = f"Weekly BD Digest generated and dispatched to {len(recipients)} recipient(s). Sent={sent}."
    GrowthAutomationLog.objects.create(
        task_type=GrowthAutomationLog.TaskType.WEEKLY_DIGEST,
        executed_by=performed_by,
        status=GrowthAutomationLog.Status.SUCCESS if sent else GrowthAutomationLog.Status.PARTIAL,
        items_evaluated=digest['new_leads_count'],
        items_updated=digest['deals_won_count'],
        summary=summary,
        details_json=digest
    )

    return {
        'success': True,
        'sent': sent,
        'recipients': recipients,
        'digest': digest,
        'summary': summary
    }

