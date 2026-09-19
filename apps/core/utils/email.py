import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

logger = logging.getLogger(__name__)

def send_kodafriq_email(subject, template_name, context, recipient_list):
    """
    Dispatch a branded HTML email to one or more recipients.
    Falls back gracefully to logger if mail delivery fails.
    """
    if not recipient_list:
        return False

    context.setdefault('PLATFORM_NAME', 'Kodafriq Data Management Solutions')
    context.setdefault('PLATFORM_URL', getattr(settings, 'PLATFORM_URL', 'http://localhost:8000'))

    try:
        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'notifications@kodafriq.com')

        send_mail(
            subject=f"[Kodafriq] {subject}",
            message=plain_message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=True
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to send email to {recipient_list}: {e}")
        return False
