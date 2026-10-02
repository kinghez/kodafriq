from decimal import Decimal
from django import forms
from .models import Contract, Timesheet, TimesheetEntry, Milestone, DisputeCase
from apps.accounts.models import CandidateProfile
from apps.employers.models import Job


class ContractCreateForm(forms.ModelForm):
    candidate = forms.ModelChoiceField(
        queryset=CandidateProfile.objects.select_related('user').all(),
        widget=forms.Select(attrs={'class': 'kf-input'})
    )
    job = forms.ModelChoiceField(
        queryset=Job.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'kf-input'})
    )

    class Meta:
        model = Contract
        fields = [
            'candidate', 'job', 'title', 'contract_type', 'disbursement_mode',
            'rate_per_hour', 'weekly_hour_limit', 'total_milestone_amount',
            'start_date', 'end_date', 'scope_of_work'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g., Inpatient Medical Coder - Remote'}),
            'contract_type': forms.Select(attrs={'class': 'kf-input', 'id': 'id_contract_type'}),
            'disbursement_mode': forms.Select(attrs={'class': 'kf-input'}),
            'rate_per_hour': forms.NumberInput(attrs={'class': 'kf-input', 'step': '0.50', 'id': 'id_rate_per_hour'}),
            'weekly_hour_limit': forms.NumberInput(attrs={'class': 'kf-input', 'min': 1, 'max': 168}),
            'total_milestone_amount': forms.NumberInput(attrs={'class': 'kf-input', 'step': '1.00', 'id': 'id_total_milestone_amount'}),
            'start_date': forms.DateInput(attrs={'class': 'kf-input', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'kf-input', 'type': 'date'}),
            'scope_of_work': forms.Textarea(attrs={'class': 'kf-input', 'rows': 4, 'placeholder': 'Key clinical responsibilities, specialty guidelines (e.g. ICD-10-CM/PCS), expectations...'}),
        }

    def __init__(self, *args, employer=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employer:
            self.fields['job'].queryset = Job.objects.filter(employer=employer)
            self.fields['job'].empty_label = "-- Direct Hire / No Specific Job Posting --"

    def clean(self):
        cleaned_data = super().clean()
        ctype = cleaned_data.get('contract_type')
        rate = cleaned_data.get('rate_per_hour')
        milestone_amt = cleaned_data.get('total_milestone_amount')

        if ctype == Contract.ContractType.HOURLY and (not rate or rate <= Decimal('0.00')):
            self.add_error('rate_per_hour', 'Hourly contracts require a positive hourly rate.')
        elif ctype == Contract.ContractType.MILESTONE and (not milestone_amt or milestone_amt <= Decimal('0.00')):
            self.add_error('total_milestone_amount', 'Milestone contracts require a valid deliverable amount.')
        return cleaned_data


class TimesheetEntryForm(forms.ModelForm):
    class Meta:
        model = TimesheetEntry
        fields = ['hours_worked', 'charts_coded_count', 'work_description']
        widgets = {
            'hours_worked': forms.NumberInput(attrs={'class': 'kf-input kf-hours-input', 'step': '0.25', 'min': '0', 'max': '24'}),
            'charts_coded_count': forms.NumberInput(attrs={'class': 'kf-input kf-charts-input', 'min': '0'}),
            'work_description': forms.Textarea(attrs={'class': 'kf-input kf-desc-input', 'rows': 2, 'placeholder': 'e.g., Coded 25 outpatient charts, resolved 4 denial queries'}),
        }


class TimesheetSubmitForm(forms.ModelForm):
    class Meta:
        model = Timesheet
        fields = ['candidate_notes']
        widgets = {
            'candidate_notes': forms.Textarea(attrs={'class': 'kf-input', 'rows': 3, 'placeholder': 'Optional summary of this week accomplishments or clinical notes for the employer...'}),
        }


class TimesheetReviewForm(forms.Form):
    ACTION_CHOICES = [
        ('approve', 'Approve & Confirm Timesheet'),
        ('dispute', 'Dispute / Request Adjustment'),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.RadioSelect)
    employer_review_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'kf-input', 'rows': 3, 'placeholder': 'Feedback or dispute rationale for the candidate...'})
    )


class MilestoneSubmitForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = ['submission_notes', 'deliverable_file']
        widgets = {
            'submission_notes': forms.Textarea(attrs={'class': 'kf-input', 'rows': 4, 'placeholder': 'Summary of deliverables completed, clinical audit results, or links to shared records...'}),
            'deliverable_file': forms.FileInput(attrs={'class': 'kf-input'}),
        }


class DisputeCaseForm(forms.ModelForm):
    class Meta:
        model = DisputeCase
        fields = ['reason']
        widgets = {
            'reason': forms.Textarea(attrs={'class': 'kf-input', 'rows': 4, 'placeholder': 'Please specify the exact nature of the disagreement so our clinical mediation team can investigate...'}),
        }


class StaffDisputeAdjudicateForm(forms.Form):
    DECISION_CHOICES = [
        ('FAVOR_CANDIDATE', 'Rule in Favor of Candidate (Release Escrow Funds)'),
        ('FAVOR_EMPLOYER', 'Rule in Favor of Employer (Cancel / Void Obligation)'),
        ('COMPROMISE', 'Mediated Compromise (Adjust Hours or Deliverable Amount)'),
    ]
    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'kf-radio-decision'})
    )
    adjusted_hours = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. 32.00', 'step': '0.50'})
    )
    adjusted_amount = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. 850.00', 'step': '1.00'})
    )
    mediator_notes = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': 'kf-input', 'rows': 4, 'placeholder': 'Provide detailed mediation findings, clinical timecard audit notes, and final ruling rationale...'})
    )
