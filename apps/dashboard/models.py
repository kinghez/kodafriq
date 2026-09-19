from django.db import models
from django.conf import settings

class AuditLog(models.Model):
    class Category(models.TextChoices):
        AUTH = 'AUTH', 'Authentication & Security'
        STAFF_ACTION = 'STAFF_ACTION', 'Staff Operation'
        ADMIN_ACTION = 'ADMIN_ACTION', 'Admin Control Panel'
        VERIFICATION = 'VERIFICATION', 'Credential Verification'
        SUSPENSION = 'SUSPENSION', 'Account Suspension'
        SCORING = 'SCORING', 'Score Weight Calibration'
        MODERATION = 'MODERATION', 'Content Moderation'
        DATA_EXPORT = 'DATA_EXPORT', 'Data Export'
        SYSTEM = 'SYSTEM', 'System Automated Event'

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_actions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='legacy_audit_logs'
    )
    action_category = models.CharField(
        max_length=40,
        choices=Category.choices,
        default=Category.STAFF_ACTION,
        db_index=True
    )
    action = models.CharField(max_length=200, db_index=True)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_targets'
    )
    target_entity = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=50, blank=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.CharField(max_length=150, blank=True)
    http_method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=255, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def save(self, *args, **kwargs):
        if self.actor and not self.user:
            self.user = self.actor
        elif self.user and not self.actor:
            self.actor = self.user
        super().save(*args, **kwargs)

    def __str__(self):
        actor_name = self.actor.username if self.actor else (self.user.username if self.user else 'System')
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.action} by {actor_name}"


def log_staff_action(actor, action, action_category=AuditLog.Category.STAFF_ACTION, target_user=None, target_entity="", target_id="", details="", request=None):
    """Helper to record staff and admin actions with IP and device context."""
    ip = None
    device_info = ""
    path = ""
    http_method = ""
    if request:
        from apps.core.utils.geo_device import get_client_ip, parse_device_info
        ip = get_client_ip(request)
        device_info = parse_device_info(request.META.get('HTTP_USER_AGENT', ''))['summary']
        path = request.path[:255]
        http_method = request.method

    return AuditLog.objects.create(
        actor=actor if actor and actor.is_authenticated else None,
        action_category=action_category,
        action=action[:200],
        target_user=target_user,
        target_entity=target_entity[:100],
        target_id=str(target_id)[:50],
        details=details,
        ip_address=ip,
        device_info=device_info[:150],
        http_method=http_method,
        path=path,
        status_code=200
    )


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        CERTIFICATE = 'CERTIFICATE', 'Certificate Earned'
        ASSESSMENT = 'ASSESSMENT', 'Assessment Result'
        SCORE_BOOST = 'SCORE_BOOST', 'Verified Score Update'
        APPLICATION = 'APPLICATION', 'Application Status'
        JOB_MATCH = 'JOB_MATCH', 'Job Opportunity'
        SECURITY = 'SECURITY', 'Security & Account Notice'
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


def send_notification(recipient, title, message, notification_type=Notification.NotificationType.SYSTEM, link="", send_email=True):
    """Helper function to dispatch persistent in-app notifications and trigger email."""
    notif = Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link
    )
    if send_email and getattr(recipient, 'email', None):
        try:
            from apps.core.utils.email import send_kodafriq_email
            send_kodafriq_email(
                subject=title,
                template_name='emails/notification_email.html',
                context={
                    'title': title,
                    'recipient_name': recipient.get_full_name() or recipient.username,
                    'message': message,
                    'action_url': link,
                },
                recipient_list=[recipient.email]
            )
        except Exception:
            pass
    return notif
