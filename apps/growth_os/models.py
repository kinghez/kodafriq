import uuid
import re
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.accounts.models import CandidateProfile
from apps.employers.models import EmployerProfile


def normalize_company_domain(raw_url_or_domain):
    """
    Normalizes domain strings (e.g. 'https://www.optum.com/en-us/' -> 'optum.com')
    to ensure robust deduplication and index lookups.
    """
    if not raw_url_or_domain:
        return ''
    cleaned = raw_url_or_domain.strip().lower()
    cleaned = re.sub(r'^https?://', '', cleaned)
    cleaned = re.sub(r'^www\.', '', cleaned)
    cleaned = cleaned.split('/')[0].split('?')[0].split('#')[0]
    return cleaned


class EmployerLead(models.Model):
    """
    Primary prospective healthcare employer record identified via the
    GrowthOS discovery engines, directory scrapers, or manual staff entry.
    """
    class IndustryVertical(models.TextChoices):
        # Healthcare Operations & Revenue Cycle
        MEDICAL_BILLING = 'MEDICAL_BILLING', 'Medical Billing & AR Follow-Up'
        MEDICAL_CODING = 'MEDICAL_CODING', 'Medical Coding & Auditing'
        RCM_SERVICES = 'RCM_SERVICES', 'Revenue Cycle Management (RCM)'
        HEALTHCARE_BPO = 'HEALTHCARE_BPO', 'Healthcare BPO & Outsourcing'
        HOSPITAL_CLINIC = 'HOSPITAL_CLINIC', 'Hospital, Network or Specialty Clinic'
        HEALTHCARE_OTHER = 'HEALTHCARE_OTHER', 'Other Healthcare Services'

        # Information Technology, Software & Cloud
        IT_SOFTWARE_DEV = 'IT_SOFTWARE_DEV', 'Software Engineering & Web Development'
        IT_CLOUD_DEVOPS = 'IT_CLOUD_DEVOPS', 'Cloud Infrastructure & DevOps'
        IT_CYBERSECURITY = 'IT_CYBERSECURITY', 'Cybersecurity & Data Protection'
        IT_DATA_AI = 'IT_DATA_AI', 'Data Engineering, Analytics & AI'
        IT_HELPDESK_SUPPORT = 'IT_HELPDESK_SUPPORT', 'IT Helpdesk & Systems Administration'
        IT_QA_TESTING = 'IT_QA_TESTING', 'QA Automation & Software Testing'

        # Finance, Accounting & Fintech
        FINANCE_ACCOUNTING = 'FINANCE_ACCOUNTING', 'Accounting, Bookkeeping & Audit'
        FINANCIAL_SERVICES = 'FINANCIAL_SERVICES', 'Fintech, Banking & Financial Analysis'

        # Operations, Customer Support & BPO
        BUSINESS_BPO = 'BUSINESS_BPO', 'Customer Support & Business Process Outsourcing'
        OTHER = 'OTHER', 'Other Specialized Services'

    class CompanySize(models.TextChoices):
        SIZE_1_10 = '1_10', '1-10 employees'
        SIZE_11_50 = '11_50', '11-50 employees'
        SIZE_51_200 = '51_200', '51-200 employees'
        SIZE_201_500 = '201_500', '201-500 employees'
        SIZE_501_PLUS = '501_PLUS', '500+ enterprise employees'

    class Source(models.TextChoices):
        DISCOVERY_ENGINE = 'DISCOVERY_ENGINE', 'Automated Discovery Engine'
        GOOGLE_SEARCH = 'GOOGLE_SEARCH', 'Google Search & Places API'
        HFMA_DIRECTORY = 'HFMA_DIRECTORY', 'HFMA / AAPC Directory'
        MANUAL_IMPORT = 'MANUAL_IMPORT', 'Manual Entry / Staff Import'
        REFERRAL = 'REFERRAL', 'Client / Talent Referral'

    class Status(models.TextChoices):
        LEAD = 'LEAD', 'Discovered Lead'
        QUALIFIED = 'QUALIFIED', 'Qualified Target'
        IN_PIPELINE = 'IN_PIPELINE', 'Active in CRM Pipeline'
        CONVERTED = 'CONVERTED', 'Converted to Active Employer'
        DISQUALIFIED = 'DISQUALIFIED', 'Disqualified / Unresponsive'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_name = models.CharField(max_length=200, db_index=True)
    domain = models.CharField(max_length=150, unique=True, db_index=True, help_text="Normalized clean domain e.g. optum.com")
    website = models.URLField(blank=True, help_text="Full website URL")
    country = models.CharField(max_length=100, default='United States')
    city = models.CharField(max_length=100, blank=True)

    industry_vertical = models.CharField(
        max_length=50,
        choices=IndustryVertical.choices,
        default=IndustryVertical.RCM_SERVICES
    )
    company_size = models.CharField(
        max_length=20,
        choices=CompanySize.choices,
        default=CompanySize.SIZE_11_50
    )
    careers_url = models.URLField(blank=True, help_text="Direct link to company careers or job board")
    source = models.CharField(
        max_length=30,
        choices=Source.choices,
        default=Source.MANUAL_IMPORT
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.LEAD,
        db_index=True
    )

    # GrowthOS Dual-Score Engine
    hiring_intent_score = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Strength of hiring demand from 0 to 100"
    )
    talent_fit_score = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Match fitness with active Kodafriq candidates from 0 to 100"
    )

    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_growth_leads',
        help_text="Kodafriq BD representative managing this account"
    )
    converted_employer_profile = models.OneToOneField(
        EmployerProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='growth_lead_origin',
        help_text="Associated official Kodafriq employer profile upon successful conversion"
    )
    notes = models.TextField(blank=True, help_text="Internal staff notes, intelligence summaries, or background")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-hiring_intent_score', '-talent_fit_score', '-created_at']
        verbose_name = "Employer Lead"
        verbose_name_plural = "Employer Leads"

    def __str__(self):
        return f"{self.company_name} ({self.domain}) [{self.get_status_display()}]"

    def save(self, *args, **kwargs):
        if not self.domain and self.website:
            self.domain = normalize_company_domain(self.website)
        elif self.domain:
            self.domain = normalize_company_domain(self.domain)
        if not self.website and self.domain:
            self.website = f"https://{self.domain}"
        super().save(*args, **kwargs)

    @property
    def primary_contact(self):
        return self.contacts.filter(is_primary=True).first() or self.contacts.first()

    @property
    def active_vacancies_count(self):
        return self.vacancies.filter(is_active=True).count()

    @property
    def priority_tier(self):
        """
        Calculates priority quadrant based on Hiring Intent and Talent Fit.
        Tier 1: High Intent (>=60) + High Fit (>=60) -> Prime Outbound Target
        Tier 2: High Intent (>=60) + Low Fit (<60)  -> Active hiring but need to recruit/train
        Tier 3: Low Intent (<60)  + High Fit (>=60) -> Strong talent fit for passive nurture
        Tier 4: Low Intent (<60)  + Low Fit (<60)   -> Unqualified / Archive
        """
        if self.hiring_intent_score >= 60 and self.talent_fit_score >= 60:
            return 1
        elif self.hiring_intent_score >= 60 and self.talent_fit_score < 60:
            return 2
        elif self.hiring_intent_score < 60 and self.talent_fit_score >= 60:
            return 3
        return 4

    @property
    def priority_tier_display(self):
        tiers = {
            1: "🔥 Tier 1: Prime Target (High Intent & High Fit)",
            2: "🟡 Tier 2: Active Hiring (Skill Gap)",
            3: "🔵 Tier 3: Passive Nurture (High Fit)",
            4: "⚪ Tier 4: Low Priority",
        }
        return tiers.get(self.priority_tier, "Unclassified")

    def recalculate_intent_score(self):
        """
        Dynamically updates Hiring Intent Score based on vacancy volume,
        persistent listings (>30 days), and decision-maker presence.
        """
        score = 0
        active_vacancies = self.vacancies.filter(is_active=True)
        count = active_vacancies.count()

        # Vacancy volume (up to 40 pts)
        if count >= 5:
            score += 40
        elif count >= 3:
            score += 30
        elif count >= 1:
            score += 20

        # Persistent vacancies (>30 days = 30 pts)
        persistent_count = active_vacancies.filter(is_persistent=True).count()
        if persistent_count > 0:
            score += 30

        # Decision-maker contact identified with valid email (20 pts)
        has_verified_contact = self.contacts.filter(email__gt='', verification_status='VERIFIED_VALID').exists()
        has_any_contact = self.contacts.filter(email__gt='').exists()
        if has_verified_contact:
            score += 20
        elif has_any_contact:
            score += 10

        # Careers URL documented (10 pts)
        if self.careers_url:
            score += 10

        self.hiring_intent_score = min(100, score)
        self.save(update_fields=['hiring_intent_score'])
        return self.hiring_intent_score


class LeadContact(models.Model):
    """
    Executive or decision-maker contact at the prospective employer organization.
    """
    class VerificationStatus(models.TextChoices):
        UNVERIFIED = 'UNVERIFIED', 'Unverified'
        VERIFIED_VALID = 'VERIFIED_VALID', 'Verified Valid'
        BOUNCED = 'BOUNCED', 'Bounced / Invalid'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(EmployerLead, on_delete=models.CASCADE, related_name='contacts')
    full_name = models.CharField(max_length=150)
    job_title = models.CharField(max_length=150, blank=True, help_text="e.g. VP of Revenue Cycle, Head of Talent")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    linkedin_url = models.URLField(blank=True)
    is_primary = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'full_name']
        verbose_name = "Lead Contact"
        verbose_name_plural = "Lead Contacts"

    def __str__(self):
        title = f" ({self.job_title})" if self.job_title else ""
        return f"{self.full_name}{title} @ {self.lead.company_name}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            LeadContact.objects.filter(lead=self.lead, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class HiringSignal(models.Model):
    """
    Detected recruitment vacancy or active hiring activity indicating demand.
    """
    class RoleCategory(models.TextChoices):
        # Healthcare Operations
        MEDICAL_CODER = 'MEDICAL_CODER', 'Medical Coder (Inpatient/Outpatient)'
        MEDICAL_BILLER = 'MEDICAL_BILLER', 'Medical Biller & AR Specialist'
        RCM_SPECIALIST = 'RCM_SPECIALIST', 'Revenue Cycle Specialist / Auditor'
        AR_SPECIALIST = 'AR_SPECIALIST', 'Denials & Accounts Receivable'
        AUDITOR = 'AUDITOR', 'DRG / Clinical Documentation Auditor'

        # Information Technology & Engineering
        SOFTWARE_ENGINEER = 'SOFTWARE_ENGINEER', 'Software Engineer (Frontend/Backend/Fullstack)'
        DEVOPS_CLOUD = 'DEVOPS_CLOUD', 'DevOps, SRE & Cloud Architect'
        CYBERSECURITY = 'CYBERSECURITY', 'Cybersecurity Analyst & SOC'
        DATA_AI = 'DATA_AI', 'Data Analyst / Data Engineer / AI'
        IT_SUPPORT = 'IT_SUPPORT', 'IT Support & Systems Administrator'
        QA_ENGINEER = 'QA_ENGINEER', 'QA & Test Automation Engineer'

        # Finance & Business Operations
        ACCOUNTANT = 'ACCOUNTANT', 'Accountant, Bookkeeper & Controller'
        FINANCIAL_ANALYST = 'FINANCIAL_ANALYST', 'Financial Analyst & Risk Management'
        CUSTOMER_SUPPORT = 'CUSTOMER_SUPPORT', 'Customer Operations & Technical Support'
        OTHER = 'OTHER', 'Other Operational Role'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(EmployerLead, on_delete=models.CASCADE, related_name='vacancies')
    job_title = models.CharField(max_length=200)
    role_category = models.CharField(
        max_length=40,
        choices=RoleCategory.choices,
        default=RoleCategory.MEDICAL_BILLER
    )
    job_url = models.URLField(blank=True, help_text="Direct link to vacancy posting")
    raw_description = models.TextField(blank=True, help_text="Scraped job description text or summary")
    extracted_skills = models.JSONField(default=list, blank=True, help_text="Keywords, medical coding systems, software required")
    date_detected = models.DateField(default=timezone.now)
    days_open = models.PositiveIntegerField(default=1, help_text="Days this role has been actively advertised")
    is_persistent = models.BooleanField(default=False, help_text="True if role has remained open for >30 days")
    is_active = models.BooleanField(default=True, help_text="Whether this vacancy is currently actively hiring")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_active', '-days_open', '-date_detected']
        verbose_name = "Hiring Signal / Vacancy"
        verbose_name_plural = "Hiring Signals & Vacancies"

    def __str__(self):
        status = "Active" if self.is_active else "Closed"
        return f"{self.job_title} @ {self.lead.company_name} ({status})"

    def save(self, *args, **kwargs):
        if self.days_open >= 30:
            self.is_persistent = True
        super().save(*args, **kwargs)


class TalentReverseMatch(models.Model):
    """
    Reverse match link between a registered Kodafriq candidate and an
    employer lead's open vacancy or organizational requirement.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(EmployerLead, on_delete=models.CASCADE, related_name='talent_matches')
    vacancy = models.ForeignKey(HiringSignal, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidate_matches')
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='growth_matches')
    match_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    matched_skills = models.JSONField(default=list, blank=True)
    matching_rationale = models.TextField(blank=True, help_text="Why this candidate is an optimal match for this employer")
    is_shortlisted = models.BooleanField(default=False, help_text="Marked to include in candidate pitch shortlist")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-match_score', '-created_at']
        unique_together = ('lead', 'candidate', 'vacancy')
        verbose_name = "Talent Reverse Match"
        verbose_name_plural = "Talent Reverse Matches"

    def __str__(self):
        cand_name = self.candidate.full_name or "Candidate"
        return f"{cand_name} -> {self.lead.company_name} ({self.match_score}%)"


class OutreachMessage(models.Model):
    """
    Generated personalized communication drafted for an employer lead.
    Subject to human-in-the-loop staff review before dispatch.
    """
    class Channel(models.TextChoices):
        EMAIL = 'EMAIL', 'Email Outreach'
        LINKEDIN = 'LINKEDIN', 'LinkedIn InMail / Message'

    class Status(models.TextChoices):
        DRAFT_PENDING_APPROVAL = 'DRAFT_PENDING_APPROVAL', 'Draft (Pending Review)'
        APPROVED = 'APPROVED', 'Approved for Sending'
        SENT = 'SENT', 'Dispatched / Sent'
        REPLIED = 'REPLIED', 'Reply Received'
        REJECTED = 'REJECTED', 'Rejected by Reviewer'
        BOUNCED = 'BOUNCED', 'Bounced'

    class ReplyClassification(models.TextChoices):
        POSITIVE_MEETING = 'POSITIVE_MEETING', 'Positive: Meeting / Call Requested'
        INFO_REQUESTED = 'INFO_REQUESTED', 'Information / Candidate Shortlist Requested'
        NOT_INTERESTED = 'NOT_INTERESTED', 'Not Interested Currently'
        UNSUBSCRIBE = 'UNSUBSCRIBE', 'Unsubscribe / Do Not Contact'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(EmployerLead, on_delete=models.CASCADE, related_name='outreaches')
    contact = models.ForeignKey(LeadContact, on_delete=models.SET_NULL, null=True, blank=True, related_name='outreaches')
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.EMAIL)
    sequence_step = models.PositiveIntegerField(default=1, help_text="Cadence sequence step: 1=Initial Pitch, 2=Follow-Up, 3=Final Touch")
    subject = models.CharField(max_length=255)
    body_text = models.TextField()

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT_PENDING_APPROVAL,
        db_index=True
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_growth_outreaches'
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    reply_classification = models.CharField(
        max_length=30,
        choices=ReplyClassification.choices,
        blank=True
    )
    reply_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Outreach Message"
        verbose_name_plural = "Outreach Messages"

    def __str__(self):
        return f"{self.channel} to {self.lead.company_name}: '{self.subject[:40]}...' [{self.get_status_display()}]"


class CRMOpportunity(models.Model):
    """
    Sales opportunity record tracking an employer lead across the 10-stage
    acquisition pipeline through to contract and placement.
    """
    class Stage(models.TextChoices):
        STAGE_1_DISCOVERED = '1_DISCOVERED', '1. Discovered'
        STAGE_2_QUALIFIED = '2_QUALIFIED', '2. Qualified Target'
        STAGE_3_HIRING_SIGNAL = '3_HIRING_SIGNAL', '3. Hiring Signal Detected'
        STAGE_4_CONTACT_IDENTIFIED = '4_CONTACT_IDENTIFIED', '4. Decision Maker Identified'
        STAGE_5_OUTREACH_SENT = '5_OUTREACH_SENT', '5. Outreach Sent'
        STAGE_6_REPLY_RECEIVED = '6_REPLY_RECEIVED', '6. Response Received'
        STAGE_7_MEETING_SCHEDULED = '7_MEETING_SCHEDULED', '7. Meeting Scheduled'
        STAGE_8_SHORTLIST_DELIVERED = '8_SHORTLIST_DELIVERED', '8. Talent Shortlist Delivered'
        STAGE_9_INTERVIEWS = '9_INTERVIEWS', '9. Interviews in Progress'
        STAGE_10_PLACEMENT_WON = '10_PLACEMENT_WON', '10. Placement Won (Success)'
        CLOSED_LOST = 'CLOSED_LOST', 'Closed Lost'

    class Priority(models.TextChoices):
        URGENT = 'URGENT', 'Urgent Priority'
        HIGH = 'HIGH', 'High Priority'
        MEDIUM = 'MEDIUM', 'Medium Priority'
        LOW = 'LOW', 'Low Priority'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.OneToOneField(EmployerLead, on_delete=models.CASCADE, related_name='crm_opportunity')
    stage = models.CharField(
        max_length=35,
        choices=Stage.choices,
        default=Stage.STAGE_1_DISCOVERED,
        db_index=True
    )
    target_roles_count = models.PositiveIntegerField(default=1, help_text="Number of clinical roles the employer needs")
    estimated_monthly_deal_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Estimated gross contract value in USD/month"
    )
    currency = models.CharField(max_length=10, default='USD')
    priority = models.CharField(max_length=15, choices=Priority.choices, default=Priority.HIGH)
    win_probability_percent = models.PositiveIntegerField(default=20)
    next_follow_up_date = models.DateField(null=True, blank=True)
    lost_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['stage', '-estimated_monthly_deal_value', '-updated_at']
        verbose_name = "CRM Opportunity"
        verbose_name_plural = "CRM Opportunities"

    def __str__(self):
        return f"{self.lead.company_name} - {self.get_stage_display()} (${self.estimated_monthly_deal_value}/mo)"


class CRMActivity(models.Model):
    """
    Chronological activity and interaction log for an employer lead.
    """
    class ActivityType(models.TextChoices):
        NOTE = 'NOTE', 'Internal Note'
        CALL = 'CALL', 'Phone Call'
        EMAIL_SENT = 'EMAIL_SENT', 'Email Sent'
        MEETING = 'MEETING', 'Discovery Meeting / Call'
        STAGE_CHANGE = 'STAGE_CHANGE', 'Pipeline Stage Transition'
        SHORTLIST_SENT = 'SHORTLIST_SENT', 'Talent Shortlist Delivered'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(EmployerLead, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=25, choices=ActivityType.choices, default=ActivityType.NOTE)
    summary = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "CRM Activity Log"
        verbose_name_plural = "CRM Activity Logs"

    def __str__(self):
        return f"[{self.get_activity_type_display()}] {self.summary} ({self.created_at.strftime('%Y-%m-%d')})"

