from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, CandidateProfile, EmployerProfile, WorkExperience, CandidateCertification
from apps.core.utils.geo_device import AFRICAN_AND_GLOBAL_COUNTRIES

class KodafriqLoginForm(forms.Form):
    username_or_email = forms.CharField(
        label="Email Address",
        widget=forms.TextInput(attrs={
            'class': 'kf-input',
            'placeholder': 'Enter your email address',
            'autocomplete': 'username',
            'required': True,
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'kf-input',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
            'required': True,
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'kf-checkbox'})
    )

    def clean(self):
        cleaned_data = super().clean()
        login_input = cleaned_data.get('username_or_email', '').strip()
        password = cleaned_data.get('password')

        if login_input and password:
            # Check if login_input is email or username
            user = None
            if '@' in login_input:
                try:
                    user_obj = User.objects.get(email__iexact=login_input)
                    user = authenticate(username=user_obj.username, password=password)
                except (User.DoesNotExist, User.MultipleObjectsReturned):
                    pass
            
            if not user:
                user = authenticate(username=login_input, password=password)

            if not user:
                raise forms.ValidationError("Invalid username/email or password. Please verify your credentials.")
            if not user.is_active:
                raise forms.ValidationError("This account is inactive. Please contact Kodafriq support.")
            if getattr(user, 'is_suspended', False):
                reason = user.suspension_reason or "Account suspended for security or compliance policy review."
                raise forms.ValidationError(f"Your account has been suspended: {reason}")

            self.user_cache = user
        return cleaned_data

    def get_user(self):
        return getattr(self, 'user_cache', None)


class TalentRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Kwesi'})
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Mensah'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'kf-input', 'placeholder': 'kwesi.mensah@healthcare.org'})
    )
    username = forms.CharField(
        max_length=40,
        help_text="Choose a unique handle for your talent profile",
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'kwesi_mensah'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'kf-input', 'placeholder': 'Minimum 8 characters'})
    )
    password_confirm = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'kf-input', 'placeholder': 'Repeat your password'})
    )
    
    # Profile Specific
    headline = forms.CharField(
        label="Primary Clinical Specialty",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'kf-input',
            'placeholder': 'e.g. Certified Inpatient Coder | CPC, ICD-10-CM Specialist'
        })
    )
    years_of_experience = forms.IntegerField(
        min_value=0,
        max_value=40,
        initial=2,
        widget=forms.NumberInput(attrs={'class': 'kf-input'})
    )
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': '+234 80 000 0000'})
    )
    country = forms.ChoiceField(
        choices=AFRICAN_AND_GLOBAL_COUNTRIES,
        initial='Nigeria',
        label="Country of Residence",
        widget=forms.Select(attrs={'class': 'kf-input', 'id': 'id_country'})
    )
    location = forms.CharField(
        label="City / State",
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Lagos, Nigeria or Remote'})
    )
    detected_country = forms.CharField(required=False, widget=forms.HiddenInput())
    detected_device = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken. Please pick another.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Passwords do not match.")
        if p1:
            try:
                validate_password(p1)
            except forms.ValidationError as error:
                self.add_error('password', error)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CANDIDATE
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            profile, _ = CandidateProfile.objects.get_or_create(user=user)
            profile.headline = self.cleaned_data.get('headline', '')
            profile.years_of_experience = self.cleaned_data.get('years_of_experience', 0)
            profile.phone = self.cleaned_data.get('phone', '')
            profile.location = self.cleaned_data.get('location', '')
            profile.country = self.cleaned_data.get('country', 'Nigeria')
            profile.save()
        user.detected_country = self.cleaned_data.get('detected_country') or self.cleaned_data.get('country')
        user.detected_device = self.cleaned_data.get('detected_device') or ''
        user.save(update_fields=['detected_country', 'detected_device'])
        return user


class EmployerRegistrationForm(forms.ModelForm):
    company_name = forms.CharField(
        label="Facility or Organization Name",
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. St. Jude Regional Hospital / Apex RCM Solutions'})
    )
    contact_person_name = forms.CharField(
        label="Contact Person Name",
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Dr. Eric Addo'})
    )
    contact_person_title = forms.CharField(
        label="Job Title / Role in Organization",
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Director of Health Informatics / Talent Lead'})
    )
    email = forms.EmailField(
        label="Corporate Work Email",
        widget=forms.EmailInput(attrs={'class': 'kf-input', 'placeholder': 'hr@organization.com'})
    )
    username = forms.CharField(
        max_length=40,
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'st_jude_hospital'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'kf-input', 'placeholder': 'Minimum 8 characters'})
    )
    password_confirm = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'kf-input', 'placeholder': 'Repeat your password'})
    )
    industry = forms.CharField(
        initial="Healthcare & Revenue Cycle Management",
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Hospital Network, Clinical Coding Agency'})
    )
    company_size = forms.ChoiceField(
        choices=[
            ('1-10 Employees', '1–10 Employees'),
            ('11-50 Employees', '11–50 Employees'),
            ('51-200 Employees', '51–200 Employees'),
            ('201-500 Employees', '201–500 Employees'),
            ('500+ Employees', '500+ Enterprise Facility'),
        ],
        widget=forms.Select(attrs={'class': 'kf-input'})
    )
    website = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={'class': 'kf-input', 'placeholder': 'https://www.organization.com'})
    )
    phone = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': '+234 80 000 0000'})
    )
    country = forms.ChoiceField(
        choices=AFRICAN_AND_GLOBAL_COUNTRIES,
        initial='Nigeria',
        label="Country / Headquarters",
        widget=forms.Select(attrs={'class': 'kf-input', 'id': 'id_country'})
    )
    detected_country = forms.CharField(required=False, widget=forms.HiddenInput())
    detected_device = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = User
        fields = ('username', 'email')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this corporate email already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken. Please pick another.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Passwords do not match.")
        if p1:
            try:
                validate_password(p1)
            except forms.ValidationError as error:
                self.add_error('password', error)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.EMPLOYER
        # Split contact person name if provided
        parts = self.cleaned_data.get('contact_person_name', '').strip().split(' ', 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            profile, _ = EmployerProfile.objects.get_or_create(user=user)
            profile.company_name = self.cleaned_data.get('company_name', '')
            profile.industry = self.cleaned_data.get('industry', '')
            profile.company_size = self.cleaned_data.get('company_size', '')
            profile.website = self.cleaned_data.get('website', '')
            profile.contact_person_title = self.cleaned_data.get('contact_person_title', '')
            profile.contact_phone = self.cleaned_data.get('phone', '')
            profile.country = self.cleaned_data.get('country', 'Nigeria')
            profile.save()
        user.detected_country = self.cleaned_data.get('detected_country') or self.cleaned_data.get('country')
        user.detected_device = self.cleaned_data.get('detected_device') or ''
        user.save(update_fields=['detected_country', 'detected_device'])
        return user


class CandidateProfileEditForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Kwesi'})
    )
    last_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Mensah'})
    )

    class Meta:
        model = CandidateProfile
        fields = (
            'headline', 'bio', 'phone', 'location', 'country',
            'years_of_experience', 'availability_status',
            'desired_salary_range', 'profile_photo', 'resume_file'
        )
        widgets = {
            'headline': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Certified Inpatient Medical Coder | CPC, CCS'}),
            'bio': forms.Textarea(attrs={'class': 'kf-input', 'rows': 4, 'placeholder': 'Write a brief professional summary of your healthcare expertise...'}),
            'phone': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': '+234 80 000 0000'}),
            'location': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Accra, Ghana / Remote'}),
            'years_of_experience': forms.NumberInput(attrs={'class': 'kf-input', 'min': 0, 'max': 45}),
            'availability_status': forms.Select(attrs={'class': 'kf-input'}),
            'desired_salary_range': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. $1,500 - $2,500 / month'}),
            'profile_photo': forms.FileInput(attrs={'class': 'kf-file-input'}),
            'resume_file': forms.FileInput(attrs={'class': 'kf-file-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save(update_fields=['first_name', 'last_name'])
            profile.save()
        return profile


class WorkExperienceForm(forms.ModelForm):
    class Meta:
        model = WorkExperience
        fields = ('organization_name', 'job_title', 'start_date', 'end_date', 'is_current', 'description')
        widgets = {
            'organization_name': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Korle-Bu Teaching Hospital'}),
            'job_title': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Senior Medical Records & Billing Specialist'}),
            'start_date': forms.DateInput(attrs={'class': 'kf-input', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'kf-input', 'type': 'date'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'kf-checkbox', 'id': 'is_current_exp'}),
            'description': forms.Textarea(attrs={'class': 'kf-input', 'rows': 3, 'placeholder': 'Key responsibilities, domain coding standards used, audit accuracy ratings...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        is_current = cleaned_data.get('is_current')
        end_date = cleaned_data.get('end_date')
        if not is_current and not end_date:
            self.add_error('end_date', 'Please specify an end date or mark as your current role.')
        return cleaned_data


class CandidateCertificationForm(forms.ModelForm):
    class Meta:
        model = CandidateCertification
        fields = ('certification_name', 'issuing_organization', 'credential_id', 'issue_date', 'expiration_date', 'certificate_file')
        widgets = {
            'certification_name': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. CPC (Certified Professional Coder)'}),
            'issuing_organization': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. AAPC / AHIMA'}),
            'credential_id': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. AAPC-99214-CPC'}),
            'issue_date': forms.DateInput(attrs={'class': 'kf-input', 'type': 'date'}),
            'expiration_date': forms.DateInput(attrs={'class': 'kf-input', 'type': 'date'}),
            'certificate_file': forms.FileInput(attrs={'class': 'kf-file-input'}),
        }
