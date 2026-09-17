from django import forms
from apps.employers.models import Job, JobRequiredSkill, Application, Shortlist
from apps.skills.models import Skill

class JobForm(forms.ModelForm):
    required_skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.filter(is_active=True).select_related('category'),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'kf-skill-checkbox'}),
        help_text='Select mandatory and preferred clinical competencies'
    )

    class Meta:
        model = Job
        fields = [
            'title',
            'job_type',
            'location',
            'min_years_experience',
            'min_score_required',
            'status',
            'description',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Senior Inpatient Coder (ICD-10-CM / DRG)'
            }),
            'job_type': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Remote / Flexible, Accra, Lagos'
            }),
            'min_years_experience': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 30
            }),
            'min_score_required': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 100,
                'step': '0.5'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Detail key clinical responsibilities, EHR experience, charts per day, and quality benchmarks...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['required_skills'].initial = self.instance.required_skills.values_list('skill_id', flat=True)

    def save(self, commit=True):
        job = super().save(commit=commit)
        if commit:
            selected_skills = self.cleaned_data.get('required_skills', [])
            # Update required skills
            existing_skill_ids = set(job.required_skills.values_list('skill_id', flat=True))
            new_skill_ids = set(s.id for s in selected_skills)

            # Remove deselected
            job.required_skills.exclude(skill_id__in=new_skill_ids).delete()

            # Add newly selected
            to_create = [
                JobRequiredSkill(job=job, skill=skill, is_mandatory=True)
                for skill in selected_skills if skill.id not in existing_skill_ids
            ]
            if to_create:
                JobRequiredSkill.objects.bulk_create(to_create)

        return job


class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['cover_note']
        widgets = {
            'cover_note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Introduce yourself, your clinical certifications (CPC, CCS, RHIA), and your availability...'
            })
        }


class ApplicationStatusForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control form-control-sm'})
        }


class ShortlistNoteForm(forms.ModelForm):
    class Meta:
        model = Shortlist
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add private evaluation notes about this candidate...'
            })
        }
