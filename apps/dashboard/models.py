from django.db import models
from django.conf import settings

class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=150)
    target_entity = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=50, blank=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.action} by {self.user}"


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        CERTIFICATE = 'CERTIFICATE', 'Certificate Earned'
        ASSESSMENT = 'ASSESSMENT', 'Assessment Result'
        SCORE_BOOST = 'SCORE_BOOST', 'Verified Score Update'
        APPLICATION = 'APPLICATION', 'Application Status'
        JOB_MATCH = 'JOB_MATCH', 'Job Opportunity'
        SYSTEM = 'SYSTEM', 'System Notice'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM
    )
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notification_type}] {self.title} for {self.recipient}"


def send_notification(recipient, title, message, notification_type=Notification.NotificationType.SYSTEM, link=""):
    """Helper function to dispatch persistent in-app notifications."""
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link
    )
