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
