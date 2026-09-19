import logging
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect
from django.urls import reverse
from .models import GuestVisit
from .utils.geo_device import get_client_ip, parse_device_info, resolve_ip_country

logger = logging.getLogger(__name__)

# Paths to exclude from visitor tracking (assets, pings, health checks)
EXCLUDED_VISITOR_PREFIXES = (
    '/static/',
    '/media/',
    '/favicon.ico',
    '/__reload__/',
    '/api/health/',
)

class VisitorTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to record guest visits, IP addresses, country, and devices
    for platform traffic intelligence.
    """
    def process_response(self, request, response):
        try:
            path = request.path
            # Only track frontend / web requests
            if any(path.startswith(prefix) for prefix in EXCLUDED_VISITOR_PREFIXES):
                return response
            
            # Don't track static asset responses or error 404s for missing files
            if response.status_code >= 400 and ('.' in path.split('/')[-1]):
                return response

            # Only track unauthenticated guests (registered users tracked via User model)
            if hasattr(request, 'user') and request.user.is_authenticated:
                return response

            ip = get_client_ip(request)
            session_key = request.session.session_key or ''
            if not session_key and hasattr(request.session, 'save'):
                try:
                    request.session.save()
                    session_key = request.session.session_key or ''
                except Exception:
                    pass

            ua = request.META.get('HTTP_USER_AGENT', '')
            device_info = parse_device_info(ua)
            geo = resolve_ip_country(ip, request)

            # Record or increment guest visit
            # Try to find a recent visit from same IP and session within same path
            visit = GuestVisit.objects.filter(
                ip_address=ip,
                path=path[:255]
            ).first()

            if visit:
                visit.visit_count += 1
                visit.country = geo['country']
                visit.country_code = geo['country_code']
                visit.city = geo['city']
                visit.device_type = device_info['device_type']
                visit.device_os = device_info['device_os']
                visit.browser = device_info['browser']
                visit.user_agent = ua[:1000]
                visit.session_key = session_key[:64]
                visit.save(update_fields=[
                    'visit_count', 'country', 'country_code', 'city',
                    'device_type', 'device_os', 'browser', 'user_agent',
                    'session_key', 'last_visited_at'
                ])
            else:
                GuestVisit.objects.create(
                    ip_address=ip,
                    session_key=session_key[:64],
                    country=geo['country'],
                    country_code=geo['country_code'],
                    city=geo['city'],
                    device_type=device_info['device_type'],
                    device_os=device_info['device_os'],
                    browser=device_info['browser'],
                    user_agent=ua[:1000],
                    path=path[:255],
                    referrer=request.META.get('HTTP_REFERER', '')[:255],
                    visit_count=1
                )
        except Exception as e:
            # Never break user response flow due to logging
            logger.debug(f"Visitor tracking error: {e}")

        return response


class AccountSecurityMiddleware(MiddlewareMixin):
    """
    Middleware to enforce account suspensions immediately across active sessions.
    If an account is flagged as suspended, they are logged out and redirected to
    the suspension notice page.
    """
    def process_request(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            if getattr(request.user, 'is_suspended', False):
                suspended_url = reverse('accounts:suspended')
                logout_url = reverse('accounts:logout')
                if request.path not in [suspended_url, logout_url]:
                    reason = request.user.suspension_reason or "Account suspended for security or compliance policy review."
                    auth_logout(request)
                    request.session['suspension_reason'] = reason
                    return redirect('accounts:suspended')
        return None


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to record staff actions, state mutations, and administrative operations
    to maintain comprehensive staff accountability.
    """
    def process_response(self, request, response):
        try:
            user = getattr(request, 'user', None)
            # Only track actions when staff/admin are active or on state-mutating requests
            if user and user.is_authenticated and user.is_kodafriq_staff:
                if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') or '/export/' in request.path:
                    # Avoid logging standard CSRF/session internal pings
                    if any(request.path.startswith(prefix) for prefix in EXCLUDED_VISITOR_PREFIXES):
                        return response

                    from apps.dashboard.models import AuditLog
                    ip = get_client_ip(request)
                    device_info = parse_device_info(request.META.get('HTTP_USER_AGENT', ''))

                    # Determine action summary
                    action_title = f"{request.method} {request.path}"
                    category = 'STAFF_ACTION'
                    if '/admin/' in request.path:
                        category = 'ADMIN_ACTION'
                    elif '/export/' in request.path:
                        category = 'DATA_EXPORT'
                    elif '/verification/' in request.path:
                        category = 'VERIFICATION'

                    AuditLog.objects.create(
                        actor=user,
                        action_category=category,
                        action=action_title[:150],
                        ip_address=ip,
                        device_info=device_info['summary'][:150],
                        http_method=request.method,
                        path=request.path[:255],
                        status_code=response.status_code,
                        details=f"Response status: {response.status_code}"
                    )
        except Exception as e:
            logger.debug(f"AuditLoggingMiddleware error: {e}")

        return response
