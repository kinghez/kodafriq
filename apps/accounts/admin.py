from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from .models import User, CandidateProfile, EmployerProfile, WorkExperience, CandidateCertification

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role')

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_email_verified', 'created_at')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active', 'is_email_verified')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-created_at',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Kodafriq Platform Role', {'fields': ('role', 'is_email_verified')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )

    def save_model(self, request, obj, form, change):
        # Auto-grant staff privileges to Kodafriq Staff
        if obj.role in [User.Role.STAFF, User.Role.ADMIN]:
            obj.is_staff = True
        super().save_model(request, obj, form, change)
        
        # Ensure profiles exist
        if obj.role == User.Role.CANDIDATE:
            CandidateProfile.objects.get_or_create(user=obj)
        elif obj.role == User.Role.EMPLOYER:
            name = obj.get_full_name() or obj.username
            EmployerProfile.objects.get_or_create(
                user=obj,
                defaults={'company_name': f'{name} Healthcare'}
            )

@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'headline', 'kodafriq_verified_score', 'is_employer_ready', 'availability_status', 'years_of_experience')
    list_filter = ('is_employer_ready', 'availability_status')
    search_fields = ('user__username', 'user__email', 'headline', 'bio')

@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'industry', 'approval_status', 'contact_person_title', 'approved_at')
    list_filter = ('approval_status', 'industry')
    search_fields = ('company_name', 'user__email')

admin.site.register(User, CustomUserAdmin)
admin.site.register(WorkExperience)
admin.site.register(CandidateCertification)
