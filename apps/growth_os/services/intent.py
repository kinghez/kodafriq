"""
apps/growth_os/services/intent.py
Algorithmic Hiring Intent Scoring Engine for Kodafriq GrowthOS.
Computes multi-variable hiring intent score based on vacancy volume,
persistent vacancy aging, listing recency, verified contacts, and careers portals.
"""
from django.utils import timezone
from datetime import timedelta
from apps.growth_os.models import EmployerLead, HiringSignal, LeadContact, CRMActivity


def calculate_lead_intent_score(lead: EmployerLead) -> int:
    """
    Computes hiring intent score (0-100) using the GrowthOS formula:
    S_intent = min(100, V + P + R + C + U)
    Where:
    - V (Vacancy Volume): up to 40 pts
    - P (Persistent Vacancy >30d / >60d): 25 to 35 pts
    - R (Recency <7d): 15 pts
    - C (Decision Maker Identified & Verified): 10 to 20 pts
    - U (Careers URL documented): 10 pts
    """
    score = 0
    active_vacancies = lead.vacancies.filter(is_active=True)
    vac_count = active_vacancies.count()

    # 1. Vacancy Volume (V: up to 40 pts)
    if vac_count >= 5:
        score += 40
    elif vac_count >= 3:
        score += 30
    elif vac_count >= 1:
        score += 20

    # 2. Persistent Vacancies (P: up to 35 pts)
    # Positions open >60 days indicate severe recruitment struggle
    persistent_60 = active_vacancies.filter(days_open__gte=60).exists()
    persistent_30 = active_vacancies.filter(days_open__gte=30).exists() or active_vacancies.filter(is_persistent=True).exists()

    if persistent_60:
        score += 35
    elif persistent_30:
        score += 25

    # 3. Recency (R: 15 pts) - Active vacancy posted or detected within the last 7 days
    seven_days_ago = timezone.now().date() - timedelta(days=7)
    recent_vacancies = active_vacancies.filter(date_detected__gte=seven_days_ago)
    if recent_vacancies.exists():
        score += 15

    # 4. Decision Maker Contact with Verified Email (C: up to 20 pts)
    verified_contacts = lead.contacts.filter(
        email__gt='',
        verification_status=LeadContact.VerificationStatus.VERIFIED_VALID
    )
    any_contacts = lead.contacts.filter(email__gt='')

    if verified_contacts.exists():
        score += 20
    elif any_contacts.exists():
        score += 10

    # 5. Careers Portal Documented (U: 10 pts)
    if lead.careers_url:
        score += 10

    total_score = min(100, score)

    old_tier = lead.priority_tier
    old_score = lead.hiring_intent_score

    lead.hiring_intent_score = total_score
    lead.save(update_fields=['hiring_intent_score'])

    new_tier = lead.priority_tier
    if old_tier != new_tier:
        CRMActivity.objects.create(
            lead=lead,
            activity_type=CRMActivity.ActivityType.STAGE_CHANGE,
            summary=f"Priority quadrant updated: Tier {old_tier} -> Tier {new_tier} ({lead.priority_tier_display})",
            details=f"Hiring intent updated from {old_score} to {total_score}."
        )

    return total_score

