from django.contrib import admin
from .models import GuestVisit

@admin.register(GuestVisit)
class GuestVisitAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'country', 'city', 'device_type', 'device_os', 'browser', 'path', 'visit_count', 'last_visited_at')
    list_filter = ('country', 'device_type', 'device_os', 'browser', 'first_visited_at', 'last_visited_at')
    search_fields = ('ip_address', 'country', 'city', 'path', 'referrer')
    readonly_fields = ('ip_address', 'session_key', 'country', 'country_code', 'city', 'device_type', 'device_os', 'browser', 'user_agent', 'path', 'referrer', 'visit_count', 'first_visited_at', 'last_visited_at')
    ordering = ('-last_visited_at',)
