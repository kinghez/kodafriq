import decimal
from decimal import Decimal
from django.db import models
from django.utils import timezone
from apps.scoring.models import ScoreWeightConfig, ScoreLog

def calculate_candidate_score(profile):
    """
    Calculates the Kodafriq Verified Score (0.00 - 100.00) based on
    the calibrated 5-component formula:
    
    Verified Score = (S_assess * W_assess) + (S_work * W_work) +
                     (S_train * W_train) + (S_exp * W_exp) + (S_ready * W_ready)
    """
    # 1. Fetch active weight configuration or fallback to defaults
    config = ScoreWeightConfig.objects.filter(is_active=True).first()
    if config:
        w_assess = Decimal(str(config.assessment_weight)) / Decimal('100')
        w_work = Decimal(str(config.work_performance_weight)) / Decimal('100')
        w_train = Decimal(str(config.training_weight)) / Decimal('100')
        w_exp = Decimal(str(config.professional_experience_weight)) / Decimal('100')
        w_ready = Decimal(str(config.readiness_weight)) / Decimal('100')
    else:
        w_assess = Decimal('0.40')
        w_work = Decimal('0.25')
        w_train = Decimal('0.15')
        w_exp = Decimal('0.10')
        w_ready = Decimal('0.10')

    # 2. Component 1: Assessment Performance (0 - 100)
    from apps.assessments.models import AssessmentAttempt
    attempts = AssessmentAttempt.objects.filter(
        candidate=profile,
        status='COMPLETED'
    )
    if attempts.exists():
        avg_score = attempts.aggregate(models.Avg('score_percentage'))['score_percentage__avg'] or 0
        s_assess = Decimal(str(round(avg_score, 2)))
    else:
        has_verified_skills = profile.skills.filter(status__in=['ASSESSED', 'KODAFRIQ_VERIFIED']).exists()
        s_assess = Decimal('65.00') if has_verified_skills else Decimal('0.00')

    # 3. Component 2: Work Performance & Verification (0 - 100)
    experiences = profile.work_experiences.all()
    if experiences.exists():
        base_work = Decimal('60.00')
        if experiences.filter(is_current=True).exists():
            base_work += Decimal('15.00')
        if experiences.count() >= 2:
            base_work += Decimal('15.00')
        s_work = min(Decimal('100.00'), base_work)
    else:
        s_work = Decimal('0.00')

    # 4. Component 3: Training & Accreditations (0 - 100)
    from apps.training.models import TrainingEnrolment
    trainings = TrainingEnrolment.objects.filter(candidate=profile, status='COMPLETED')
    if trainings.exists():
        s_train = min(Decimal('100.00'), Decimal(str(trainings.count() * 50)))
    else:
        certs = profile.certifications.all()
        if certs.exists():
            verified_certs = certs.filter(is_verified=True).count()
            s_train = Decimal('85.00') if verified_certs > 0 else Decimal('50.00')
        else:
            s_train = Decimal('0.00')

    # 5. Component 4: Professional Experience (0 - 100)
    years = profile.years_of_experience
    s_exp = min(Decimal('100.00'), Decimal(str(years * 18)))

    # 6. Component 5: Professional Readiness (0 - 100)
    readiness_factors = [
        bool(profile.user.first_name and profile.user.last_name),
        bool(profile.headline),
        bool(profile.bio),
        bool(profile.phone),
        bool(profile.location),
        bool(profile.profile_photo),
        bool(profile.resume_file),
        bool(profile.skills.exists()),
    ]
    s_ready = Decimal(str(round((sum(readiness_factors) / len(readiness_factors)) * 100, 2)))

    # 7. Weighted Composite Score
    final_score = (
        (s_assess * w_assess) +
        (s_work * w_work) +
        (s_train * w_train) +
        (s_exp * w_exp) +
        (s_ready * w_ready)
    ).quantize(Decimal('0.01'), rounding=decimal.ROUND_HALF_UP)

    final_score = min(Decimal('100.00'), max(Decimal('0.00'), final_score))

    # 8. Update Verification and Employer Readiness Status
    is_verified = profile.compute_verification_status()
    profile.is_verified = is_verified

    # Employer Readiness: Verified + Relevant Clinical Experience + Benchmark Score (>= 60)
    has_experience = (profile.years_of_experience >= 1) or profile.work_experiences.exists()
    if is_verified and has_experience and final_score >= Decimal('60.00'):
        profile.is_employer_ready = True
    else:
        profile.is_employer_ready = False
        
    profile.save(update_fields=['kodafriq_verified_score', 'is_verified', 'is_employer_ready'])

    # 9. Record in ScoreLog
    ScoreLog.objects.create(
        candidate=profile,
        final_score=final_score,
        assessment_component=s_assess,
        work_component=s_work,
        training_component=s_train,
        experience_component=s_exp,
        readiness_component=s_ready
    )

    return {
        'final_score': float(final_score),
        's_assess': float(s_assess),
        's_work': float(s_work),
        's_train': float(s_train),
        's_exp': float(s_exp),
        's_ready': float(s_ready),
        'w_assess': int(w_assess * 100),
        'w_work': int(w_work * 100),
        'w_train': int(w_train * 100),
        'w_exp': int(w_exp * 100),
        'w_ready': int(w_ready * 100),
    }
