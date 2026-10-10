from django.db import models

class GuestVisit(models.Model):
    """
    Tracks visitor activity, IP address, country/location, device, and browser
    across the Kodafriq platform for analytics, security, and traffic intelligence.
    """
    ip_address = models.GenericIPAddressField(db_index=True)
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    country = models.CharField(max_length=100, default='Unknown', db_index=True)
    country_code = models.CharField(max_length=10, blank=True)
    city = models.CharField(max_length=100, blank=True)
    device_type = models.CharField(max_length=30, default='Desktop')
    device_os = models.CharField(max_length=60, blank=True)
    browser = models.CharField(max_length=60, blank=True)
    user_agent = models.TextField(blank=True)
    path = models.CharField(max_length=255)
    referrer = models.CharField(max_length=255, blank=True)
    visit_count = models.PositiveIntegerField(default=1)
    first_visited_at = models.DateTimeField(auto_now_add=True)
    last_visited_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_visited_at']
        verbose_name = 'Guest Visit'
        verbose_name_plural = 'Guest Visits'

    def __str__(self):
        return f"{self.ip_address} ({self.country}) - {self.path} [{self.device_type}]"


class HomePageSetting(models.Model):
    """
    Singleton model to manage customizable homepage assets and artwork from Django Admin.
    """
    title = models.CharField(max_length=100, default="Homepage Configuration")
    hero_background_image = models.ImageField(
        upload_to='homepage/',
        blank=True,
        null=True,
        verbose_name="Hero Desktop Artwork (Right Side Background)",
        help_text="Desktop hero background artwork (Recommended: 1920x1080 transparent or blended PNG/JPG). Leave blank for default."
    )
    hero_mobile_image = models.ImageField(
        upload_to='homepage/',
        blank=True,
        null=True,
        verbose_name="Hero Mobile Visual Image",
        help_text="Mobile hero visual image shown below the CTA on mobile devices. Leave blank for default."
    )
    ecosystem_image = models.ImageField(
        upload_to='homepage/',
        blank=True,
        null=True,
        verbose_name="Ecosystem Section Doctor Visual",
        help_text="Healthcare Talent Ecosystem visual image. Leave blank for default."
    )
    trust_security_image = models.ImageField(
        upload_to='homepage/',
        blank=True,
        null=True,
        verbose_name="Trust & Security Section Visual",
        help_text="Trust by Design section image. Leave blank for default."
    )
    partners_strip_image = models.ImageField(
        upload_to='homepage/',
        blank=True,
        null=True,
        verbose_name="Partners Banner Strip Image (Fallback)",
        help_text="Consolidated partner logos strip image (used if individual partner organizations are not added). Leave blank for default."
    )
    # Social Media Platforms (Configurable from Django Admin)
    linkedin_url = models.URLField(
        blank=True,
        verbose_name="LinkedIn URL",
        help_text="Company/Organization LinkedIn profile or page URL. Leave empty to hide on website."
    )
    twitter_url = models.URLField(
        blank=True,
        verbose_name="X (Twitter) URL",
        help_text="X / Twitter profile URL. Leave empty to hide on website."
    )
    facebook_url = models.URLField(
        blank=True,
        verbose_name="Facebook URL",
        help_text="Facebook page URL. Leave empty to hide on website."
    )
    instagram_url = models.URLField(
        blank=True,
        verbose_name="Instagram URL",
        help_text="Instagram profile URL. Leave empty to hide on website."
    )
    youtube_url = models.URLField(
        blank=True,
        verbose_name="YouTube URL",
        help_text="YouTube channel or video URL. Leave empty to hide on website."
    )
    whatsapp_url = models.URLField(
        blank=True,
        verbose_name="WhatsApp URL",
        help_text="WhatsApp contact or business link. Leave empty to hide on website."
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Homepage Image & Asset Settings'
        verbose_name_plural = 'Homepage Image & Asset Settings'

    def __str__(self):
        return self.title

    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class PartnerOrganization(models.Model):
    """
    Individual partner / trusted organization logos displayed in 'OUR PARTNERS & TRUSTED ORGANIZATIONS'.
    """
    name = models.CharField(max_length=150, help_text="Organization name (e.g. World Health Organization, Johns Hopkins, NHS)")
    logo = models.ImageField(upload_to='partners/', help_text="Upload partner logo (transparent PNG or SVG recommended)")
    website_url = models.URLField(blank=True, help_text="Optional website link (makes logo clickable)")
    display_order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first (e.g. 1, 2, 3)")
    is_active = models.BooleanField(default=True, help_text="Toggle visibility on homepage")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = 'Partner & Trusted Organization'
        verbose_name_plural = 'Partners & Trusted Organizations'

    def __str__(self):
        return self.name


class ContactInquiry(models.Model):
    """
    Stores contact and enterprise inquiries submitted from the website Contact Us section.
    """
    ROLE_CHOICES = [
        ('employer', 'Healthcare Employer / Facility'),
        ('candidate', 'Healthcare Professional / Candidate'),
        ('partner', 'Institution / Strategic Partner'),
        ('general', 'General Inquiry / Support'),
    ]

    name = models.CharField(max_length=150, verbose_name="Full Name")
    email = models.EmailField(verbose_name="Work / Contact Email")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Phone Number (Optional)")
    inquiry_type = models.CharField(max_length=40, choices=ROLE_CHOICES, default='employer', verbose_name="Inquiry Type")
    subject = models.CharField(max_length=200, verbose_name="Subject")
    message = models.TextField(verbose_name="Message")
    is_resolved = models.BooleanField(default=False, verbose_name="Resolved / Followed Up")
    notes = models.TextField(blank=True, verbose_name="Internal Admin Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contact Inquiry'
        verbose_name_plural = 'Contact Inquiries'

    def __str__(self):
        return f"{self.name} ({self.get_inquiry_type_display()}) - {self.subject}"


class FAQItem(models.Model):
    """
    Stores frequently asked questions displayed on the homepage.
    Administrators can add, update, reorder, or toggle active status from Django Admin.
    """
    CATEGORY_CHOICES = [
        ('verification', 'Talent Verification & Credentialing'),
        ('employers', 'Employers & Hiring Process'),
        ('payments', 'Contracts & Milestone Payments'),
        ('security', 'Data Security & Compliance'),
        ('general', 'General Inquiries'),
    ]

    question = models.CharField(max_length=255, help_text="The question title displayed on the homepage.")
    answer = models.TextField(help_text="Detailed answer text. Supports standard text or paragraphs.")
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, default='verification', help_text="Category group for organization.")
    display_order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first (e.g. 1, 2, 3...)")
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide from the homepage without deleting.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = 'FAQ Item'
        verbose_name_plural = 'FAQ Items'

    def __str__(self):
        return self.question


class LegalPage(models.Model):
    """
    Stores legal documents such as Privacy Policy and Terms of Service.
    Administrators can edit headings, summaries, and full text directly from Django Admin.
    """
    PAGE_TYPE_CHOICES = [
        ('privacy', 'Privacy Policy'),
        ('terms', 'Terms of Service'),
    ]

    page_type = models.CharField(max_length=30, choices=PAGE_TYPE_CHOICES, unique=True, help_text="Select whether this is the Privacy Policy or Terms of Service.")
    title = models.CharField(max_length=150, help_text="Page title displayed in the hero banner.")
    slug = models.SlugField(max_length=60, unique=True, help_text="URL slug (e.g. privacy-policy or terms-of-service).")
    last_updated_date = models.CharField(max_length=60, default="October 6, 2026", help_text="Text display of last revised date (e.g. October 6, 2026).")
    summary = models.TextField(blank=True, help_text="High-level overview summary shown at the top of the legal document.")
    content = models.TextField(help_text="Full legal content. Supports HTML markup (headings, paragraphs, lists, callout boxes).")
    is_published = models.BooleanField(default=True, help_text="Toggle visibility on the website.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Legal Page'
        verbose_name_plural = 'Legal Pages'

    def __str__(self):
        return f"{self.get_page_type_display()} ({self.title})"


class Announcement(models.Model):
    """
    Site-wide and Dashboard Announcements & Launch Alerts.
    Completely configurable and toggleable by Administrators in Django Admin.
    Supports modal popups, top banners, image flyers, action buttons, custom intervals/delays,
    and granular placement targeting (Homepage, Dashboards, or Both).
    """
    TARGET_PLACEMENT_CHOICES = [
        ('both', 'Both Homepage and Dashboards'),
        ('homepage', 'Homepage Only'),
        ('dashboard', 'Dashboards Only'),
    ]

    DISPLAY_MODE_CHOICES = [
        ('both', 'Both Top Banner & Modal Popup'),
        ('popup', 'Modal Popup Dialog Only'),
        ('banner', 'Top Banner Only'),
    ]

    CONTENT_FORMAT_CHOICES = [
        ('full', 'Full Rich Combo (Images, Text, Details & Action Links)'),
        ('images_only', 'Image / Flyer Only (Full Visual)'),
        ('images_with_links', 'Image / Flyer with Action Links'),
        ('text_only', 'Text Only (No Images, with/without Links)'),
        ('text_with_links', 'Text with Action Links Only'),
        ('text_with_images', 'Text with Images (No Action Links)'),
    ]

    POPUP_TRIGGER_CHOICES = [
        ('delay', 'Stay Duration Delay (Pops up after visitor stays on page)'),
        ('random_interval', 'Random Time Intervals (Pops up periodically at random intervals)'),
        ('immediate', 'Immediate (Pops up immediately on page load)'),
    ]

    # Core Identifiers
    title = models.CharField(
        max_length=200,
        help_text="Announcement title (e.g. 'Kodafriq Official Platform Launch')."
    )
    eyebrow_badge = models.CharField(
        max_length=80,
        default="OFFICIAL LAUNCH EVENT",
        help_text="Small pill tag displayed above title (e.g. 'OFFICIAL LAUNCH EVENT', 'LIVE TODAY', 'NEW UPDATE')."
    )
    headline = models.CharField(
        max_length=255,
        blank=True,
        help_text="Subheading or slogan (e.g. 'Global Healthcare Talent Without Borders – Connecting skilled professionals with global opportunities')."
    )
    body_text = models.TextField(
        blank=True,
        help_text="Detailed announcement description, agenda, or highlights. Supports multiple paragraphs."
    )

    # Event Details (For webinars, launches, live streams)
    event_datetime = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Exact scheduled date & time of the event (optional, used for countdown / badges)."
    )
    event_datetime_text = models.CharField(
        max_length=150,
        blank=True,
        default="Saturday, 10 October 2026 • 5:00 PM UK / 4:00 PM GHANA",
        help_text="Human-readable event date/time string displayed to users."
    )
    event_location_text = models.CharField(
        max_length=150,
        blank=True,
        default="Online (Google Meet)",
        help_text="Event venue or format (e.g. 'Online (Google Meet)', 'Virtual Broadcast')."
    )

    # Visual Imagery (Flyers / Banners)
    image = models.ImageField(
        upload_to='announcements/',
        blank=True,
        null=True,
        verbose_name="Primary Image / Flyer",
        help_text="Primary flyer or event poster (e.g. Official Launch Agenda flyer)."
    )
    secondary_image = models.ImageField(
        upload_to='announcements/',
        blank=True,
        null=True,
        verbose_name="Secondary Image / Flyer",
        help_text="Optional secondary poster (e.g. Keynote Speakers flyer). When provided, users can switch between flyers in the modal."
    )
    image_alt_text = models.CharField(
        max_length=200,
        blank=True,
        default="Kodafriq Launch Event Flyer",
        help_text="Accessibility alt text for the images."
    )

    # Action Links & Call-To-Action (CTAs)
    primary_action_text = models.CharField(
        max_length=80,
        blank=True,
        default="Join Launch Meeting",
        help_text="Text for primary button (e.g. 'Join Launch Meeting', 'Join Us Live Online')."
    )
    primary_action_url = models.URLField(
        blank=True,
        default="https://calendar.app.google/ox5GwEg89EsPeYJ39",
        help_text="Link for primary button (e.g. Google Meet link, Google Calendar event link)."
    )
    primary_action_new_tab = models.BooleanField(
        default=True,
        help_text="Open primary action link in a new browser tab."
    )
    secondary_action_text = models.CharField(
        max_length=80,
        blank=True,
        default="Register as Candidate",
        help_text="Optional secondary button text (e.g. 'Register as Candidate', 'Explore Platform')."
    )
    secondary_action_url = models.CharField(
        max_length=255,
        blank=True,
        default="/accounts/register/candidate/",
        help_text="Optional secondary link (can be internal URL like /accounts/register/candidate/ or external URL)."
    )

    # Display Placement & Format Controls
    target_placement = models.CharField(
        max_length=20,
        choices=TARGET_PLACEMENT_CHOICES,
        default='both',
        help_text="Where this announcement will be displayed."
    )
    display_mode = models.CharField(
        max_length=20,
        choices=DISPLAY_MODE_CHOICES,
        default='both',
        help_text="Choose whether this appears as a Top Banner, a Modal Popup, or Both."
    )
    content_format = models.CharField(
        max_length=20,
        choices=CONTENT_FORMAT_CHOICES,
        default='full',
        help_text="Structure of the announcement: Just text, text + links, text + images, image only, image + links, or full combo."
    )

    # Popup Timing & Trigger Behavior
    popup_trigger_type = models.CharField(
        max_length=20,
        choices=POPUP_TRIGGER_CHOICES,
        default='delay',
        help_text="When/how the modal popup triggers: after staying on page, at random time intervals, or immediately."
    )
    popup_delay_seconds = models.PositiveIntegerField(
        default=3,
        help_text="For 'Stay Duration': seconds after page load before the modal pops up (e.g. 3 or 5 seconds)."
    )
    random_min_interval_seconds = models.PositiveIntegerField(
        default=20,
        help_text="For 'Random Intervals': minimum seconds before the popup triggers."
    )
    random_max_interval_seconds = models.PositiveIntegerField(
        default=60,
        help_text="For 'Random Intervals': maximum seconds before the popup triggers."
    )
    allow_dismiss = models.BooleanField(
        default=True,
        help_text="Allow users to dismiss/close the popup."
    )
    remember_dismissal_hours = models.PositiveIntegerField(
        default=0,
        help_text="Hours to keep modal closed after user dismisses it (0 = re-check on new page/session or interval)."
    )

    # Master Toggle & Scheduling
    is_active = models.BooleanField(
        default=True,
        help_text="Master switch: Check to turn ON announcement, uncheck to turn OFF immediately at any time."
    )
    start_datetime = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Optional auto-start schedule date/time (leave empty to show immediately)."
    )
    end_datetime = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Optional auto-expire date/time (leave empty to show indefinitely until turned off)."
    )
    priority = models.PositiveIntegerField(
        default=10,
        help_text="Higher priority announcements display before lower priority ones if multiple are active."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', '-created_at']
        verbose_name = 'Platform Announcement & Launch Event'
        verbose_name_plural = 'Platform Announcements & Launch Events'

    def __str__(self):
        status = 'ACTIVE' if self.is_active else 'INACTIVE'
        return f'[{status}] {self.title} ({self.get_target_placement_display()})'

    @property
    def has_images(self):
        return bool(self.image or self.secondary_image)

    @property
    def has_links(self):
        return bool(self.primary_action_url or self.secondary_action_url)
