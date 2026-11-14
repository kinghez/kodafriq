from django import forms
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
            'company_name', 'domain', 'website', 'country', 'city',
            'industry_vertical', 'company_size', 'careers_url', 'source',
            'status', 'assigned_staff', 'notes'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'placeholder': 'e.g. MedCare Billing Solutions'}),
            'domain': forms.TextInput(attrs={'placeholder': 'e.g. medcarebilling.com'}),
            'website': forms.URLInput(attrs={'placeholder': 'https://medcarebilling.com'}),
            'careers_url': forms.URLInput(attrs={'placeholder': 'https://medcarebilling.com/careers'}),
            'city': forms.TextInput(attrs={'placeholder': 'e.g. Dallas, TX or Remote'}),
            'country': forms.TextInput(attrs={'placeholder': 'United States'}),
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
