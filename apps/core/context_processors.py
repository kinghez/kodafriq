from datetime import datetime

def platform_context(request):
    homepage_settings = None
    partner_organizations = []

    try:
        from .models import HomePageSetting, PartnerOrganization
        homepage_settings = HomePageSetting.get_settings()
        partner_organizations = list(PartnerOrganization.objects.filter(is_active=True).order_by('display_order', 'id'))
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
    }
