from django.db import models
from apps.accounts.models import EmployerProfile, CandidateProfile
from apps.skills.models import Skill

class Job(models.Model):
    class JobType(models.TextChoices):
        FULL_TIME = 'FULL_TIME', 'Full-Time'
        PART_TIME = 'PART_TIME', 'Part-Time'
        CONTRACT = 'CONTRACT', 'Contract'
        REMOTE = 'REMOTE', 'Remote'
        HYBRID = 'HYBRID', 'Hybrid'
        ON_SITE = 'ON_SITE', 'On-Site'

    class JobStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active / Open'
        PAUSED = 'PAUSED', 'Paused'
        CLOSED = 'CLOSED', 'Closed / Filled'

    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name='jobs')
    title = models.CharField(max_length=200)
    description = models.TextField()
    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.REMOTE)
    location = models.CharField(max_length=150, default='Remote / Flexible')
    min_years_experience = models.PositiveIntegerField(default=2)
    min_score_required = models.DecimalField(max_digits=5, decimal_places=2, default=60.00)
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def clean_snippet(self):
        """Clean markdown symbols and return a clean short summary snippet."""
        import re
        txt = self.description or ''
        # Remove markdown headers (###), bold/italics (** or *), lists, links
        txt = re.sub(r'#+\s*', '', txt)
        txt = re.sub(r'\*{1,3}', '', txt)
        txt = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', txt)
        txt = re.sub(r'[`_~]', '', txt)
        txt = re.sub(r'\s+', ' ', txt).strip()
        words = txt.split()
        if len(words) > 24:
            return ' '.join(words[:24]) + '...'
        return txt

    def __str__(self):
        return f"{self.title} at {self.employer.company_name}"

class JobRequiredSkill(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='required_skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        unique_together = ('job', 'skill')

    def __str__(self):
        return f"{self.job.title} - {self.skill.name}"

class Application(models.Model):
    class Status(models.TextChoices):
        APPLIED = 'APPLIED', 'Applied'
        REVIEWED = 'REVIEWED', 'Reviewed'
        SHORTLISTED = 'SHORTLISTED', 'Shortlisted'
        INTERVIEW = 'INTERVIEW', 'Interviewing'
        OFFERED = 'OFFERED', 'Offered'
        REJECTED = 'REJECTED', 'Declined'

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='applications')
    match_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.APPLIED)
    cover_note = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('job', 'candidate')

    def __str__(self):
        return f"{self.candidate.full_name} -> {self.job.title} ({self.match_percentage}%)"

class Shortlist(models.Model):
    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name='shortlists')
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='favorited_by')
    notes = models.TextField(blank=True)
    rate_negotiable = models.BooleanField(default=False, help_text='Indicates rate negotiation interest for this candidate')
    is_shortlisted = models.BooleanField(default=True, help_text='Indicates candidate is in employer saved talent pool')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employer', 'candidate')

    def __str__(self):
        return f"{self.employer.company_name} shortlists {self.candidate.full_name}"
