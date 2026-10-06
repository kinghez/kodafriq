from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import GuestVisit, HomePageSetting, PartnerOrganization, ContactInquiry


@admin.register(GuestVisit)
class GuestVisitAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'country', 'city', 'device_type', 'device_os', 'browser', 'path', 'visit_count', 'last_visited_at')
    list_filter = ('country', 'device_type', 'device_os', 'browser', 'first_visited_at', 'last_visited_at')
    search_fields = ('ip_address', 'country', 'city', 'path', 'referrer')
    readonly_fields = ('ip_address', 'session_key', 'country', 'country_code', 'city', 'device_type', 'device_os', 'browser', 'user_agent', 'path', 'referrer', 'visit_count', 'first_visited_at', 'last_visited_at')
    ordering = ('-last_visited_at',)


@admin.register(HomePageSetting)
class HomePageSettingAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Homepage Hero Artwork & Visuals", {
            'fields': ('title', 'hero_background_image', 'hero_mobile_image'),
            'description': "Configure desktop hero background artwork and mobile visual. If left empty, default static platform assets are used."
        }),
        ("Ecosystem & Trust Section Imagery", {
            'fields': ('ecosystem_image', 'trust_security_image'),
            'description': "Replace images in 'Complete Healthcare Talent Ecosystem' and 'Trust by Design'."
        }),
        ("Partners Banner Strip Fallback", {
            'fields': ('partners_strip_image',),
            'description': "Consolidated partner strip banner (used if individual partner organizations below are not added)."
        }),
        ("Social Media Platforms (Homepage & Footer)", {
            'fields': (
                'linkedin_url',
                'twitter_url',
                'facebook_url',
                'instagram_url',
                'youtube_url',
                'whatsapp_url',
            ),
            'description': "Provide links to your social media profiles. Only platforms with an entered URL will be displayed to visitors on the homepage and footer."
        }),
        ("Metadata", {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        # Prevent creating multiple setting instances
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PartnerOrganization)
class PartnerOrganizationAdmin(admin.ModelAdmin):
    list_display = ('logo_thumbnail', 'name', 'website_url', 'display_order', 'is_active', 'created_at')
    list_display_links = ('name', 'logo_thumbnail')
    list_editable = ('display_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'website_url')
    ordering = ('display_order', 'id')

    def logo_thumbnail(self, obj):
        if obj.logo:
            return format_html(
                '<div style="width: 70px; height: 35px; background: #0f172a; border-radius: 6px; display: flex; align-items: center; justify-content: center; padding: 3px;">'
                '<img src="{}" style="max-height: 28px; max-width: 60px; object-fit: contain;">'
                '</div>',
                obj.logo.url
            )
        return mark_safe('<span style="color: #94a3b8;">No logo</span>')
    logo_thumbnail.short_description = 'Logo'


@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'inquiry_type', 'subject', 'is_resolved', 'created_at')
    list_filter = ('inquiry_type', 'is_resolved', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message', 'notes')
    list_editable = ('is_resolved',)
    readonly_fields = ('name', 'email', 'phone', 'inquiry_type', 'subject', 'message', 'created_at', 'updated_at')
    fieldsets = (
        ("Inquiry Details", {
            'fields': ('name', 'email', 'phone', 'inquiry_type', 'subject', 'message', 'created_at')
        }),
        ("Resolution & Notes", {
            'fields': ('is_resolved', 'notes', 'updated_at')
        }),
    )
    ordering = ('-created_at',)
