from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Permission
from django.utils.safestring import mark_safe
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
        'is_suspended', 'detected_country', 'is_staff', 'dashboard_access_badge', 'created_at'
    )
    list_filter = (
        'role', 'is_suspended', 'is_staff', 'is_superuser', 'is_active',
        'is_email_verified', 'detected_country'
    )
    search_fields = ('username', 'email', 'first_name', 'last_name', 'registration_ip', 'last_login_ip', 'detected_country')
    ordering = ('-created_at',)
    actions = [
        'resend_verification_emails', 'suspend_selected_users', 'reactivate_selected_users',
        'grant_all_dashboard_permissions', 'grant_financial_dashboard_permissions', 'reset_dashboard_permissions'
    ]
    
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


    @admin.display(description="Dashboard RBAC Access")
    def dashboard_access_badge(self, obj):
        if obj.is_superuser:
            return mark_safe('<span style="background: #10b981; color: white; padding: 2px 7px; border-radius: 4px; font-weight: 600; font-size: 11px;">👑 Superuser (Full)</span>')
        if not getattr(obj, 'is_kodafriq_staff', False) and not obj.is_staff:
            return mark_safe('<span style="color: #94a3b8; font-size: 12px;">—</span>')
        
        perms = set(obj.user_permissions.filter(content_type__app_label='dashboard', codename__startswith='access_').values_list('codename', flat=True))
        group_perms = set(Permission.objects.filter(group__user=obj, content_type__app_label='dashboard', codename__startswith='access_').values_list('codename', flat=True))
        all_perms = perms | group_perms
        
        if not all_perms:
            return mark_safe('<span style="background: #64748b; color: white; padding: 2px 7px; border-radius: 4px; font-size: 11px;">Dashboard Only</span>')
        
        short_names = {
            'access_notifications': 'Notifs',
            'access_contracts': 'Contracts',
            'access_disputes': 'Disputes',
            'access_payments': 'Payments',
            'access_automation': 'Automation',
            'access_analytics': 'Analytics',
            'access_broadcasts': 'Broadcasts',
            'access_security_audit': 'Audit',
        }
        badges = [f'<span style="background: #0284c7; color: white; padding: 1px 5px; border-radius: 3px; font-size: 10px; margin-right: 2px;">{short_names.get(p, p)}</span>' for p in all_perms]
        return mark_safe(" ".join(badges))

    @admin.action(description="Grant all Admin Dashboard access permissions")
    def grant_all_dashboard_permissions(self, request, queryset):
        dashboard_perms = Permission.objects.filter(content_type__app_label='dashboard', codename__startswith='access_')
        count = 0
        for user in queryset:
            if user.is_staff or getattr(user, 'is_kodafriq_staff', False):
                user.user_permissions.add(*dashboard_perms)
                count += 1
        self.message_user(request, f"Granted all dashboard page permissions to {count} staff account(s).", level=messages.SUCCESS)

    @admin.action(description="Grant Financial & Payments permissions (Payments + Automation)")
    def grant_financial_dashboard_permissions(self, request, queryset):
        perms = Permission.objects.filter(content_type__app_label='dashboard', codename__in=['access_payments', 'access_automation'])
        count = 0
        for user in queryset:
            if user.is_staff or getattr(user, 'is_kodafriq_staff', False):
                user.user_permissions.add(*perms)
                count += 1
        self.message_user(request, f"Granted financial dashboard permissions to {count} staff account(s).", level=messages.SUCCESS)

    @admin.action(description="Reset to default staff access (Dashboard & Control Panel only)")
    def reset_dashboard_permissions(self, request, queryset):
        dashboard_perms = Permission.objects.filter(content_type__app_label='dashboard', codename__startswith='access_')
        count = 0
        for user in queryset:
            if user.is_staff or getattr(user, 'is_kodafriq_staff', False):
                user.user_permissions.remove(*dashboard_perms)
                count += 1
        self.message_user(request, f"Reset {count} staff account(s) to default access (Dashboard & Control Panel only).", level=messages.INFO)

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

    @admin.action(description="Resend email verification link to selected users")
    def resend_verification_emails(self, request, queryset):
        from apps.core.services.email_service import EmailService
        sent_count = 0
        for user in queryset:
            if user.email and not user.is_email_verified:
                EmailService.send_verification_email(user, request=request)
                sent_count += 1
        if sent_count > 0:
            self.message_user(request, f"Verification emails successfully dispatched to {sent_count} user(s).", messages.SUCCESS)
        else:
            self.message_user(request, "Selected user(s) either already have verified emails or have no email configured.", messages.WARNING)

    def save_model(self, request, obj, form, change):
        is_new = not change
        if obj.role in [User.Role.STAFF, User.Role.ADMIN]:
            obj.is_staff = True
        
        # Comprehensive audit logging for suspension state mutations
        if 'is_suspended' in form.changed_data:
            if obj.is_suspended:
                if not obj.suspended_at:
                    obj.suspended_at = timezone.now()
                obj.suspended_by = request.user
                if not obj.suspension_reason:
                    obj.suspension_reason = "Suspended by platform administrator."
                log_staff_action(
                    actor=request.user,
                    action=f"Account Suspended: {obj.username}",
                    action_category='SUSPENSION',
                    target_user=obj,
                    target_entity="User",
                    target_id=str(obj.pk) if obj.pk else "",
                    details=f"Admin {request.user.username} placed account under suspension. Reason: {obj.suspension_reason}",
                    request=request
                )
            else:
                obj.suspended_at = None
                obj.suspended_by = None
                obj.suspension_reason = ""
                log_staff_action(
                    actor=request.user,
                    action=f"Account Reactivated: {obj.username}",
                    action_category='SUSPENSION',
                    target_user=obj,
                    target_entity="User",
                    target_id=str(obj.pk) if obj.pk else "",
                    details=f"Admin {request.user.username} lifted suspension for account {obj.username}. Access restored.",
                    request=request
                )

        if not is_new:
            if 'role' in form.changed_data:
                log_staff_action(
                    actor=request.user,
                    action=f"User Role Updated: {obj.username} -> {obj.get_role_display()}",
                    action_category='ADMIN_ACTION',
                    target_user=obj,
                    target_entity="User",
                    target_id=str(obj.pk),
                    details=f"Role changed from {form.initial.get('role')} to {obj.role} by admin {request.user.username}.",
                    request=request
                )
            if 'is_active' in form.changed_data:
                log_staff_action(
                    actor=request.user,
                    action=f"Account Active State Changed: {obj.username} -> {obj.is_active}",
                    action_category='ADMIN_ACTION',
                    target_user=obj,
                    target_entity="User",
                    target_id=str(obj.pk),
                    details=f"Active state set to {obj.is_active} by admin {request.user.username}.",
                    request=request
                )
            if 'is_staff' in form.changed_data or 'is_superuser' in form.changed_data:
                log_staff_action(
                    actor=request.user,
                    action=f"Admin Privileges Updated: {obj.username}",
                    action_category='ADMIN_ACTION',
                    target_user=obj,
                    target_entity="User",
                    target_id=str(obj.pk),
                    details=f"Staff={obj.is_staff}, Superuser={obj.is_superuser} modified by admin {request.user.username}.",
                    request=request
                )

        super().save_model(request, obj, form, change)

        # Log new account creation
        if is_new:
            log_staff_action(
                actor=request.user,
                action=f"User Account Created: {obj.username}",
                action_category='ADMIN_ACTION',
                target_user=obj,
                target_entity="User",
                target_id=str(obj.pk),
                details=f"Account created in admin with role {obj.role}, email {obj.email}.",
                request=request
            )
        
        # Ensure profiles exist
        if obj.role == User.Role.CANDIDATE:
            CandidateProfile.objects.get_or_create(user=obj)
        elif obj.role == User.Role.EMPLOYER:
            name = obj.get_full_name() or obj.username
            EmployerProfile.objects.get_or_create(
                user=obj,
                defaults={'company_name': f'{name} Healthcare'}
            )

        # Dispatch onboarding, verification emails, and in-app notices for newly created users from Django Admin
        if is_new and obj.email:
            from apps.core.services.email_service import EmailService
            EmailService.send_onboarding_email(obj)
            EmailService.send_verification_email(obj, request=request)
            from apps.dashboard.models import send_notification, Notification
            send_notification(
                recipient=obj,
                title="Welcome to Kodafriq",
                message="Welcome to Kodafriq! Complete your profile credentials and start discovering healthcare opportunities.",
                notification_type=Notification.NotificationType.SYSTEM,
                link="/dashboard/"
            )
            messages.info(request, f"Onboarding & email verification links have been dispatched to {obj.email}.")

    def delete_model(self, request, obj):
        username = obj.username
        email = obj.email
        pk = obj.pk
        role = obj.role
        log_staff_action(
            actor=request.user,
            action=f"User Deleted: {username}",
            action_category='ADMIN_ACTION',
            target_user=None,
            target_entity="User",
            target_id=str(pk),
            details=f"User {username} (Email: {email}, Role: {role}, ID: {pk}) permanently deleted by admin {request.user.username}.",
            request=request
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            log_staff_action(
                actor=request.user,
                action=f"User Deleted (Bulk Action): {obj.username}",
                action_category='ADMIN_ACTION',
                target_user=None,
                target_entity="User",
                target_id=str(obj.pk),
                details=f"User {obj.username} (Email: {obj.email}, Role: {obj.role}, ID: {obj.pk}) deleted in bulk by admin {request.user.username}.",
                request=request
            )
        super().delete_queryset(request, queryset)

@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'headline', 'country', 'kodafriq_verified_score', 'is_verified', 'is_employer_ready', 'availability_status', 'years_of_experience')
    list_filter = ('country', 'is_verified', 'is_employer_ready', 'availability_status')
    search_fields = ('user__username', 'user__email', 'headline', 'bio', 'location', 'country')

    def save_model(self, request, obj, form, change):
        if 'is_verified' in form.changed_data:
            log_staff_action(
                actor=request.user,
                action=f"Candidate Verification: {'Verified' if obj.is_verified else 'Unverified'}",
                action_category='VERIFICATION',
                target_user=obj.user,
                target_entity="CandidateProfile",
                target_id=str(obj.pk),
                details=f"Verification status set to {obj.is_verified} for candidate {obj.user.username} by admin {request.user.username}.",
                request=request
            )
            from apps.dashboard.models import send_notification, Notification
            send_notification(
                recipient=obj.user,
                title="Profile Verification Updated",
                message=f"Your profile verification status is now: {'Verified' if obj.is_verified else 'Under Review'}.",
                notification_type=Notification.NotificationType.SCORE_BOOST
            )
        if 'is_employer_ready' in form.changed_data:
            log_staff_action(
                actor=request.user,
                action=f"Employer Readiness: {'Ready' if obj.is_employer_ready else 'Not Ready'}",
                action_category='VERIFICATION',
                target_user=obj.user,
                target_entity="CandidateProfile",
                target_id=str(obj.pk),
                details=f"Employer readiness status set to {obj.is_employer_ready} for {obj.user.username} by admin {request.user.username}.",
                request=request
            )
        super().save_model(request, obj, form, change)

@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'country', 'industry', 'approval_status', 'contact_person_title', 'approved_at')
    list_filter = ('country', 'approval_status', 'industry')
    search_fields = ('company_name', 'user__email', 'country')

    def save_model(self, request, obj, form, change):
        if 'approval_status' in form.changed_data:
            log_staff_action(
                actor=request.user,
                action=f"Employer Approval: {obj.get_approval_status_display()}",
                action_category='STAFF_ACTION',
                target_user=obj.user,
                target_entity="EmployerProfile",
                target_id=str(obj.pk),
                details=f"Employer company '{obj.company_name}' approval status updated to {obj.approval_status} by admin {request.user.username}.",
                request=request
            )
            from apps.dashboard.models import send_notification, Notification
            send_notification(
                recipient=obj.user,
                title="Company Approval Status",
                message=f"Your employer account status is now: {obj.get_approval_status_display()}.",
                notification_type=Notification.NotificationType.SYSTEM
            )
        super().save_model(request, obj, form, change)

admin.site.register(User, CustomUserAdmin)
admin.site.register(WorkExperience)
admin.site.register(CandidateCertification)
