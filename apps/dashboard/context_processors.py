from django.db.models import Q
from apps.dashboard.models import DirectMessage

def notification_context(request):
    """
    Context processor to inject unread notification count, unread message count,
    and recent notifications into all templates for authenticated users.
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {
            'unread_notifications_count': 0,
            'unread_messages_count': 0,
            'recent_notifications': [],
        }
    
    user = request.user
    unread_notifications_count = user.notifications.filter(is_read=False).count()
    recent = user.notifications.all()[:5]

    unread_messages_count = DirectMessage.objects.filter(
        is_read=False
    ).exclude(
        sender=user
    ).filter(
        Q(conversation__employer__user=user) | Q(conversation__candidate__user=user)
    ).count()

    return {
        'unread_notifications_count': unread_notifications_count,
        'unread_messages_count': unread_messages_count,
        'recent_notifications': recent,
    }
