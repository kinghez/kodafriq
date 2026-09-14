from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver

class User(AbstractUser):
    class Role(models.TextChoices):
        CANDIDATE = 'CANDIDATE', 'Healthcare Talent (Candidate)'
        EMPLOYER = 'EMPLOYER', 'Healthcare Employer'
        STAFF = 'STAFF', 'Kodafriq Staff'
        ADMIN = 'ADMIN', 'Kodafriq Administrator'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CANDIDATE,
        help_text='Primary role on the platform'
    )
    is_email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_talent(self):
        return self.role == self.Role.CANDIDATE

    @property
    def is_candidate(self):
        return self.role == self.Role.CANDIDATE

    @property
    def is_employer(self):
        return self.role == self.Role.EMPLOYER

    @property
    def is_kodafriq_staff(self):
        return self.role in [self.Role.STAFF, self.Role.ADMIN] or self.is_staff or self.is_superuser

    @property
    def role_badge_display(self):
        if self.is_kodafriq_staff:
            return 'Kodafriq Staff'
        elif self.is_employer:
            return 'Healthcare Employer'
        return 'Healthcare Talent'


class CandidateProfile(models.Model):
    class Availability(models.TextChoices):
        IMMEDIATE = 'IMMEDIATE', 'Immediately Available'
        TWO_WEEKS = 'TWO_WEEKS', '2 Weeks Notice'
        ONE_MONTH = 'ONE_MONTH', '1 Month Notice'
        NOT_LOOKING = 'NOT_LOOKING', 'Currently Employed / Not Looking'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='candidate_profile')
    headline = models.CharField(max_length=255, blank=True, help_text='e.g., Inpatient Medical Coder | CPC, CCS Certified')
    bio = models.TextField(blank=True, help_text='Professional bio & summary')
    phone = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=100, blank=True, help_text='e.g., Accra, Ghana / Remote')
    years_of_experience = models.PositiveIntegerField(default=0)
    availability_status = models.CharField(
        max_length=30,
        choices=Availability.choices,
        default=Availability.IMMEDIATE
    )
    desired_salary_range = models.CharField(max_length=100, blank=True)
    is_employer_ready = models.BooleanField(
        default=False,
        help_text='Indicates candidate has verified credentials and passed readiness check'
    )
    kodafriq_verified_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text='Dynamic weighted score from 0.00 to 100.00'
    )
    profile_photo = models.ImageField(upload_to='candidates/photos/', blank=True, null=True)
    resume_file = models.FileField(upload_to='candidates/resumes/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.user.email})'

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username


class EmployerProfile(models.Model):
    class ApprovalStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Verification'
        APPROVED = 'APPROVED', 'Approved Healthcare Employer'
        REJECTED = 'REJECTED', 'Application Declined'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employer_profile')
    company_name = models.CharField(max_length=200)
    industry = models.CharField(max_length=120, default='Healthcare & Revenue Cycle Management')
    website = models.URLField(blank=True)
    company_size = models.CharField(max_length=50, blank=True, help_text='e.g., 50-200 Employees')
    contact_person_title = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    company_logo = models.ImageField(upload_to='employers/logos/', blank=True, null=True)
    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING
    )
    approval_notes = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.company_name} ({self.get_approval_status_display()})'


class WorkExperience(models.Model):
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='work_experiences')
    organization_name = models.CharField(max_length=200)
    job_title = models.CharField(max_length=150)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.job_title} at {self.organization_name}'


class CandidateCertification(models.Model):
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='certifications')
    certification_name = models.CharField(max_length=150, help_text='e.g., CPC (Certified Professional Coder)')
    issuing_organization = models.CharField(max_length=150, help_text='e.g., AAPC, AHIMA')
    credential_id = models.CharField(max_length=100, blank=True)
    issue_date = models.DateField()
    expiration_date = models.DateField(null=True, blank=True)
    certificate_file = models.FileField(upload_to='candidates/certifications/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.certification_name} - {self.candidate.user.get_full_name() or self.candidate.user.username}'


# Signals for automatic profile provisioning and staff permission
@receiver(post_save, sender=User)
def handle_user_profile_and_roles(sender, instance, created, **kwargs):
    # Auto-grant is_staff for Kodafriq Staff
    if instance.role in [User.Role.STAFF, User.Role.ADMIN]:
        if not instance.is_staff:
            User.objects.filter(pk=instance.pk).update(is_staff=True)

    # Auto-create CandidateProfile
    if instance.role == User.Role.CANDIDATE:
        CandidateProfile.objects.get_or_create(user=instance)

    # Auto-create EmployerProfile
    elif instance.role == User.Role.EMPLOYER:
        if not hasattr(instance, 'employer_profile'):
            name = instance.get_full_name() or instance.username
            EmployerProfile.objects.get_or_create(
                user=instance,
                defaults={'company_name': f'{name} Healthcare'}
            )
