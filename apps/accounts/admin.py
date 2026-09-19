from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.contrib import messages
from .models import User, CandidateProfile, EmployerProfile, WorkExperience, CandidateCertification
from apps.dashboard.models import log_staff_action

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role')

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    list_display = (
        'username', 'email', 'first_name', 'last_name', 'role',
        'is_suspended', 'detected_country', 'registration_ip', 'last_login_ip',
        'is_staff', 'is_email_verified', 'created_at'
    )
    list_filter = (
        'role', 'is_suspended', 'is_staff', 'is_superuser', 'is_active',
        'is_email_verified', 'detected_country'
    )
    search_fields = ('username', 'email', 'first_name', 'last_name', 'registration_ip', 'last_login_ip', 'detected_country')
    ordering = ('-created_at',)
    actions = ['suspend_selected_users', 'reactivate_selected_users']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Kodafriq Platform Role', {'fields': ('role', 'is_email_verified')}),
        ('Account Suspension & Compliance', {
            'fields': ('is_suspended', 'suspension_reason', 'suspended_at', 'suspended_by')
        }),
        ('Telemetry & Geolocation Intelligence', {
            'fields': ('detected_country', 'detected_country_code', 'detected_device', 'registration_ip', 'last_login_ip')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )

    @admin.action(description="Suspend selected accounts")
    def suspend_selected_users(self, request, queryset):
        now = timezone.now()
        count = 0
        for user in queryset:
            if not user.is_suspended:
                user.is_suspended = True
                user.suspension_reason = "Suspended by administrator via bulk management action."
                user.suspended_at = now
                user.suspended_by = request.user
                user.save(update_fields=['is_suspended', 'suspension_reason', 'suspended_at', 'suspended_by'])
                log_staff_action(
                    actor=request.user,
                    action=f"Account Suspended (Bulk Action)",
                    action_category='SUSPENSION',
                    target_user=user,
                    details=f"User {user.username} was placed under administrative suspension.",
                    request=request
                )
                count += 1
        self.message_user(request, f"Successfully suspended {count} user account(s).", level=messages.WARNING)

    @admin.action(description="Reactivate / Unsuspend selected accounts")
    def reactivate_selected_users(self, request, queryset):
        count = 0
        for user in queryset:
            if user.is_suspended:
                user.is_suspended = False
                user.suspension_reason = ""
                user.suspended_at = None
                user.suspended_by = None
                user.save(update_fields=['is_suspended', 'suspension_reason', 'suspended_at', 'suspended_by'])
                log_staff_action(
                    actor=request.user,
                    action=f"Account Reactivated (Bulk Action)",
                    action_category='SUSPENSION',
                    target_user=user,
                    details=f"User {user.username} suspension was lifted.",
                    request=request
                )
                count += 1
        self.message_user(request, f"Successfully reactivated {count} user account(s).", level=messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        if obj.role in [User.Role.STAFF, User.Role.ADMIN]:
            obj.is_staff = True
        
        # Track suspension metadata if toggled in form
        if 'is_suspended' in form.changed_data:
            if obj.is_suspended and not obj.suspended_at:
                obj.suspended_at = timezone.now()
                obj.suspended_by = request.user
                if not obj.suspension_reason:
                    obj.suspension_reason = "Suspended by platform administrator."
            elif not obj.is_suspended:
                obj.suspended_at = None
                obj.suspended_by = None
                obj.suspension_reason = ""

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
    list_display = ('user', 'headline', 'country', 'kodafriq_verified_score', 'is_employer_ready', 'availability_status', 'years_of_experience')
    list_filter = ('country', 'is_employer_ready', 'availability_status')
    search_fields = ('user__username', 'user__email', 'headline', 'bio', 'location', 'country')

@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'country', 'industry', 'approval_status', 'contact_person_title', 'approved_at')
    list_filter = ('country', 'approval_status', 'industry')
    search_fields = ('company_name', 'user__email', 'country')

admin.site.register(User, CustomUserAdmin)
admin.site.register(WorkExperience)
admin.site.register(CandidateCertification)
