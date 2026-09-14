from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'target_entity', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp')
