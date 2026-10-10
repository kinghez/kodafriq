from datetime import datetime
from django.utils import timezone
from django.db import models

def platform_context(request):
    homepage_settings = None
    partner_organizations = []
    active_announcements = []
    active_announcement = None

    try:
        from .models import HomePageSetting, PartnerOrganization, Announcement
        homepage_settings = HomePageSetting.get_settings()
        partner_organizations = list(PartnerOrganization.objects.filter(is_active=True).order_by('display_order', 'id'))

        now = timezone.now()
        announcement_qs = Announcement.objects.filter(is_active=True)
        # Check scheduling window if dates are defined
        announcement_qs = announcement_qs.filter(
            models.Q(start_datetime__isnull=True) | models.Q(start_datetime__lte=now),
            models.Q(end_datetime__isnull=True) | models.Q(end_datetime__gte=now)
        )

        current_path = getattr(request, 'path', '') or ''
        is_dashboard = current_path.startswith('/dashboard')
        is_homepage = (current_path == '/')

        if is_homepage:
            announcement_qs = announcement_qs.filter(target_placement__in=['both', 'homepage'])
        elif is_dashboard:
            announcement_qs = announcement_qs.filter(target_placement__in=['both', 'dashboard'])
        else:
            # Other public/platform pages inherit 'both' or 'homepage' targeting
            announcement_qs = announcement_qs.filter(target_placement__in=['both', 'homepage'])

        active_announcements = list(announcement_qs.order_by('-priority', '-created_at'))
        if active_announcements:
            active_announcement = active_announcements[0]
    except Exception:
        # Avoid crashing during migrations or setup
        pass

    return {
        'PLATFORM_NAME': 'Kodafriq Data Management Solutions',
        'PLATFORM_SHORT_NAME': 'Kodafriq',
        'PLATFORM_TAGLINE': 'Digital Healthcare Talent Verification & Employer Matching',
        'CURRENT_YEAR': datetime.now().year,
        'INITIAL_SECTOR': 'Healthcare – Medical Coding, Medical Billing & Revenue Cycle Management',
        'homepage_settings': homepage_settings,
        'partner_organizations': partner_organizations,
        'active_announcements': active_announcements,
        'active_announcement': active_announcement,
    }
