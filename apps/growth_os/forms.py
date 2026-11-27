from decimal import Decimal
from django import forms
from apps.accounts.models import CandidateProfile
from apps.contracts.models import Contract
from .models import EmployerLead, LeadContact, HiringSignal, CRMActivity, CRMOpportunity, OutreachMessage, normalize_company_domain


class StyledModelForm(forms.ModelForm):
    """Base form that injects Kodafriq design system styles into all widgets."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.update({'style': 'accent-color: #006fe6; width: 18px; height: 18px; cursor: pointer;'})
            elif isinstance(widget, forms.Select):
                widget.attrs.update({
                    'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; background: #ffffff; outline: none; box-sizing: border-box;'
                })
            elif isinstance(widget, forms.Textarea):
                widget.attrs.update({
                    'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; background: #ffffff; outline: none; box-sizing: border-box; font-family: inherit;',
                    'rows': 4
                })
            else:
                widget.attrs.update({
                    'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; background: #ffffff; outline: none; box-sizing: border-box;'
                })


class EmployerLeadForm(StyledModelForm):
    class Meta:
        model = EmployerLead
        fields = [
            'company_name', 'domain', 'website', 'phone', 'contact_email',
            'country', 'city', 'industry_vertical', 'company_size',
            'careers_url', 'source', 'status', 'assigned_staff', 'notes'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'placeholder': 'e.g. MedCare Billing Solutions'}),
            'domain': forms.TextInput(attrs={'placeholder': 'e.g. medcarebilling.com'}),
            'website': forms.URLInput(attrs={'placeholder': 'https://medcarebilling.com'}),
            'phone': forms.TextInput(attrs={'placeholder': '+1 555-234-5678 / +44 20 7946 0000'}),
            'contact_email': forms.EmailInput(attrs={'placeholder': 'careers@medcarebilling.com'}),
            'careers_url': forms.URLInput(attrs={'placeholder': 'https://medcarebilling.com/careers'}),
            'city': forms.TextInput(attrs={'placeholder': 'e.g. London, UK or Dallas, TX'}),
            'country': forms.TextInput(attrs={'placeholder': 'e.g. United Kingdom, Canada, United States'}),
        }

    def clean_domain(self):
        domain = self.cleaned_data.get('domain', '').strip()
        website = self.cleaned_data.get('website', '').strip()
        if not domain and website:
            domain = normalize_company_domain(website)
        elif domain:
            domain = normalize_company_domain(domain)

        # Check domain uniqueness excluding self
        qs = EmployerLead.objects.filter(domain=domain)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"An employer lead with domain '{domain}' already exists.")
        return domain


class LeadContactForm(StyledModelForm):
    class Meta:
        model = LeadContact
        fields = ['full_name', 'job_title', 'email', 'phone', 'linkedin_url', 'is_primary', 'verification_status']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'e.g. Sarah Jenkins'}),
            'job_title': forms.TextInput(attrs={'placeholder': 'e.g. VP of Revenue Cycle Operations'}),
            'email': forms.EmailInput(attrs={'placeholder': 's.jenkins@company.com'}),
            'phone': forms.TextInput(attrs={'placeholder': '+1 (555) 234-5678'}),
            'linkedin_url': forms.URLInput(attrs={'placeholder': 'https://linkedin.com/in/sarahjenkins'}),
        }


class HiringSignalForm(StyledModelForm):
    class Meta:
        model = HiringSignal
        fields = ['job_title', 'role_category', 'job_url', 'days_open', 'is_active', 'raw_description']
        widgets = {
            'job_title': forms.TextInput(attrs={'placeholder': 'e.g. Senior Inpatient Medical Coder'}),
            'job_url': forms.URLInput(attrs={'placeholder': 'https://company.com/jobs/senior-coder'}),
            'days_open': forms.NumberInput(attrs={'min': 1}),
            'raw_description': forms.Textarea(attrs={'placeholder': 'Paste job summary, core qualifications, ICD-10/CPT requirements...'}),
        }


class CRMActivityForm(StyledModelForm):
    class Meta:
        model = CRMActivity
        fields = ['activity_type', 'summary', 'details']
        widgets = {
            'summary': forms.TextInput(attrs={'placeholder': 'e.g. Discovery call with Head of Talent regarding 5 open billing roles'}),
            'details': forms.Textarea(attrs={'placeholder': 'Key takeaways, next steps, required rate ranges, feedback...'}),
        }


class CRMOpportunityForm(StyledModelForm):
    class Meta:
        model = CRMOpportunity
        fields = [
            'stage', 'target_roles_count', 'estimated_monthly_deal_value',
            'currency', 'priority', 'win_probability_percent',
            'next_follow_up_date', 'lost_reason'
        ]
        widgets = {
            'target_roles_count': forms.NumberInput(attrs={'min': 1}),
            'estimated_monthly_deal_value': forms.NumberInput(attrs={'step': '100', 'min': 0, 'placeholder': 'e.g. 8500.00'}),
            'win_probability_percent': forms.NumberInput(attrs={'min': 0, 'max': 100, 'placeholder': 'e.g. 40'}),
            'next_follow_up_date': forms.DateInput(attrs={'type': 'date'}),
            'lost_reason': forms.TextInput(attrs={'placeholder': 'Reason if lost / archived'}),
        }


class OutreachMessageForm(StyledModelForm):
    class Meta:
        model = OutreachMessage
        fields = ['channel', 'sequence_step', 'subject', 'body_text', 'status', 'contact']
        widgets = {
            'subject': forms.TextInput(attrs={'placeholder': 'Subject line...'}),
            'body_text': forms.Textarea(attrs={'rows': 10, 'placeholder': 'Personalized outreach message copy...'}),
        }


class OutreachGenerateForm(forms.Form):
    channel = forms.ChoiceField(
        choices=OutreachMessage.Channel.choices,
        initial=OutreachMessage.Channel.EMAIL,
        widget=forms.Select(attrs={
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; background: #ffffff; outline: none; box-sizing: border-box;'
        })
    )
    sequence_step = forms.ChoiceField(
        choices=[
            (1, 'Step 1: Initial Hook & Talent Shortlist Pitch'),
            (2, 'Step 2: Value-Add & Risk Reversal Follow-Up (Day 4)'),
            (3, 'Step 3: Closing the Loop / Break-Up Touch (Day 8)')
        ],
        initial=1,
        widget=forms.Select(attrs={
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; background: #ffffff; outline: none; box-sizing: border-box;'
        })
    )
    contact_id = forms.UUIDField(
        required=False,
        widget=forms.HiddenInput()
    )


class PublicShortlistInquiryForm(forms.Form):
    """Employer-facing inquiry form on the public candidate shortlist page."""
    full_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'Your Full Name (e.g. Jane Doe)',
            'style': 'width: 100%; padding: 12px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    work_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Work Email (e.g. j.doe@company.com)',
            'style': 'width: 100%; padding: 12px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    phone = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Phone Number (optional)',
            'style': 'width: 100%; padding: 12px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    requested_roles = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Role(s) of interest (e.g. Senior Medical Coder, Python Developer)',
            'style': 'width: 100%; padding: 12px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Specific questions, preferred start dates, or interview time slots...',
            'style': 'width: 100%; padding: 12px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box; font-family: inherit;'
        })
    )


class QuickActivityForm(StyledModelForm):
    """Activity logging form that optionally allows scheduling next follow-up date."""
    next_follow_up_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; background: #ffffff; outline: none; box-sizing: border-box;'
        })
    )

    class Meta:
        model = CRMActivity
        fields = ['activity_type', 'summary', 'details']
        widgets = {
            'summary': forms.TextInput(attrs={'placeholder': 'e.g. Discovery meeting with VP Operations regarding 3 coders'}),
            'details': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Discussion points, candidate feedback, agreed action items...'}),
        }


class LeadConversionForm(forms.Form):
    """
    1-Click Conversion Form:
    Converts EmployerLead into official Kodafriq EmployerProfile, links User account,
    and optionally drafts an initial Contract with a matched candidate.
    """
    # Employer User & Organization Details
    email = forms.EmailField(
        label="Employer Account Email",
        widget=forms.EmailInput(attrs={
            'placeholder': 'e.g. billing-director@company.com',
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    company_name = forms.CharField(
        label="Company Name",
        max_length=200,
        widget=forms.TextInput(attrs={
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    contact_person_name = forms.CharField(
        label="Primary Contact Person",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. Sarah Jenkins',
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    contact_person_title = forms.CharField(
        label="Contact Person Job Title",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. VP of Revenue Cycle Operations',
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    phone = forms.CharField(
        label="Phone Number",
        max_length=40,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '+1 (555) 234-5678',
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    website = forms.URLField(
        label="Company Website",
        required=False,
        widget=forms.URLInput(attrs={
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    country = forms.CharField(
        label="Country",
        required=False,
        initial="United States",
        widget=forms.TextInput(attrs={
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    city = forms.CharField(
        label="City / Headquarters",
        required=False,
        widget=forms.TextInput(attrs={
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    industry = forms.CharField(
        label="Industry Sector",
        required=False,
        widget=forms.TextInput(attrs={
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )

    # Initial Placement Contract Provisioning
    create_contract = forms.BooleanField(
        label="Draft Initial Placement Contract Now",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'style': 'accent-color: #006fe6; width: 18px; height: 18px; cursor: pointer;'
        })
    )
    candidate_id = forms.CharField(
        label="Selected Candidate",
        max_length=64,
        required=False,
        widget=forms.Select(attrs={
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; background: #ffffff; outline: none; box-sizing: border-box;'
        })
    )
    contract_title = forms.CharField(
        label="Contract Title / Role",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. Remote Senior Inpatient Medical Coder',
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    contract_type = forms.ChoiceField(
        label="Contract Type",
        choices=Contract.ContractType.choices,
        initial=Contract.ContractType.HOURLY,
        required=False,
        widget=forms.Select(attrs={
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; background: #ffffff; outline: none; box-sizing: border-box;'
        })
    )
    rate_per_hour = forms.DecimalField(
        label="Candidate Net Hourly Rate ($ USD)",
        max_digits=10,
        decimal_places=2,
        initial=Decimal('25.00'),
        required=False,
        widget=forms.NumberInput(attrs={
            'step': '1.00',
            'min': '0.00',
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    weekly_hour_limit = forms.IntegerField(
        label="Weekly Billable Hours Limit",
        initial=40,
        required=False,
        widget=forms.NumberInput(attrs={
            'min': '1',
            'max': '80',
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    total_milestone_amount = forms.DecimalField(
        label="Fixed Milestone Amount ($ USD - if milestone contract)",
        max_digits=10,
        decimal_places=2,
        initial=Decimal('0.00'),
        required=False,
        widget=forms.NumberInput(attrs={
            'step': '50.00',
            'min': '0.00',
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box;'
        })
    )
    scope_of_work = forms.CharField(
        label="Scope of Work & Deliverables",
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Outline specific responsibilities, expected daily chart volume, EHR systems (Epic/Cerner), communication channels...',
            'style': 'width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 0.9rem; color: #091e42; outline: none; box-sizing: border-box; font-family: inherit;'
        })
    )

    def __init__(self, *args, candidate_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if candidate_choices is not None:
            self.fields['candidate_id'].widget.choices = candidate_choices
