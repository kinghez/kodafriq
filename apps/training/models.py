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

    @property
    def total_modules(self):
        return self.modules.count()


class ProgramModule(models.Model):
    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=1)
    duration_minutes = models.PositiveIntegerField(default=45, help_text="Estimated study duration in minutes")
    content = models.TextField(help_text="Clinical guidelines, chart scenarios, and curriculum material")
    key_takeaways = models.TextField(blank=True, help_text="Core clinical coding rules and guidelines")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        unique_together = ('program', 'order')

    def __str__(self):
        return f"{self.program.title} - M{self.order}: {self.title}"


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

    @property
    def total_modules_count(self):
        return self.program.modules.count()

    @property
    def completed_modules_count(self):
        return self.module_progresses.filter(is_completed=True).count()

    @property
    def progress_percentage(self):
        total = self.total_modules_count
        if total == 0:
            return 100 if self.status == self.EnrolmentStatus.COMPLETED else 0
        completed = self.completed_modules_count
        return int(round((completed / total) * 100))


class ModuleProgress(models.Model):
    enrolment = models.ForeignKey(TrainingEnrolment, on_delete=models.CASCADE, related_name='module_progresses')
    module = models.ForeignKey(ProgramModule, on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('enrolment', 'module')

    def __str__(self):
        return f"{self.enrolment.candidate.full_name} - {self.module.title} [{'Done' if self.is_completed else 'Pending'}]"
