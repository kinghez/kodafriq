from django.db import models
from django.conf import settings
from apps.accounts.models import CandidateProfile

class SkillCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon_name = models.CharField(max_length=50, default='activity', help_text='Icon identifier for UI')

    class Meta:
        verbose_name_plural = 'Skill Categories'

    def __str__(self):
        return self.name


class Skill(models.Model):
    category = models.ForeignKey(SkillCategory, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=120, unique=True)
    code_standard = models.CharField(max_length=50, blank=True, help_text='e.g., ICD-10-CM, CPT, HCPCS, DRG, RCM')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name} ({self.code_standard})' if self.code_standard else self.name


class CandidateSkill(models.Model):
    class VerificationStatus(models.TextChoices):
        SELF_REPORTED = 'SELF_REPORTED', 'Self-Reported'
        ASSESSED = 'ASSESSED', 'Assessed'
        KODAFRIQ_VERIFIED = 'KODAFRIQ_VERIFIED', 'Kodafriq Verified'

    class ProficiencyLevel(models.TextChoices):
        BEGINNER = 'BEGINNER', 'Beginner / Foundational'
        INTERMEDIATE = 'INTERMEDIATE', 'Intermediate / Competent'
        ADVANCED = 'ADVANCED', 'Advanced / Proficient'
        EXPERT = 'EXPERT', 'Subject Matter Expert'

    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='candidate_instances')
    status = models.CharField(
        max_length=25,
        choices=VerificationStatus.choices,
        default=VerificationStatus.SELF_REPORTED
    )
    proficiency = models.CharField(
        max_length=20,
        choices=ProficiencyLevel.choices,
        default=ProficiencyLevel.INTERMEDIATE
    )
    years_experience = models.PositiveIntegerField(default=1)
    evidence_file = models.FileField(upload_to='skills/evidence/', blank=True, null=True)
    evidence_notes = models.TextField(blank=True, help_text='Description of supporting evidence')
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_skills'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_feedback = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('candidate', 'skill')

    def __str__(self):
        return f'{self.candidate.full_name} - {self.skill.name} [{self.get_status_display()}]'
