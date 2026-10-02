from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'action_category', 'actor', 'target_user', 'status_code', 'ip_address', 'device_info', 'timestamp')
    list_filter = ('action_category', 'status_code', 'http_method', 'timestamp')
    search_fields = ('action', 'actor__username', 'actor__email', 'target_user__username', 'target_user__email', 'ip_address', 'details', 'path')
    readonly_fields = ('actor', 'user', 'target_user', 'action', 'action_category', 'details', 'ip_address', 'device_info', 'http_method', 'path', 'status_code', 'target_entity', 'target_id', 'timestamp')
    ordering = ('-timestamp',)

from .models import Conversation, DirectMessage, SupportTicket, Notification, FlaggedMessageLog

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'employer', 'candidate', 'status', 'created_at', 'updated_at')
    list_display_links = ('employer', 'candidate')
    list_filter = ('status', 'created_at')
    search_fields = ('employer__company_name', 'candidate__user__username', 'subject')

@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'is_read', 'created_at')
    list_display_links = ('conversation', 'sender')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__username', 'body')

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'user', 'category', 'priority', 'status', 'created_at')
    list_display_links = ('subject',)
    list_filter = ('priority', 'status', 'category', 'created_at')
    search_fields = ('subject', 'name', 'email', 'message')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'title', 'notification_type', 'is_read', 'created_at')
    list_display_links = ('title',)
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('recipient__username', 'title', 'message')

@admin.register(FlaggedMessageLog)
class FlaggedMessageLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'recipient', 'detected_reasons', 'created_at')
    list_display_links = ('sender', 'detected_reasons')
    list_filter = ('detected_reasons', 'created_at')
    search_fields = ('sender__username', 'sender__email', 'recipient__username', 'recipient__email', 'original_body', 'detected_reasons')
    readonly_fields = ('sender', 'recipient', 'conversation', 'original_body', 'detected_reasons', 'flagged_snippets', 'created_at')
    ordering = ('-created_at',)

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils.safestring import mark_safe
from django.db import models

User = get_user_model()

class StaffDashboardAccessProxy(User):
    """
    Dedicated Django Admin proxy model allowing platform superusers to easily
    review and configure dashboard sidebar access permissions for all staff members.
    """
    class Meta:
        proxy = True
        verbose_name = "Staff Dashboard Permission"
        verbose_name_plural = "Staff Dashboard Permissions"

@admin.register(StaffDashboardAccessProxy)
class StaffDashboardAccessAdmin(admin.ModelAdmin):
    list_display = ('username', 'get_full_name', 'email', 'role', 'is_superuser_badge', 'permitted_pages_display')
    list_filter = ('role', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fields = ('username', 'email', 'role', 'is_staff', 'is_superuser', 'user_permissions')
    readonly_fields = ('username', 'email', 'role', 'is_staff', 'is_superuser')
    filter_horizontal = ('user_permissions',)
    actions = ['grant_all_dashboard_permissions', 'grant_financial_permissions', 'reset_to_default_permissions']

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            models.Q(role__in=[User.Role.STAFF, User.Role.ADMIN]) | models.Q(is_staff=True)
        )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "user_permissions":
            kwargs["queryset"] = Permission.objects.filter(
                content_type__app_label='dashboard',
                codename__startswith='access_'
            ).order_by('name')
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @admin.display(description="Superuser Status")
    def is_superuser_badge(self, obj):
        if obj.is_superuser:
            return mark_safe('<span style="background: #10b981; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">👑 Superuser (Unrestricted)</span>')
        return mark_safe('<span style="background: #3b82f6; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px;">Staff Member</span>')

    @admin.display(description="Permitted Sidebar Pages")
    def permitted_pages_display(self, obj):
        if obj.is_superuser:
            return mark_safe('<span style="color: #10b981; font-weight: 600;">All Pages (Full Access)</span>')
        
        perms = set(obj.user_permissions.filter(
            content_type__app_label='dashboard',
            codename__startswith='access_'
        ).values_list('codename', flat=True))

        group_perms = set(Permission.objects.filter(
            group__user=obj,
            content_type__app_label='dashboard',
            codename__startswith='access_'
        ).values_list('codename', flat=True))

        all_perms = perms | group_perms

        label_map = {
            'access_notifications': ('Notifications', '#6366f1'),
            'access_contracts': ('Contracts', '#0ea5e9'),
            'access_disputes': ('Disputes', '#f59e0b'),
            'access_payments': ('Payments', '#10b981'),
            'access_automation': ('Automation', '#8b5cf6'),
            'access_analytics': ('Analytics', '#ec4899'),
            'access_broadcasts': ('Broadcasts', '#14b8a6'),
            'access_security_audit': ('Audit Logs', '#ef4444'),
        }

        if not all_perms:
            return mark_safe('<span style="color: #64748b; font-style: italic;">Dashboard &amp; Control Panel Only</span>')

        pills = []
        for code, (label, color) in label_map.items():
            if code in all_perms:
                pills.append(f'<span style="background: {color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; margin-right: 3px; display: inline-block;">{label}</span>')

        return mark_safe(" ".join(pills))

    @admin.action(description="Grant all Dashboard Sidebar permissions to selected staff")
    def grant_all_dashboard_permissions(self, request, queryset):
        perms = Permission.objects.filter(content_type__app_label='dashboard', codename__startswith='access_')
        count = 0
        for u in queryset:
            u.user_permissions.add(*perms)
            count += 1
        self.message_user(request, f"Granted all dashboard sidebar permissions to {count} staff member(s).", level=messages.SUCCESS)

    @admin.action(description="Grant Financial & Payments permissions (Payments + Automation)")
    def grant_financial_permissions(self, request, queryset):
        perms = Permission.objects.filter(content_type__app_label='dashboard', codename__in=['access_payments', 'access_automation'])
        count = 0
        for u in queryset:
            u.user_permissions.add(*perms)
            count += 1
        self.message_user(request, f"Granted Financial permissions to {count} staff member(s).", level=messages.SUCCESS)

    @admin.action(description="Reset to default (Dashboard & Control Panel only)")
    def reset_to_default_permissions(self, request, queryset):
        perms = Permission.objects.filter(content_type__app_label='dashboard', codename__startswith='access_')
        count = 0
        for u in queryset:
            u.user_permissions.remove(*perms)
            count += 1
        self.message_user(request, f"Reset {count} staff member(s) to default access.", level=messages.INFO)
