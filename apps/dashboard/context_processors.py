def notification_context(request):
    """
    Context processor to inject unread notification count and recent notifications
    into all templates for authenticated users.
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {
            'unread_notifications_count': 0,
            'recent_notifications': [],
        }
    
    unread_count = request.user.notifications.filter(is_read=False).count()
    recent = request.user.notifications.all()[:5]
    return {
        'unread_notifications_count': unread_count,
        'recent_notifications': recent,
    }
