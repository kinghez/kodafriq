from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth import get_user_model
from .models import NotificationBroadcast, BroadcastDeliveryLog
from .services import NotificationService

User = get_user_model()


class BroadcastDeliveryLogInline(admin.TabularInline):
    model = BroadcastDeliveryLog
    extra = 0
    can_delete = False
    readonly_fields = ('recipient', 'channel', 'status', 'error_message', 'delivered_at')
    ordering = ('-delivered_at',)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(NotificationBroadcast)
class NotificationBroadcastAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'channel_badge',
        'target_badge',
        'status_badge',
        'total_recipients',
        'success_count',
        'failure_count',
        'sender',
        'sent_at',
    )
    list_filter = ('channel', 'target_type', 'status', 'notification_type', 'sent_at')
    search_fields = ('title', 'message', 'sender__username', 'sender__email')
    filter_horizontal = ('target_users',)
    readonly_fields = ('sent_at', 'total_recipients', 'success_count', 'failure_count', 'created_at', 'updated_at')
    inlines = [BroadcastDeliveryLogInline]
    actions = ['dispatch_selected_broadcasts']

    fieldsets = (
        ("Origin & Channel", {
            "fields": ("sender", "channel", "notification_type"),
            "description": "Configure the sender and delivery format for this announcement."
        }),
        ("Target Audience", {
            "fields": ("target_type", "target_group", "target_single_user", "target_users"),
            "description": "Choose who receives this broadcast. Relevant audience fields automatically appear based on your Target Type."
        }),
        ("Message Content", {
            "fields": ("title", "message", "action_url", "action_button_text"),
            "description": "Craft the subject and body. Action URL and button label are included in in-app notifications and email CTA buttons."
        }),
        ("Status & Delivery Metrics", {
            "fields": ("status", "sent_at", "total_recipients", "success_count", "failure_count"),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    class Media:
        js = ('js/admin_broadcast_dynamic.js',)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if 'sender' not in initial and request.user.is_authenticated:
            initial['sender'] = request.user.pk
        return initial

    def save_model(self, request, obj, form, change):
        if not obj.sender_id and request.user.is_authenticated:
            obj.sender = request.user
        super().save_model(request, obj, form, change)
        if obj.target_type == NotificationBroadcast.TargetType.SINGLE_USER and obj.target_single_user:
            obj.target_users.set([obj.target_single_user])

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'target_single_user':
            kwargs['queryset'] = User.objects.filter(is_active=True).order_by('username')
            field = super().formfield_for_foreignkey(db_field, request, **kwargs)
            field.label_from_instance = lambda obj: (
                f"{obj.username} — {obj.get_full_name()} ({obj.email})"
                if obj.get_full_name() and obj.email
                else f"{obj.username} ({obj.email or 'No email'})"
            )
            return field
        if db_field.name == 'sender':
            kwargs['queryset'] = User.objects.filter(is_active=True).order_by('username')
            field = super().formfield_for_foreignkey(db_field, request, **kwargs)
            field.label_from_instance = lambda obj: (
                f"{obj.username} — {obj.get_full_name()} ({obj.email})"
                if obj.get_full_name() and obj.email
                else f"{obj.username} ({obj.email or 'Staff'})"
            )
            return field
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def channel_badge(self, obj):
        colors = {
            'IN_APP': '#006fe6',
            'EMAIL': '#8b5cf6',
            'BOTH': '#10b981',
        }
        color = colors.get(obj.channel, '#64748b')
        return format_html(
            '<span style="background: {}; color: #fff; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 11px;">{}</span>',
            color, obj.get_channel_display()
        )
    channel_badge.short_description = 'Channel'

    def target_badge(self, obj):
        if obj.target_type == NotificationBroadcast.TargetType.GROUP and obj.target_group:
            detail = f" ({obj.target_group.name})"
        elif obj.target_type == NotificationBroadcast.TargetType.SINGLE_USER and obj.target_single_user:
            detail = f" ({obj.target_single_user.username})"
        else:
            detail = ""
        return format_html(
            '<span style="font-weight: 600; color: #091e42;">{}{}</span>',
            obj.get_target_type_display(), detail
        )
    target_badge.short_description = 'Target Audience'

    def status_badge(self, obj):
        colors = {
            'DRAFT': '#f59e0b',
            'SENT': '#10b981',
            'FAILED': '#ef4444',
        }
        color = colors.get(obj.status, '#64748b')
        return format_html(
            '<span style="background: {}; color: #fff; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    @admin.action(description="Dispatch selected broadcasts now")
    def dispatch_selected_broadcasts(self, request, queryset):
        sent_total = 0
        for broadcast in queryset:
            NotificationService.dispatch_broadcast(broadcast)
            sent_total += 1
        self.message_user(request, f"Successfully processed and dispatched {sent_total} broadcast(s).")


@admin.register(BroadcastDeliveryLog)
class BroadcastDeliveryLogAdmin(admin.ModelAdmin):
    list_display = ('broadcast', 'recipient', 'channel', 'status_badge', 'delivered_at')
    list_filter = ('channel', 'status', 'delivered_at')
    search_fields = ('recipient__username', 'recipient__email', 'broadcast__title', 'error_message')
    readonly_fields = ('broadcast', 'recipient', 'channel', 'status', 'error_message', 'delivered_at')

    def status_badge(self, obj):
        colors = {
            'SUCCESS': '#10b981',
            'FAILED': '#ef4444',
            'SKIPPED': '#f59e0b',
        }
        color = colors.get(obj.status, '#64748b')
        return format_html(
            '<span style="background: {}; color: #fff; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False
