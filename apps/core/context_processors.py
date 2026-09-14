from datetime import datetime

def platform_context(request):
    return {
        'PLATFORM_NAME': 'Kodafriq Data Management Solutions',
        'PLATFORM_SHORT_NAME': 'Kodafriq',
        'PLATFORM_TAGLINE': 'Digital Healthcare Talent Verification & Employer Matching',
        'CURRENT_YEAR': datetime.now().year,
        'INITIAL_SECTOR': 'Healthcare – Medical Coding, Medical Billing & Revenue Cycle Management',
    }
