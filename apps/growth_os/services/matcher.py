"""
apps/growth_os/services/matcher.py
Reverse Talent Matching Engine for Kodafriq GrowthOS.
Matches vetted healthcare candidates against employer open vacancies and operational verticals.
"""
from decimal import Decimal
from apps.accounts.models import CandidateProfile
from apps.growth_os.models import EmployerLead, TalentReverseMatch


def compute_lead_reverse_matches(lead: EmployerLead) -> int:
    """
    Computes reverse talent matches between Kodafriq candidate pool and this employer lead.
    Creates or updates TalentReverseMatch entries and recalculates the lead's talent_fit_score.
    """
    vacancies = lead.vacancies.filter(is_active=True)

    # 1. Gather target role keywords from vacancies or lead vertical
    target_terms = set()
    for v in vacancies:
        target_terms.add(v.job_title.lower())
        if v.role_category:
            target_terms.add(v.get_role_category_display().lower())
        if v.extracted_skills:
            for s in v.extracted_skills:
                target_terms.add(str(s).lower())

    if not target_terms:
        target_terms.add(lead.get_industry_vertical_display().lower())

    # 2. Query potential candidate pool (verified or employer-ready prioritized)
    candidates = CandidateProfile.objects.select_related('user').prefetch_related(
        'skills__skill', 'certifications'
    ).filter(user__is_active=True).order_by('-is_employer_ready', '-is_verified', '-kodafriq_verified_score')

    matched_candidate_scores = []
    matching_vacancy = vacancies.first()

    # Evaluate up to 30 active candidates
    for candidate in candidates[:30]:
        score = Decimal('30.00')  # Base baseline
        matched_skills = []
        rationale_points = []

        candidate_skills = [cs.skill.name.lower() for cs in candidate.skills.all()]
        cand_headline = (candidate.headline or '').lower()
        cand_bio = (candidate.bio or '').lower()
        cand_certs = [c.name.lower() for c in candidate.certifications.all()]

        # Check keyword matches
        for term in target_terms:
            words = [w for w in term.replace(',', ' ').replace('/', ' ').replace('&', ' ').split() if len(w) > 3]
            for w in words:
                if any(w in cs for cs in candidate_skills) or w in cand_headline or w in cand_bio or any(w in cert for cert in cand_certs):
                    matched_skills.append(w.capitalize())

        matched_skills = list(dict.fromkeys(matched_skills))[:6]

        # Skill score (up to 35 pts)
        if len(matched_skills) >= 3:
            score += Decimal('35.00')
            rationale_points.append(f"Demonstrated proficiency in {', '.join(matched_skills[:3])}")
        elif len(matched_skills) >= 1:
            score += Decimal('20.00')
            rationale_points.append(f"Matches required domain skill: {matched_skills[0]}")
        else:
            score += Decimal('10.00')

        # Kodafriq Verified & Assessment bonus (up to 25 pts)
        if candidate.is_employer_ready:
            score += Decimal('15.00')
            rationale_points.append("Kodafriq Employer-Ready Certified")
        if candidate.is_verified:
            score += Decimal('10.00')
            rationale_points.append("Verified professional credentials")

        # Verified score weighting (up to 10 pts)
        if candidate.kodafriq_verified_score > 0:
            score += Decimal(str(round(float(candidate.kodafriq_verified_score) * 0.10, 2)))

        # Immediate availability bonus (10 pts)
        if candidate.availability_status == CandidateProfile.Availability.IMMEDIATE:
            score += Decimal('10.00')
            rationale_points.append("Immediately available for deployment")
        elif candidate.availability_status == CandidateProfile.Availability.TWO_WEEKS:
            score += Decimal('5.00')

        # Experience bonus (up to 5 pts)
        if candidate.years_of_experience >= 3:
            score += Decimal('5.00')

        score = min(Decimal('98.00'), max(Decimal('45.00'), score))

        # Save match
        TalentReverseMatch.objects.update_or_create(
            lead=lead,
            candidate=candidate,
            vacancy=matching_vacancy,
            defaults={
                'match_score': score,
                'matched_skills': matched_skills,
                'matching_rationale': " | ".join(rationale_points) or "Relevant healthcare billing & coding talent match."
            }
        )
        matched_candidate_scores.append(float(score))

    # Calculate overall talent_fit_score for the lead
    if matched_candidate_scores:
        top_scores = sorted(matched_candidate_scores, reverse=True)[:5]
        avg_top = sum(top_scores) / len(top_scores)
        lead.talent_fit_score = int(round(avg_top))
    else:
        lead.talent_fit_score = 0

    lead.save(update_fields=['talent_fit_score'])
    return lead.talent_fit_score

