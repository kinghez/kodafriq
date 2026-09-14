from django.db import models
from apps.accounts.models import CandidateProfile

class ScoreWeightConfig(models.Model):
    name = models.CharField(max_length=100, default="Standard Kodafriq Weighting")
    assessment_weight = models.DecimalField(max_digits=5, decimal_places=2, default=40.00, help_text="Weight for assessments (default 40%)")
    work_performance_weight = models.DecimalField(max_digits=5, decimal_places=2, default=25.00, help_text="Weight for work performance (default 25%)")
    training_weight = models.DecimalField(max_digits=5, decimal_places=2, default=15.00, help_text="Weight for training completion (default 15%)")
    professional_experience_weight = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, help_text="Weight for years of experience (default 10%)")
    readiness_weight = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, help_text="Weight for professional readiness (default 10%)")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Active: {self.is_active})"

class ScoreLog(models.Model):
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='score_logs')
    final_score = models.DecimalField(max_digits=5, decimal_places=2)
    assessment_component = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    work_component = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    training_component = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    experience_component = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    readiness_component = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    calculated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.candidate.full_name}: {self.final_score}% at {self.calculated_at:%Y-%m-%d %H:%M}"
