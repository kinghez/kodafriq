from django.contrib import admin
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import GuestVisit, HomePageSetting, PartnerOrganization, ContactInquiry, FAQItem, LegalPage, Announcement, Testimonial


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
            'fields': (
                'title',
                'hero_background_preview',
                'hero_background_image',
                'hero_mobile_preview',
                'hero_mobile_image',
            ),
            'description': "Preview and configure desktop hero background artwork and mobile visual. Live previews below display the currently active images. Upload a new file to replace."
        }),
        ("Ecosystem & Trust Section Imagery", {
            'fields': (
                'ecosystem_image_preview',
                'ecosystem_image',
                'trust_security_preview',
                'trust_security_image',
            ),
            'description': "Preview and replace images in 'Complete Healthcare Talent Ecosystem' and 'Trust by Design'."
        }),
        ("Partners Banner Strip Fallback", {
            'fields': (
                'partners_strip_preview',
                'partners_strip_image',
            ),
            'description': "Consolidated partner strip banner (used if individual partner organizations below are not added)."
        }),
        ("Homepage Testimonials Section Configuration", {
            'fields': (
                'show_testimonials',
                'testimonials_eyebrow',
                'testimonials_title',
                'testimonials_subtitle',
            ),
            'description': "Toggle visibility of the Testimonials section on the homepage, and customize the section heading and description."
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
    readonly_fields = (
        'hero_background_preview',
        'hero_mobile_preview',
        'ecosystem_image_preview',
        'trust_security_preview',
        'partners_strip_preview',
        'updated_at',
    )

    def _render_image_preview(self, custom_img, default_static_path, label):
        if custom_img:
            url = custom_img.url
            badge = '<span style="background: #10B981; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase;">Active Custom Image</span>'
        else:
            url = static(default_static_path)
            badge = '<span style="background: #2563EB; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase;">Active Default Image</span>'

        return format_html(
            '<div style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; margin-bottom: 8px; max-width: 480px;">'
            '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">'
            '<strong style="color: #f8fafc; font-size: 12px;">{}</strong>'
            '{}'
            '</div>'
            '<div style="background: #020e26; border-radius: 6px; padding: 8px; text-align: center; overflow: hidden;">'
            '<a href="{}" target="_blank" title="Click to view full image">'
            '<img src="{}" style="max-height: 120px; max-width: 100%; object-fit: contain; border-radius: 4px;" alt="{}">'
            '</a>'
            '</div>'
            '<div style="margin-top: 6px; font-size: 11px; color: #94a3b8;">'
            'Click image to view in new tab. Choose a new file below to change this image.'
            '</div>'
            '</div>',
            label,
            mark_safe(badge),
            url,
            url,
            label
        )

    def hero_background_preview(self, obj):
        return self._render_image_preview(obj.hero_background_image, 'images/hero_master_1024.png', 'Desktop Hero Background Artwork')
    hero_background_preview.short_description = "Current Desktop Hero Visual"

    def hero_mobile_preview(self, obj):
        return self._render_image_preview(obj.hero_mobile_image, 'images/hero_founder_mobile_blended.png', 'Mobile Hero Visual Image')
    hero_mobile_preview.short_description = "Current Mobile Hero Visual"

    def ecosystem_image_preview(self, obj):
        return self._render_image_preview(obj.ecosystem_image, 'images/ecosystem_doctor_hd.jpg', 'Ecosystem Section Visual')
    ecosystem_image_preview.short_description = "Current Ecosystem Visual"

    def trust_security_preview(self, obj):
        return self._render_image_preview(obj.trust_security_image, 'images/trust_security_hd.jpg', 'Trust & Security Visual')
    trust_security_preview.short_description = "Current Trust Visual"

    def partners_strip_preview(self, obj):
        return self._render_image_preview(obj.partners_strip_image, 'images/partner-logos.png', 'Partners Strip Banner')
    partners_strip_preview.short_description = "Current Partners Strip Visual"

    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PartnerOrganization)
class PartnerOrganizationAdmin(admin.ModelAdmin):
    list_display = ('logo_thumbnail', 'name', 'website_url', 'display_order', 'is_active', 'created_at')
    list_display_links = ('logo_thumbnail', 'name')
    list_editable = ('display_order', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'website_url')
    ordering = ('display_order', 'id')
    readonly_fields = ('logo_form_preview', 'created_at')

    fieldsets = (
        ("Organization Information", {
            'fields': ('name', 'website_url', 'display_order', 'is_active')
        }),
        ("Logo Artwork", {
            'fields': ('logo_form_preview', 'logo'),
            'description': "Upload partner logo (transparent PNG or SVG recommended). See current logo preview above."
        }),
        ("Metadata", {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def logo_thumbnail(self, obj):
        if obj.logo:
            return format_html(
                '<div style="width: 80px; height: 38px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; display: flex; align-items: center; justify-content: center; padding: 4px;">'
                '<img src="{}" style="max-height: 30px; max-width: 72px; object-fit: contain;">'
                '</div>',
                obj.logo.url
            )
        return mark_safe('<span style="color: #94a3b8; font-size: 11px;">No logo</span>')
    logo_thumbnail.short_description = 'Logo'

    def logo_form_preview(self, obj):
        if obj and obj.logo:
            return format_html(
                '<div style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; max-width: 300px; text-align: center;">'
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-height: 60px; max-width: 240px; object-fit: contain;" alt="{}">'
                '</a>'
                '<div style="margin-top: 6px; font-size: 11px; color: #94a3b8;">Current active logo. Upload a new file below to replace it.</div>'
                '</div>',
                obj.logo.url, obj.logo.url, obj.name
            )
        return "No logo uploaded yet."
    logo_form_preview.short_description = "Current Logo Preview"


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('avatar_preview', 'author_name', 'role_title', 'organization', 'rating_stars', 'display_order', 'is_active', 'created_at')
    list_display_links = ('avatar_preview', 'author_name')
    list_editable = ('display_order', 'is_active')
    list_filter = ('is_active', 'rating', 'created_at')
    search_fields = ('author_name', 'role_title', 'organization', 'content')
    ordering = ('display_order', '-created_at')
    readonly_fields = ('avatar_preview_large', 'created_at', 'updated_at')

    fieldsets = (
        ("Author & Healthcare Affiliation", {
            'fields': (
                'author_name',
                'role_title',
                'organization',
                'avatar_preview_large',
                'avatar',
            ),
            'description': "Provide the author's full name, professional title, healthcare organization, and optional headshot photo."
        }),
        ("Rating & Testimonial Quote", {
            'fields': ('rating', 'content'),
            'description': "Select the star rating (1 to 5 stars) and enter the testimonial text or review."
        }),
        ("Display Priority & Visibility", {
            'fields': ('display_order', 'is_active', 'created_at', 'updated_at'),
            'description': "Set display sequence order (lower numbers appear first) and toggle visibility on the website."
        }),
    )

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="width: 36px; height: 36px; border-radius: 50%; object-fit: cover; border: 2px solid #2563EB;">',
                obj.avatar.url
            )
        return format_html(
            '<div style="width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #2563EB, #10B981); color: #ffffff; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700;">'
            '{}'
            '</div>',
            obj.initials
        )
    avatar_preview.short_description = "Avatar"

    def avatar_preview_large(self, obj):
        if obj and obj.avatar:
            return format_html(
                '<div style="margin-bottom: 6px;">'
                '<img src="{}" style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover; border: 2px solid #2563EB; display: block;">'
                '<span style="font-size: 11px; color: #94a3b8;">Current photo</span>'
                '</div>',
                obj.avatar.url
            )
        return "No photo uploaded (initials monogram will be displayed)."
    avatar_preview_large.short_description = "Current Avatar Photo"

    def rating_stars(self, obj):
        stars = "★" * obj.rating + "☆" * (5 - obj.rating)
        return format_html('<span style="color: #F59E0B; font-size: 14px; letter-spacing: 2px;">{}</span>', stars)
    rating_stars.short_description = "Rating"


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
