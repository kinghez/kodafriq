from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from apps.dashboard.models import log_staff_action, AuditLog
from apps.core.utils.geo_device import get_client_ip, parse_device_info

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    try:
        ip = get_client_ip(request) if request else getattr(user, 'last_login_ip', None)
        device_summary = ""
        if request:
            device_info = parse_device_info(request.META.get('HTTP_USER_AGENT', ''))
            device_summary = device_info.get('summary', '')

        # Update last login telemetry on user object if fields exist
        if hasattr(user, 'last_login_ip'):
            user.last_login_ip = ip
            user.save(update_fields=['last_login_ip'])

        log_staff_action(
            actor=user,
            action="User Login Success",
            action_category=AuditLog.Category.AUTH,
            target_user=user,
            target_entity="User",
            target_id=str(user.pk),
            details=f"Authenticated session initiated for {user.username} ({user.get_role_display()}). Device: {device_summary}",
            request=request
        )
    except Exception:
        pass


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    try:
        if user and user.is_authenticated:
            log_staff_action(
                actor=user,
                action="User Logout",
                action_category=AuditLog.Category.AUTH,
                target_user=user,
                target_entity="User",
                target_id=str(user.pk),
                details=f"User {user.username} terminated their active session.",
                request=request
            )
    except Exception:
        pass


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    try:
        username = credentials.get('username', 'Unknown')
        ip = get_client_ip(request) if request else None
        device_summary = ""
        if request:
            device_info = parse_device_info(request.META.get('HTTP_USER_AGENT', ''))
            device_summary = device_info.get('summary', '')

        AuditLog.objects.create(
            actor=None,
            action_category=AuditLog.Category.AUTH,
            action="Failed Login Attempt",
            target_entity="User",
            details=f"Failed authentication attempt for username '{username}'. Device: {device_summary}",
            ip_address=ip,
            device_info=device_summary[:150],
            http_method=request.method if request else "POST",
            path=request.path[:255] if request else "/accounts/login/",
            status_code=401
        )
    except Exception:
        pass
