import uuid
from decimal import Decimal
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from apps.accounts.models import EmployerProfile, CandidateProfile
from apps.employers.models import Job


class Contract(models.Model):
    class ContractType(models.TextChoices):
        HOURLY = 'HOURLY', 'Hourly (Weekly Timesheet)'
        MILESTONE = 'MILESTONE', 'Fixed Milestone / Deliverables'

    class DisbursementMode(models.TextChoices):
        OPTION_A = 'OPTION_A', 'Option A: Direct Subaccount Split (Weekly Recurring)'
        OPTION_B = 'OPTION_B', 'Option B: Platform Escrow Pool (Milestone/Short-Term)'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Candidate Acceptance'
        ACTIVE = 'ACTIVE', 'Active / In Progress'
        PAUSED = 'PAUSED', 'Paused'
        COMPLETED = 'COMPLETED', 'Completed'
        TERMINATED = 'TERMINATED', 'Terminated'
        DECLINED = 'DECLINED', 'Declined'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract_ref = models.CharField(max_length=24, unique=True, blank=True, editable=False)

    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name='contracts')
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='contracts')
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts')

    title = models.CharField(max_length=255, help_text="e.g., Inpatient Medical Coder - Remote")
    contract_type = models.CharField(max_length=20, choices=ContractType.choices, default=ContractType.HOURLY)
    disbursement_mode = models.CharField(max_length=20, choices=DisbursementMode.choices, default=DisbursementMode.OPTION_A)

    # Economics (Candidate agreed rate + Kodafriq 10% platform markup)
    rate_per_hour = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Net hourly rate paid to candidate ($)")
    kodafriq_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'), help_text="Kodafriq platform markup percentage (default 10.00%)")
    weekly_hour_limit = models.PositiveIntegerField(default=40, help_text="Maximum billable hours allowed per week")
    total_milestone_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), blank=True, help_text="Total fixed deliverable amount (for MILESTONE contract)")
    currency = models.CharField(max_length=10, default='USD')

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    scope_of_work = models.TextField(blank=True, help_text="Key deliverables, responsibilities, chart types, and clinical expectations")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.contract_ref:
            import random
            rand_suffix = random.randint(1000, 9999)
            self.contract_ref = f"KD-{rand_suffix}"
            while Contract.objects.filter(contract_ref=self.contract_ref).exclude(pk=self.pk).exists():
                rand_suffix = random.randint(1000, 9999)
                self.contract_ref = f"KD-{rand_suffix}"
        super().save(*args, **kwargs)

    @property
    def platform_fee_multiplier(self):
        return Decimal('1.00') + (self.kodafriq_fee_percent / Decimal('100.00'))

    @property
    def billed_rate_per_hour(self):
        """Employer total billed hourly rate ($T = $R * (1 + M/100))"""
        return (self.rate_per_hour * self.platform_fee_multiplier).quantize(Decimal('0.01'))

    @property
    def platform_fee_per_hour(self):
        """Platform fee per hour retained by Kodafriq ($T - $R)"""
        return (self.billed_rate_per_hour - self.rate_per_hour).quantize(Decimal('0.01'))

    @property
    def billed_milestone_amount(self):
        """Employer total billed amount for fixed milestone"""
        return (self.total_milestone_amount * self.platform_fee_multiplier).quantize(Decimal('0.01'))

    @property
    def platform_fee_milestone(self):
        return (self.billed_milestone_amount - self.total_milestone_amount).quantize(Decimal('0.01'))

    def get_or_create_current_timesheet(self):
        """
        Retrieves or generates the current week's Timesheet (Mon-Sun),
        pre-populating the 7 daily TimesheetEntry records.
        """
        today = timezone.localdate()
        mon = today - timedelta(days=today.weekday())
        sun = mon + timedelta(days=6)

        timesheet, _ = Timesheet.objects.get_or_create(
            contract=self,
            week_start_date=mon,
            defaults={'week_end_date': sun, 'status': Timesheet.Status.DRAFT}
        )
        existing_dates = set(timesheet.entries.values_list('date', flat=True))
        for day_offset in range(7):
            d = mon + timedelta(days=day_offset)
            if d not in existing_dates:
                TimesheetEntry.objects.create(
                    timesheet=timesheet,
                    date=d,
                    hours_worked=Decimal('0.00'),
                    charts_coded_count=0,
                    work_description=''
                )
        return timesheet

    def get_absolute_url(self):
        return reverse('contracts:contract_detail', kwargs={'pk': str(self.pk)})

    def __str__(self):
        return f"{self.contract_ref}: {self.title} ({self.employer.company_name} ➔ {self.candidate.full_name})"


class Timesheet(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft (In Progress)'
        SUBMITTED = 'SUBMITTED', 'Submitted for Review'
        APPROVED = 'APPROVED', 'Approved by Employer'
        PAID = 'PAID', 'Paid / Settled'
        DISPUTED = 'DISPUTED', 'Disputed / Under Review'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='timesheets')
    week_start_date = models.DateField(help_text="Monday of the timesheet week")
    week_end_date = models.DateField(help_text="Sunday of the timesheet week")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    candidate_notes = models.TextField(blank=True, help_text="Weekly summary notes from talent to employer")
    employer_review_notes = models.TextField(blank=True, help_text="Review feedback or adjustment comments")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-week_start_date']
        unique_together = ('contract', 'week_start_date')

    @property
    def total_hours(self):
        res = self.entries.aggregate(models.Sum('hours_worked'))['hours_worked__sum']
        return res if res is not None else Decimal('0.00')

    @property
    def total_charts_coded(self):
        res = self.entries.aggregate(models.Sum('charts_coded_count'))['charts_coded_count__sum']
        return res if res is not None else 0

    @property
    def talent_gross_earnings(self):
        """Net talent compensation for logged hours"""
        return (self.total_hours * self.contract.rate_per_hour).quantize(Decimal('0.01'))

    @property
    def kodafriq_fee(self):
        """10% platform markup fee"""
        return (self.talent_gross_earnings * (self.contract.kodafriq_fee_percent / Decimal('100.00'))).quantize(Decimal('0.01'))

    @property
    def total_employer_charge(self):
        """Gross amount billed to employer"""
        return (self.talent_gross_earnings + self.kodafriq_fee).quantize(Decimal('0.01'))

    def get_absolute_url(self):
        return reverse('contracts:candidate_timesheet_log', kwargs={'pk': str(self.pk)})

    def __str__(self):
        return f"{self.contract.contract_ref} - Week of {self.week_start_date.strftime('%b %d, %Y')} ({self.get_status_display()})"


class TimesheetEntry(models.Model):
    timesheet = models.ForeignKey(Timesheet, on_delete=models.CASCADE, related_name='entries')
    date = models.DateField()
    hours_worked = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    charts_coded_count = models.PositiveIntegerField(default=0, help_text="Charts coded, claims audited, or cases handled")
    work_description = models.TextField(blank=True, help_text="Clinical summary of tasks completed")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date']
        unique_together = ('timesheet', 'date')

    @property
    def day_name(self):
        return self.date.strftime('%A')

    @property
    def short_day(self):
        return self.date.strftime('%a')

    def __str__(self):
        return f"{self.date.strftime('%a %Y-%m-%d')}: {self.hours_worked} hrs ({self.charts_coded_count} charts)"


class Milestone(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending / Not Started'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        SUBMITTED = 'SUBMITTED', 'Submitted for Review'
        APPROVED = 'APPROVED', 'Approved'
        PAID = 'PAID', 'Paid / Disbursed'
        DISPUTED = 'DISPUTED', 'Disputed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Net talent milestone compensation")
    order = models.PositiveIntegerField(default=1)
    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    deliverable_file = models.FileField(upload_to='contracts/milestones/', null=True, blank=True)
    submission_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    employer_feedback = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']

    @property
    def kodafriq_fee(self):
        return (self.amount * (self.contract.kodafriq_fee_percent / Decimal('100.00'))).quantize(Decimal('0.01'))

    @property
    def total_employer_charge(self):
        return (self.amount + self.kodafriq_fee).quantize(Decimal('0.01'))

    def __str__(self):
        return f"{self.contract.contract_ref} - Milestone {self.order}: {self.title} (${self.amount})"


class DisputeCase(models.Model):
    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open / Under Mediation'
        RESOLVED = 'RESOLVED', 'Resolved'
        CANCELLED = 'CANCELLED', 'Withdrawn / Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='disputes')
    timesheet = models.ForeignKey(Timesheet, on_delete=models.SET_NULL, null=True, blank=True, related_name='disputes')
    milestone = models.ForeignKey(Milestone, on_delete=models.SET_NULL, null=True, blank=True, related_name='disputes')
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contract_disputes')
    reason = models.TextField(help_text="Detailed explanation of disagreement or quality concern")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    resolution_notes = models.TextField(blank=True, help_text="Mediation notes and resolution details by Kodafriq Staff")
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Dispute on {self.contract.contract_ref} ({self.get_status_display()})"
