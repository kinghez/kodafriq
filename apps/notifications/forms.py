from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .models import NotificationBroadcast

User = get_user_model()


class BroadcastComposeForm(forms.ModelForm):
    target_single_user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('username'),
        required=False,
        label="Select Single Recipient",
        help_text="Target a specific user by username or email"
    )
    target_multiple_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('username'),
        required=False,
        label="Select Multiple Recipients",
        help_text="Choose one or more platform users"
    )

    class Meta:
        model = NotificationBroadcast
        fields = [
            'channel',
            'target_type',
            'target_group',
            'notification_type',
            'title',
            'message',
            'action_url',
            'action_button_text',
        ]
        widgets = {
            'channel': forms.Select(attrs={'class': 'kf-form-select', 'id': 'id_channel'}),
            'target_type': forms.Select(attrs={'class': 'kf-form-select', 'id': 'id_target_type'}),
            'target_group': forms.Select(attrs={'class': 'kf-form-select', 'id': 'id_target_group'}),
            'notification_type': forms.Select(attrs={'class': 'kf-form-select', 'id': 'id_notification_type'}),
            'title': forms.TextInput(attrs={
                'class': 'kf-form-input',
                'placeholder': 'e.g., Important Security Update or New Clinical Requisition Alert',
                'id': 'id_title'
            }),
            'message': forms.Textarea(attrs={
                'class': 'kf-form-input',
                'rows': 5,
                'placeholder': 'Compose your broadcast notification or email message...',
                'id': 'id_message'
            }),
            'action_url': forms.TextInput(attrs={
                'class': 'kf-form-input',
                'placeholder': 'e.g. /training/ or https://kodafriq.com/opportunity/42',
                'id': 'id_action_url'
            }),
            'action_button_text': forms.TextInput(attrs={
                'class': 'kf-form-input',
                'placeholder': 'e.g. View Details / Take Action',
                'id': 'id_action_button_text'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['target_group'].queryset = Group.objects.all().order_by('name')
        self.fields['target_group'].empty_label = "— Choose a Django Group —"
        self.fields['target_single_user'].empty_label = "— Select User (Username / Email) —"
        
        # Customize user display label
        self.fields['target_single_user'].label_from_instance = lambda u: f"{u.username} — {u.get_full_name() or u.username} ({u.email or 'no email'}) [{u.get_role_display() if hasattr(u, 'get_role_display') else u.role}]"
        self.fields['target_multiple_users'].label_from_instance = lambda u: f"{u.username} — {u.get_full_name() or u.username} ({u.email or 'no email'}) [{u.get_role_display() if hasattr(u, 'get_role_display') else u.role}]"

    def clean(self):
        cleaned_data = super().clean()
        target_type = cleaned_data.get('target_type')

        if target_type == NotificationBroadcast.TargetType.SINGLE_USER:
            if not cleaned_data.get('target_single_user'):
                self.add_error('target_single_user', 'Please select a recipient user.')

        elif target_type == NotificationBroadcast.TargetType.MULTIPLE_USERS:
            if not cleaned_data.get('target_multiple_users'):
                self.add_error('target_multiple_users', 'Please select at least one recipient user.')

        elif target_type == NotificationBroadcast.TargetType.GROUP:
            if not cleaned_data.get('target_group'):
                self.add_error('target_group', 'Please select a target Django group.')

        return cleaned_data
