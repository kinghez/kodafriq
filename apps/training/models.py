from django.db import models
from apps.accounts.models import CandidateProfile
from apps.skills.models import Skill

class TrainingProgram(models.Model):
    title = models.CharField(max_length=200)
    instructor = models.CharField(max_length=150, default="Kodafriq Clinical Faculty")
    description = models.TextField()
    curriculum_overview = models.TextField(blank=True)
    skills_covered = models.ManyToManyField(Skill, blank=True, related_name='training_programs')
    duration_weeks = models.PositiveIntegerField(default=4)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.duration_weeks} wks)"

class TrainingEnrolment(models.Model):
    class EnrolmentStatus(models.TextChoices):
        ENROLLED = 'ENROLLED', 'Enrolled'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed & Certified'
        DROPPED = 'DROPPED', 'Withdrawn'

    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE, related_name='enrolments')
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='training_enrolments')
    status = models.CharField(max_length=25, choices=EnrolmentStatus.choices, default=EnrolmentStatus.ENROLLED)
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    final_assessment_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    certificate_id = models.CharField(max_length=50, blank=True, unique=True, null=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('program', 'candidate')

    def __str__(self):
        return f"{self.candidate.full_name} in {self.program.title} [{self.get_status_display()}]"
