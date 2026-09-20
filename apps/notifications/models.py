from django.db import models
from django.conf import settings
from django.contrib.auth.models import Group


class NotificationBroadcast(models.Model):
    class Channel(models.TextChoices):
        IN_APP = 'IN_APP', 'In-App Notification Only'
        EMAIL = 'EMAIL', 'Email Broadcast Only'
        BOTH = 'BOTH', 'Both In-App & Email'

    class TargetType(models.TextChoices):
        SINGLE_USER = 'SINGLE_USER', 'Single Specific User'
        MULTIPLE_USERS = 'MULTIPLE_USERS', 'Multiple Specific Users'
        ALL_EMPLOYERS = 'ALL_EMPLOYERS', 'All Employers'
        ALL_PROFESSIONALS = 'ALL_PROFESSIONALS', 'All Healthcare Professionals (Candidates)'
        ALL_ADMINS = 'ALL_ADMINS', 'All Administrators & Staff'
        ALL_USERS = 'ALL_USERS', 'All Platform Users'
        GROUP = 'GROUP', 'Django User Group'

    class NotificationType(models.TextChoices):
        SYSTEM = 'SYSTEM', 'Platform Announcement'
        SECURITY = 'SECURITY', 'Security & Account Notice'
        URGENT = 'URGENT', 'Urgent Critical Alert'
        JOB_MATCH = 'JOB_MATCH', 'Job Opportunity Alert'
        ASSESSMENT = 'ASSESSMENT', 'Clinical Assessment Notice'
        CERTIFICATE = 'CERTIFICATE', 'Training & Certification Notice'
        GENERAL = 'GENERAL', 'General Communication'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_broadcasts'
    )
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.IN_APP,
        help_text="Delivery channel for this communication"
    )
    target_type = models.CharField(
        max_length=30,
        choices=TargetType.choices,
        default=TargetType.ALL_USERS,
        help_text="Target audience category"
    )
    target_group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notification_broadcasts',
        help_text="Target Django auth group if target_type is GROUP"
    )
    target_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='targeted_broadcasts',
        help_text="Target users if single or multiple users are selected"
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM,
        help_text="Classification for styling and icon"
    )
    title = models.CharField(max_length=255, verbose_name="Subject / Title")
    message = models.TextField(verbose_name="Message / Body Content")
    action_url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Action Link (URL)",
        help_text="Optional link target for in-app click or email CTA button"
    )
    action_button_text = models.CharField(
        max_length=80,
        blank=True,
        default="View Details",
        verbose_name="Action Button Label"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    total_recipients = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)

    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification Broadcast'
        verbose_name_plural = 'Notification Broadcasts'

    def __str__(self):
        return f"[{self.get_channel_display()}] {self.title} ({self.get_target_type_display()})"

    @property
    def is_delivered(self):
        return self.status == self.Status.SENT


class BroadcastDeliveryLog(models.Model):
    class DeliveryStatus(models.TextChoices):
        SUCCESS = 'SUCCESS', 'Delivered'
        FAILED = 'FAILED', 'Delivery Failed'
        SKIPPED = 'SKIPPED', 'Skipped'

    broadcast = models.ForeignKey(
        NotificationBroadcast,
        on_delete=models.CASCADE,
        related_name='delivery_logs'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='broadcast_deliveries'
    )
    channel = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.SUCCESS
    )
    error_message = models.TextField(blank=True)
    delivered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-delivered_at']
        verbose_name = 'Broadcast Delivery Log'
        verbose_name_plural = 'Broadcast Delivery Logs'

    def __str__(self):
        return f"Delivery to {self.recipient} [{self.channel}]: {self.status}"
