from django.db import models
from apps.accounts.models import CandidateProfile
from apps.skills.models import SkillCategory, Skill

class Assessment(models.Model):
    category = models.ForeignKey(SkillCategory, on_delete=models.CASCADE, related_name='assessments')
    primary_skill = models.ForeignKey(Skill, on_delete=models.SET_NULL, null=True, blank=True, related_name='assessments')
    title = models.CharField(max_length=200)
    description = models.TextField()
    instructions = models.TextField(blank=True, default='Answer all questions before the timer expires.')
    duration_minutes = models.PositiveIntegerField(default=30)
    pass_mark_percentage = models.PositiveIntegerField(default=75)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.duration_minutes} mins)"

class Question(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='questions')
    prompt = models.TextField()
    explanation = models.TextField(blank=True)
    points = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Q{self.order}: {self.prompt[:50]}"

class AnswerChoice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({self.is_correct})"

class AssessmentAttempt(models.Model):
    class AttemptStatus(models.TextChoices):
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        TIMED_OUT = 'TIMED_OUT', 'Timed Out'

    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='assessment_attempts')
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='attempts')
    status = models.CharField(max_length=20, choices=AttemptStatus.choices, default=AttemptStatus.IN_PROGRESS)
    score_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    passed = models.BooleanField(default=False)
    total_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.candidate.full_name} - {self.assessment.title} ({self.score_percentage}%)"

class CandidateResponse(models.Model):
    attempt = models.ForeignKey(AssessmentAttempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(AnswerChoice, on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
