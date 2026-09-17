from django import forms
from apps.skills.models import CandidateSkill, Skill

class CandidateSkillAddForm(forms.ModelForm):
    class Meta:
        model = CandidateSkill
        fields = ('skill', 'proficiency', 'years_experience', 'evidence_file', 'evidence_notes')
        widgets = {
            'skill': forms.Select(attrs={'class': 'kf-input'}),
            'proficiency': forms.Select(attrs={'class': 'kf-input'}),
            'years_experience': forms.NumberInput(attrs={'class': 'kf-input', 'min': 0, 'max': 40}),
            'evidence_file': forms.FileInput(attrs={'class': 'kf-file-input'}),
            'evidence_notes': forms.Textarea(attrs={'class': 'kf-input', 'rows': 2, 'placeholder': 'Add details about your audit accuracy or experience with this standard...'}),
        }

    def __init__(self, *args, candidate=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidate = candidate
        # Only show active skills that the candidate has not added yet
        if candidate:
            existing_skill_ids = candidate.skills.values_list('skill_id', flat=True)
            self.fields['skill'].queryset = Skill.objects.filter(is_active=True).exclude(id__in=existing_skill_ids)
