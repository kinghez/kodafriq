from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'action_category', 'actor', 'target_user', 'status_code', 'ip_address', 'device_info', 'timestamp')
    list_filter = ('action_category', 'status_code', 'http_method', 'timestamp')
    search_fields = ('action', 'actor__username', 'actor__email', 'target_user__username', 'target_user__email', 'ip_address', 'details', 'path')
    readonly_fields = ('actor', 'user', 'target_user', 'action', 'action_category', 'details', 'ip_address', 'device_info', 'http_method', 'path', 'status_code', 'target_entity', 'target_id', 'timestamp')
    ordering = ('-timestamp',)

from .models import Conversation, DirectMessage, SupportTicket, Notification

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'employer', 'candidate', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('employer__company_name', 'candidate__user__username', 'subject')

@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__username', 'body')

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'user', 'category', 'priority', 'status', 'created_at')
    list_filter = ('priority', 'status', 'category', 'created_at')
    search_fields = ('subject', 'name', 'email', 'message')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('recipient__username', 'title', 'message')
