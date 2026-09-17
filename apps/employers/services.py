from decimal import Decimal
from apps.skills.models import CandidateSkill

def calculate_job_match(job, candidate):
    """
    Computes a smart match percentage (0.00 - 100.00) between a Job requisition
    and a CandidateProfile based on:
      1. Verified Score Match (40% weight)
      2. Clinical Skill Alignment & Verification Tier (40% weight)
      3. Experience Match (20% weight)
    """
    # 1. Verified Score Match (40%)
    target_score = float(job.min_score_required) if job.min_score_required else 60.0
    candidate_score = float(candidate.kodafriq_verified_score) if candidate.kodafriq_verified_score else 0.0
    
    if target_score > 0:
        score_ratio = min(1.2, candidate_score / target_score)
        s_score = min(100.0, score_ratio * 100.0)
    else:
        s_score = 100.0

    # 2. Clinical Skill Alignment (40%)
    req_skills = list(job.required_skills.select_related('skill').all())
    if req_skills:
        cand_skills_map = {
            cs.skill_id: cs for cs in candidate.skills.all()
        }
        total_weight = 0.0
        earned_weight = 0.0

        for req in req_skills:
            weight = 2.0 if req.is_mandatory else 1.0
            total_weight += weight

            if req.skill_id in cand_skills_map:
                cand_skill = cand_skills_map[req.skill_id]
                tier = cand_skill.status
                if tier == CandidateSkill.VerificationStatus.KODAFRIQ_VERIFIED:
                    tier_multiplier = 1.0
                elif tier == CandidateSkill.VerificationStatus.ASSESSED:
                    tier_multiplier = 0.90
                else:  # SELF_REPORTED
                    tier_multiplier = 0.60
                earned_weight += weight * tier_multiplier

        s_skills = (earned_weight / total_weight) * 100.0 if total_weight > 0 else 100.0
    else:
        s_skills = 100.0 if candidate.skills.exists() else 70.0

    # 3. Experience Match (20%)
    req_exp = float(job.min_years_experience) if job.min_years_experience else 1.0
    cand_exp = float(candidate.years_of_experience) if candidate.years_of_experience else 0.0
    if req_exp > 0:
        exp_ratio = min(1.25, cand_exp / req_exp)
        s_exp = min(100.0, exp_ratio * 100.0)
    else:
        s_exp = 100.0

    # Composite Match Percentage
    final_match = (s_score * 0.40) + (s_skills * 0.40) + (s_exp * 0.20)
    final_match = max(0.0, min(100.0, round(final_match, 1)))
    return Decimal(str(final_match))
