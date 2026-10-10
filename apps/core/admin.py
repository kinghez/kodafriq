from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import GuestVisit, HomePageSetting, PartnerOrganization, ContactInquiry, FAQItem, LegalPage, Announcement


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


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'display_order', 'is_active', 'updated_at')
    list_editable = ('display_order', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('question', 'answer')
    ordering = ('display_order', 'id')
    fieldsets = (
        ("Question & Category", {
            'fields': ('question', 'category', 'display_order', 'is_active')
        }),
        ("Answer Content", {
            'fields': ('answer',),
            'description': "Provide the complete, clear answer for visitors."
        }),
    )


@admin.register(LegalPage)
class LegalPageAdmin(admin.ModelAdmin):
    list_display = ('title', 'page_type', 'slug', 'last_updated_date', 'is_published', 'updated_at')
    list_editable = ('is_published',)
    list_filter = ('page_type', 'is_published')
    search_fields = ('title', 'summary', 'content')
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        ("Document Configuration", {
            'fields': ('title', 'page_type', 'slug', 'last_updated_date', 'is_published'),
            'description': "Choose document type (Privacy Policy or Terms of Service), page title, and display date."
        }),
        ("Overview Summary", {
            'fields': ('summary',),
            'description': "Executive summary displayed in the header card."
        }),
        ("Full Legal Content (HTML / Text)", {
            'fields': ('content',),
            'description': "Complete legal text. Supports clean HTML formatting, sections, lists, and callout blocks."
        }),
        ("System Metadata", {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('updated_at',)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        'thumbnail_preview',
        'title',
        'eyebrow_badge',
        'target_placement',
        'display_mode',
        'popup_trigger_type',
        'is_active',
        'priority',
        'updated_at',
    )
    list_display_links = ('thumbnail_preview', 'title')
    list_editable = ('is_active', 'priority')
    list_filter = (
        'is_active',
        'target_placement',
        'display_mode',
        'content_format',
        'popup_trigger_type',
    )
    search_fields = ('title', 'eyebrow_badge', 'headline', 'body_text')
    readonly_fields = ('image_preview_primary', 'image_preview_secondary', 'created_at', 'updated_at')
    actions = ['make_active', 'make_inactive']

    fieldsets = (
        ("Announcement Headline & Core Content", {
            'fields': ('title', 'eyebrow_badge', 'headline', 'body_text', 'content_format'),
            'description': "Configure the title, category badge, and announcement body text. Choose layout style (full combo, image only, text only, etc.)."
        }),
        ("Event Schedule & Live Timing", {
            'fields': ('event_datetime_text', 'event_location_text', 'event_datetime', 'start_datetime', 'end_datetime'),
            'description': "Display date/time text (e.g. Saturday 10 October 2026 5:00 PM UK), location, and optional automated start/end schedule."
        }),
        ("Visual Posters & Promotional Flyers", {
            'fields': ('image', 'image_preview_primary', 'secondary_image', 'image_preview_secondary', 'image_alt_text'),
            'description': "Upload event posters/flyers. When both primary and secondary images are uploaded, visitors can toggle between flyers in the modal."
        }),
        ("Call-to-Action Buttons & Links", {
            'fields': (
                'primary_action_text',
                'primary_action_url',
                'primary_action_new_tab',
                'secondary_action_text',
                'secondary_action_url',
            ),
            'description': "Configure meeting links (e.g. Google Meet link https://calendar.app.google/ox5GwEg89EsPeYJ39) and secondary actions."
        }),
        ("Display Placement & Popup Trigger Behavior", {
            'fields': (
                'target_placement',
                'display_mode',
                'popup_trigger_type',
                'popup_delay_seconds',
                'random_min_interval_seconds',
                'random_max_interval_seconds',
                'allow_dismiss',
                'remember_dismissal_hours',
            ),
            'description': "Choose where this announcement appears (Homepage, Dashboards, or Both), format (Top Banner, Modal Popup, or Both), and trigger timing (Stay Duration delay or random periodic intervals)."
        }),
        ("Master Visibility & Priority", {
            'fields': ('is_active', 'priority', 'created_at', 'updated_at'),
            'description': "Master switch: Check to turn ON, uncheck to turn OFF immediately at any time."
        }),
    )

    def thumbnail_preview(self, obj):
        img_url = obj.image.url if obj.image else (obj.secondary_image.url if obj.secondary_image else None)
        if img_url:
            return format_html(
                '<div style="width: 54px; height: 38px; border-radius: 6px; overflow: hidden; background: #0A1128; border: 1px solid #1e293b; display: flex; align-items: center; justify-content: center;">'
                '<img src="{}" style="max-width: 100%; max-height: 100%; object-fit: cover;">'
                '</div>',
                img_url
            )
        return mark_safe('<span style="color: #64748b; font-size: 0.8rem;">Text Only</span>')
    thumbnail_preview.short_description = "Flyer"

    def image_preview_primary(self, obj):
        if obj.image:
            return format_html(
                '<div style="max-width: 320px; border-radius: 8px; overflow: hidden; border: 1px solid #334155; margin-top: 6px;">'
                '<img src="{}" style="width: 100%; height: auto; display: block;">'
                '</div>',
                obj.image.url
            )
        return "No primary image uploaded yet."
    image_preview_primary.short_description = "Primary Flyer Preview"

    def image_preview_secondary(self, obj):
        if obj.secondary_image:
            return format_html(
                '<div style="max-width: 320px; border-radius: 8px; overflow: hidden; border: 1px solid #334155; margin-top: 6px;">'
                '<img src="{}" style="width: 100%; height: auto; display: block;">'
                '</div>',
                obj.secondary_image.url
            )
        return "No secondary image uploaded yet."
    image_preview_secondary.short_description = "Secondary Flyer Preview"

    @admin.action(description="Activate selected announcements")
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} announcement(s) successfully activated.")

    @admin.action(description="Deactivate selected announcements")
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} announcement(s) successfully deactivated.")
