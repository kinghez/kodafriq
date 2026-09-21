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
