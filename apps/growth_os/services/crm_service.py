"""
GrowthOS CRM & Pipeline Service
Handles stage transitions, pipeline metrics, and 1-click conversion from
EmployerLead to Kodafriq EmployerProfile & Contract.
"""
from decimal import Decimal
import uuid
import secrets
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q, F

from apps.accounts.models import EmployerProfile, CandidateProfile
from apps.contracts.models import Contract
from apps.growth_os.models import EmployerLead, CRMOpportunity, CRMActivity, TalentReverseMatch

User = get_user_model()

STAGE_PROBABILITIES = {
    CRMOpportunity.Stage.STAGE_1_DISCOVERED: 10,
    CRMOpportunity.Stage.STAGE_2_QUALIFIED: 20,
    CRMOpportunity.Stage.STAGE_3_HIRING_SIGNAL: 35,
    CRMOpportunity.Stage.STAGE_4_CONTACT_IDENTIFIED: 45,
    CRMOpportunity.Stage.STAGE_5_OUTREACH_SENT: 50,
    CRMOpportunity.Stage.STAGE_6_REPLY_RECEIVED: 65,
    CRMOpportunity.Stage.STAGE_7_MEETING_SCHEDULED: 75,
    CRMOpportunity.Stage.STAGE_8_SHORTLIST_DELIVERED: 85,
    CRMOpportunity.Stage.STAGE_9_INTERVIEWS: 90,
    CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON: 100,
    CRMOpportunity.Stage.CLOSED_LOST: 0,
}


def ensure_opportunities_for_all_leads():
    """
    Guarantees that every EmployerLead in the database has an associated CRMOpportunity
    so it appears seamlessly on the Kanban pipeline board.
    """
    leads_without_opp = EmployerLead.objects.filter(crm_opportunity__isnull=True)
    new_opps = []
    for lead in leads_without_opp:
        new_opps.append(CRMOpportunity(
            lead=lead,
            stage=CRMOpportunity.Stage.STAGE_1_DISCOVERED,
            win_probability_percent=STAGE_PROBABILITIES.get(CRMOpportunity.Stage.STAGE_1_DISCOVERED, 10),
            priority=CRMOpportunity.Priority.HIGH if lead.hiring_intent_score >= 60 else CRMOpportunity.Priority.MEDIUM
        ))
    if new_opps:
        CRMOpportunity.objects.bulk_create(new_opps)


def transition_opportunity_stage(opportunity, new_stage, performed_by=None, notes=""):
    """
    Safely transitions an opportunity to a new Kanban stage, auto-logs a CRMActivity,
    syncs the lead status, and updates win probability.
    """
    if new_stage not in CRMOpportunity.Stage.values:
        raise ValueError(f"Invalid pipeline stage: {new_stage}")

    old_stage = opportunity.stage
    old_stage_display = opportunity.get_stage_display()

    opportunity.stage = new_stage
    opportunity.win_probability_percent = STAGE_PROBABILITIES.get(new_stage, opportunity.win_probability_percent)
    opportunity.save(update_fields=['stage', 'win_probability_percent', 'updated_at'])

    lead = opportunity.lead
    # Synchronize parent lead status
    if new_stage == CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON:
        if lead.status != EmployerLead.Status.CONVERTED:
            lead.status = EmployerLead.Status.CONVERTED
            lead.save(update_fields=['status', 'updated_at'])
    elif new_stage == CRMOpportunity.Stage.CLOSED_LOST:
        if lead.status != EmployerLead.Status.DISQUALIFIED:
            lead.status = EmployerLead.Status.DISQUALIFIED
            lead.save(update_fields=['status', 'updated_at'])
    else:
        if lead.status not in [EmployerLead.Status.IN_PIPELINE, EmployerLead.Status.QUALIFIED]:
            lead.status = EmployerLead.Status.IN_PIPELINE
            lead.save(update_fields=['status', 'updated_at'])

    # Log CRM Stage Change Activity
    new_stage_display = opportunity.get_stage_display()
    details_text = notes.strip() if notes else f"Pipeline stage moved from '{old_stage_display}' to '{new_stage_display}'."
    if opportunity.estimated_monthly_deal_value > 0:
        details_text += f" | Estimated Deal: ${opportunity.estimated_monthly_deal_value:,.2f}/mo"

    CRMActivity.objects.create(
        lead=lead,
        activity_type=CRMActivity.ActivityType.STAGE_CHANGE,
        summary=f"Stage Changed: {new_stage_display}",
        details=details_text,
        performed_by=performed_by
    )

    return opportunity


def get_kanban_board_data(sector=None, priority=None, staff=None, search_query=None):
    """
    Fetches and organizes opportunities across all 10 stages plus CLOSED_LOST,
    calculating pipeline aggregates and deal metrics.
    """
    ensure_opportunities_for_all_leads()

    qs = CRMOpportunity.objects.select_related(
        'lead', 'lead__assigned_staff'
    ).prefetch_related(
        'lead__vacancies', 'lead__contacts'
    )

    # Filters
    if sector:
        qs = qs.filter(lead__industry_vertical=sector)
    if priority:
        qs = qs.filter(priority=priority)
    if staff:
        qs = qs.filter(lead__assigned_staff_id=staff)
    if search_query:
        sq = search_query.strip()
        qs = qs.filter(
            Q(lead__company_name__icontains=sq) |
            Q(lead__domain__icontains=sq) |
            Q(lead__city__icontains=sq)
        )

    # Compute overall active metrics (excluding closed lost)
    active_qs = qs.exclude(stage=CRMOpportunity.Stage.CLOSED_LOST)
    total_active_deals = active_qs.count()

    total_pipeline_val = active_qs.aggregate(
        total=Sum('estimated_monthly_deal_value')
    )['total'] or Decimal('0.00')

    # Weighted Pipeline Value
    weighted_sum = Decimal('0.00')
    for opp in active_qs:
        weight = Decimal(str(opp.win_probability_percent)) / Decimal('100.00')
        weighted_sum += (opp.estimated_monthly_deal_value * weight)

    # Follow-ups needing attention
    today = timezone.localdate()
    overdue_followups = qs.filter(
        next_follow_up_date__lt=today
    ).exclude(stage__in=[CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON, CRMOpportunity.Stage.CLOSED_LOST]).count()

    due_today_followups = qs.filter(
        next_follow_up_date=today
    ).exclude(stage__in=[CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON, CRMOpportunity.Stage.CLOSED_LOST]).count()

    # Build Stage Columns
    stage_choices = list(CRMOpportunity.Stage.choices)
    columns = []

    # Map all opportunities by stage
    opps_by_stage = {}
    for opp in qs.order_by('-estimated_monthly_deal_value', '-updated_at'):
        opps_by_stage.setdefault(opp.stage, []).append(opp)

    for stage_code, stage_label in stage_choices:
        stage_opps = opps_by_stage.get(stage_code, [])
        stage_val = sum((o.estimated_monthly_deal_value for o in stage_opps), Decimal('0.00'))
        columns.append({
            'code': stage_code,
            'label': stage_label,
            'count': len(stage_opps),
            'total_value': stage_val,
            'opportunities': stage_opps,
            'is_lost': stage_code == CRMOpportunity.Stage.CLOSED_LOST,
            'is_won': stage_code == CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON,
        })

    return {
        'columns': columns,
        'total_active_deals': total_active_deals,
        'total_pipeline_value': total_pipeline_val,
        'total_weighted_value': weighted_sum,
        'overdue_followups_count': overdue_followups,
        'due_today_followups_count': due_today_followups,
    }


@transaction.atomic
def convert_lead_to_employer(lead, user_data=None, contract_data=None, performed_by=None):
    """
    1-Click Conversion Engine:
    Converts an EmployerLead into a full Kodafriq EmployerProfile, links User account,
    creates initial Contract (if candidate selected), advances stage to 10_PLACEMENT_WON,
    and logs immutable CRM audit activities.
    """
    user_data = user_data or {}
    contract_data = contract_data or {}

    primary_contact = lead.contacts.filter(is_primary=True).first() or lead.contacts.first()

    # Determine user email
    email = user_data.get('email', '').strip().lower()
    if not email and primary_contact and primary_contact.email:
        email = primary_contact.email.strip().lower()
    if not email:
        clean_domain = lead.domain or 'employer.local'
        email = f"contact@{clean_domain}"

    # Determine username
    base_username = email.split('@')[0].replace('.', '_').replace('-', '_')[:25]
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exclude(email=email).exists():
        username = f"{base_username}_{counter}"
        counter += 1

    # Find or create User
    user = User.objects.filter(email=email).first()
    if not user:
        raw_password = user_data.get('password') or secrets.token_urlsafe(12)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=raw_password,
            first_name=user_data.get('first_name', primary_contact.full_name.split()[0] if primary_contact else ''),
            last_name=user_data.get('last_name', ' '.join(primary_contact.full_name.split()[1:]) if primary_contact and len(primary_contact.full_name.split()) > 1 else ''),
            role=User.Role.EMPLOYER,
            is_email_verified=True,
        )
    else:
        if user.role != User.Role.EMPLOYER and not user.is_staff and not user.is_superuser:
            user.role = User.Role.EMPLOYER
            user.save(update_fields=['role'])

    # Find or update EmployerProfile
    employer_profile, _ = EmployerProfile.objects.get_or_create(
        user=user,
        defaults={
            'company_name': user_data.get('company_name', lead.company_name),
            'website': user_data.get('website', lead.website),
            'country': user_data.get('country', lead.country),
            'city': user_data.get('city', lead.city),
            'approval_status': EmployerProfile.ApprovalStatus.APPROVED,
        }
    )

    # Sync employer profile fields with lead data
    employer_profile.company_name = user_data.get('company_name') or lead.company_name
    employer_profile.website = user_data.get('website') or lead.website
    employer_profile.country = user_data.get('country') or lead.country
    employer_profile.city = user_data.get('city') or lead.city
    employer_profile.industry = user_data.get('industry') or lead.get_industry_vertical_display()
    if lead.company_size:
        employer_profile.company_size = lead.get_company_size_display()
    if primary_contact:
        employer_profile.contact_person_title = primary_contact.job_title
        employer_profile.contact_phone = primary_contact.phone
    employer_profile.approval_status = EmployerProfile.ApprovalStatus.APPROVED
    employer_profile.approved_at = timezone.now()
    if lead.notes:
        employer_profile.bio = lead.notes
    employer_profile.save()

    # Link lead to EmployerProfile and update status
    lead.converted_employer_profile = employer_profile
    lead.status = EmployerLead.Status.CONVERTED
    lead.save(update_fields=['converted_employer_profile', 'status', 'updated_at'])

    # Update CRM Opportunity to Stage 10 Won
    opportunity, _ = CRMOpportunity.objects.get_or_create(lead=lead)
    opportunity.stage = CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON
    opportunity.win_probability_percent = 100
    opportunity.save(update_fields=['stage', 'win_probability_percent', 'updated_at'])

    # Provision Contract if candidate selected
    contract = None
    candidate_id = contract_data.get('candidate_id')
    if candidate_id:
        try:
            candidate = CandidateProfile.objects.get(id=candidate_id)
            title = contract_data.get('title') or f"{lead.company_name} - Operations Specialist"
            contract_type = contract_data.get('contract_type') or Contract.ContractType.HOURLY
            rate = Decimal(str(contract_data.get('rate_per_hour') or '25.00'))
            milestone_amount = Decimal(str(contract_data.get('total_milestone_amount') or '0.00'))
            weekly_hours = int(contract_data.get('weekly_hour_limit') or 40)
            scope = contract_data.get('scope_of_work') or f"Dedicated healthcare placement for {lead.company_name}."

            contract = Contract.objects.create(
                employer=employer_profile,
                candidate=candidate,
                title=title,
                contract_type=contract_type,
                rate_per_hour=rate,
                total_milestone_amount=milestone_amount,
                weekly_hour_limit=weekly_hours,
                scope_of_work=scope,
                status=Contract.Status.PENDING,
            )
        except CandidateProfile.DoesNotExist:
            contract = None

    # Log CRM Activity
    summary_text = f"Converted Lead to Employer Profile: {employer_profile.company_name}"
    contract_detail = f" | Contract Ref: {contract.contract_ref}" if contract else " | No initial contract created."
    details_text = f"User Account: {user.email} (ID: {user.id}){contract_detail}. Stage advanced to 10. Placement Won."

    CRMActivity.objects.create(
        lead=lead,
        activity_type=CRMActivity.ActivityType.STAGE_CHANGE,
        summary=summary_text,
        details=details_text,
        performed_by=performed_by
    )

    return {
        'success': True,
        'user': user,
        'employer_profile': employer_profile,
        'contract': contract,
        'opportunity': opportunity,
    }

