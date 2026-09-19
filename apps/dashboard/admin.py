from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'action_category', 'actor', 'target_user', 'status_code', 'ip_address', 'device_info', 'timestamp')
    list_filter = ('action_category', 'status_code', 'http_method', 'timestamp')
    search_fields = ('action', 'actor__username', 'actor__email', 'target_user__username', 'target_user__email', 'ip_address', 'details', 'path')
    readonly_fields = ('actor', 'user', 'target_user', 'action', 'action_category', 'details', 'ip_address', 'device_info', 'http_method', 'path', 'status_code', 'target_entity', 'target_id', 'timestamp')
    ordering = ('-timestamp',)
