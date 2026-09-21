import logging
from django.utils import timezone
from django.db import models
from django.contrib.auth import get_user_model
from .models import NotificationBroadcast, BroadcastDeliveryLog
from apps.dashboard.models import Notification
from apps.core.utils.email import send_kodafriq_email

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationService:
    @staticmethod
    def resolve_recipients(broadcast):
        """
        Returns an active, non-suspended QuerySet of users targeted by the broadcast.
        """
        target_type = broadcast.target_type

        if target_type == NotificationBroadcast.TargetType.SINGLE_USER:
            if broadcast.target_single_user:
                return User.objects.filter(pk=broadcast.target_single_user.pk, is_active=True, is_suspended=False)
            return broadcast.target_users.filter(is_active=True, is_suspended=False).distinct()

        elif target_type == NotificationBroadcast.TargetType.MULTIPLE_USERS:
            return broadcast.target_users.filter(is_active=True, is_suspended=False).distinct()

        elif target_type == NotificationBroadcast.TargetType.ALL_EMPLOYERS:
            return User.objects.filter(role='EMPLOYER', is_active=True, is_suspended=False)

        elif target_type == NotificationBroadcast.TargetType.ALL_PROFESSIONALS:
            return User.objects.filter(role='CANDIDATE', is_active=True, is_suspended=False)

        elif target_type == NotificationBroadcast.TargetType.ALL_ADMINS:
            return User.objects.filter(
                models.Q(role__in=['STAFF', 'ADMIN']) | models.Q(is_staff=True) | models.Q(is_superuser=True),
                is_active=True
            ).distinct()

        elif target_type == NotificationBroadcast.TargetType.GROUP:
            if broadcast.target_group:
                return User.objects.filter(
                    groups=broadcast.target_group,
                    is_active=True,
                    is_suspended=False
                ).distinct()
            return User.objects.none()

        elif target_type == NotificationBroadcast.TargetType.ALL_USERS:
            return User.objects.filter(is_active=True, is_suspended=False)

        return User.objects.none()

    @classmethod
    def dispatch_broadcast(cls, broadcast):
        """
        Executes delivery for a broadcast message across designated channels (IN_APP, EMAIL, BOTH).
        Logs each recipient delivery in BroadcastDeliveryLog and updates broadcast totals.
        """
        recipients = cls.resolve_recipients(broadcast)
        total_recipients = recipients.count()

        channel = broadcast.channel
        do_in_app = channel in (NotificationBroadcast.Channel.IN_APP, NotificationBroadcast.Channel.BOTH)
        do_email = channel in (NotificationBroadcast.Channel.EMAIL, NotificationBroadcast.Channel.BOTH)

        success_count = 0
        failure_count = 0

        for user in recipients:
            user_has_error = False

            # 1. In-App Notification Dispatch
            if do_in_app:
                try:
                    Notification.objects.create(
                        recipient=user,
                        title=broadcast.title,
                        message=broadcast.message,
                        notification_type=broadcast.notification_type,
                        link=broadcast.action_url or ""
                    )
                    BroadcastDeliveryLog.objects.create(
                        broadcast=broadcast,
                        recipient=user,
                        channel='IN_APP',
                        status=BroadcastDeliveryLog.DeliveryStatus.SUCCESS
                    )
                except Exception as e:
                    user_has_error = True
                    logger.error(f"Error creating in-app notification for {user}: {e}")
                    BroadcastDeliveryLog.objects.create(
                        broadcast=broadcast,
                        recipient=user,
                        channel='IN_APP',
                        status=BroadcastDeliveryLog.DeliveryStatus.FAILED,
                        error_message=str(e)
                    )

            # 2. Email Broadcast Dispatch
            if do_email:
                if user.email:
                    try:
                        email_sent = send_kodafriq_email(
                            subject=broadcast.title,
                            template_name='emails/broadcast_email.html',
                            context={
                                'title': broadcast.title,
                                'recipient_name': user.get_full_name() or user.username,
                                'message': broadcast.message,
                                'action_url': broadcast.action_url,
                                'action_text': broadcast.action_button_text or "View Details",
                                'notification_type': broadcast.get_notification_type_display(),
                            },
                            recipient_list=[user.email]
                        )
                        if email_sent:
                            BroadcastDeliveryLog.objects.create(
                                broadcast=broadcast,
                                recipient=user,
                                channel='EMAIL',
                                status=BroadcastDeliveryLog.DeliveryStatus.SUCCESS
                            )
                        else:
                            user_has_error = True
                            BroadcastDeliveryLog.objects.create(
                                broadcast=broadcast,
                                recipient=user,
                                channel='EMAIL',
                                status=BroadcastDeliveryLog.DeliveryStatus.FAILED,
                                error_message="Mail backend returned false or failed delivery"
                            )
                    except Exception as e:
                        user_has_error = True
                        logger.error(f"Error dispatching email to {user.email}: {e}")
                        BroadcastDeliveryLog.objects.create(
                            broadcast=broadcast,
                            recipient=user,
                            channel='EMAIL',
                            status=BroadcastDeliveryLog.DeliveryStatus.FAILED,
                            error_message=str(e)
                        )
                else:
                    BroadcastDeliveryLog.objects.create(
                        broadcast=broadcast,
                        recipient=user,
                        channel='EMAIL',
                        status=BroadcastDeliveryLog.DeliveryStatus.SKIPPED,
                        error_message="Recipient has no email address configured"
                    )

            if user_has_error:
                failure_count += 1
            else:
                success_count += 1

        broadcast.total_recipients = total_recipients
        broadcast.success_count = success_count
        broadcast.failure_count = failure_count
        broadcast.status = NotificationBroadcast.Status.SENT
        broadcast.sent_at = timezone.now()
        broadcast.save(update_fields=['total_recipients', 'success_count', 'failure_count', 'status', 'sent_at'])

        return {
            'total_recipients': total_recipients,
            'success_count': success_count,
            'failure_count': failure_count,
        }
