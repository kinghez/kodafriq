"""
Kodafriq IP Geolocation and Device Intelligence Utilities
"""
import re
import urllib.request
import json
from django.core.cache import cache

AFRICAN_AND_GLOBAL_COUNTRIES = [
    # Top African Healthcare Talent & Employer Hubs
    ('Ghana', 'Ghana'),
    ('Nigeria', 'Nigeria'),
    ('Kenya', 'Kenya'),
    ('Rwanda', 'Rwanda'),
    ('South Africa', 'South Africa'),
    ('Egypt', 'Egypt'),
    ('Ethiopia', 'Ethiopia'),
    ('Uganda', 'Uganda'),
    ('Tanzania', 'Tanzania'),
    ('Morocco', 'Morocco'),
    ('Senegal', 'Senegal'),
    ('Cameroon', 'Cameroon'),
    ("Côte d'Ivoire", "Côte d'Ivoire"),
    ('Zambia', 'Zambia'),
    ('Zimbabwe', 'Zimbabwe'),
    ('Mauritius', 'Mauritius'),
    ('Botswana', 'Botswana'),
    ('Namibia', 'Namibia'),
    # Key International Healthcare Corridors
    ('United Kingdom', 'United Kingdom'),
    ('United States', 'United States'),
    ('Canada', 'Canada'),
    ('United Arab Emirates', 'United Arab Emirates'),
    ('Saudi Arabia', 'Saudi Arabia'),
    ('Germany', 'Germany'),
    ('Australia', 'Australia'),
    ('India', 'India'),
    ('Other', 'Other International Location'),
]

COUNTRY_CALLING_CODES = {
    'NG': '234',
    'GH': '233',
    'KE': '254',
    'RW': '250',
    'ZA': '27',
    'EG': '20',
    'ET': '251',
    'UG': '256',
    'TZ': '255',
    'MA': '212',
    'SN': '221',
    'CM': '237',
    'CI': '225',
    'ZM': '260',
    'ZW': '263',
    'MU': '230',
    'BW': '267',
    'NA': '264',
    'GB': '44',
    'US': '1',
    'CA': '1',
    'AE': '971',
    'SA': '966',
    'DE': '49',
    'AU': '61',
    'IN': '91',
}

COUNTRY_CODE_MAP = {
    'GH': 'Ghana',
    'NG': 'Nigeria',
    'KE': 'Kenya',
    'RW': 'Rwanda',
    'ZA': 'South Africa',
    'EG': 'Egypt',
    'ET': 'Ethiopia',
    'UG': 'Uganda',
    'TZ': 'Tanzania',
    'MA': 'Morocco',
    'SN': 'Senegal',
    'CM': 'Cameroon',
    'CI': "Côte d'Ivoire",
    'GB': 'United Kingdom',
    'US': 'United States',
    'CA': 'Canada',
    'AE': 'United Arab Emirates',
    'SA': 'Saudi Arabia',
    'DE': 'Germany',
    'AU': 'Australia',
    'IN': 'India',
}

def get_client_ip(request):
    """
    Extract the true client IP address, checking proxy and Cloudflare headers.
    """
    if not request:
        return '127.0.0.1'
    
    # Cloudflare connecting IP
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf_ip:
        return cf_ip.strip()

    # X-Forwarded-For header (first address is client)
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        parts = x_forwarded.split(',')
        return parts[0].strip()

    # X-Real-IP
    x_real = request.META.get('HTTP_X_REAL_IP')
    if x_real:
        return x_real.strip()

    return request.META.get('REMOTE_ADDR', '127.0.0.1').strip()


def parse_device_info(user_agent_string):
    """
    Parse HTTP User-Agent string into device type, OS, and browser.
    """
    ua = (user_agent_string or '').strip()
    if not ua:
        return {
            'device_type': 'Desktop',
            'device_os': 'Unknown OS',
            'browser': 'Unknown Browser',
            'summary': 'Desktop Client',
        }

    # Detect Device Type
    device_type = 'Desktop'
    if re.search(r'mobile|android.*mobile|iphone|ipod|blackberry|opera mini|iemobile', ua, re.IGNORECASE):
        device_type = 'Mobile'
    elif re.search(r'ipad|tablet|android(?!.*mobile)|kindle|playbook', ua, re.IGNORECASE):
        device_type = 'Tablet'
    elif re.search(r'bot|crawl|spider|slurp|facebookexternalhit', ua, re.IGNORECASE):
        device_type = 'Bot / Crawler'

    # Detect OS
    device_os = 'Unknown OS'
    if 'Windows NT 10.0' in ua:
        device_os = 'Windows 11 / 10'
    elif 'Windows NT 6.3' in ua:
        device_os = 'Windows 8.1'
    elif 'Windows NT 6.1' in ua:
        device_os = 'Windows 7'
    elif 'Windows' in ua:
        device_os = 'Windows'
    elif 'iPhone' in ua:
        device_os = 'iOS (iPhone)'
    elif 'iPad' in ua:
        device_os = 'iOS (iPad)'
    elif 'Mac OS X' in ua or 'Macintosh' in ua:
        device_os = 'macOS'
    elif 'Android' in ua:
        device_os = 'Android'
    elif 'Linux' in ua:
        device_os = 'Linux'
    elif 'CrOS' in ua:
        device_os = 'Chrome OS'

    # Detect Browser
    browser = 'Unknown Browser'
    if 'Edg/' in ua or 'Edge/' in ua:
        browser = 'Microsoft Edge'
    elif 'OPR/' in ua or 'Opera' in ua:
        browser = 'Opera'
    elif 'Chrome/' in ua:
        browser = 'Google Chrome'
    elif 'Firefox/' in ua:
        browser = 'Mozilla Firefox'
    elif 'Safari/' in ua and 'Chrome/' not in ua:
        browser = 'Apple Safari'

    summary = f"{browser} on {device_os} ({device_type})"
    return {
        'device_type': device_type,
        'device_os': device_os,
        'browser': browser,
        'summary': summary,
    }


def resolve_ip_country(ip_address, request=None):
    """
    Resolve country and city from IP address.
    Checks Cloudflare headers, cached lookups, and private IP fallbacks.
    """
    # 1. Cloudflare header if present
    if request:
        cf_country = request.META.get('HTTP_CF_IPCOUNTRY')
        if cf_country and cf_country != 'XX':
            cc = cf_country.upper()
            country_name = COUNTRY_CODE_MAP.get(cc, cc)
            default_city = 'Lagos' if cc == 'NG' else ('Accra' if cc == 'GH' else '')
            return {
                'country': country_name,
                'country_code': cc,
                'city': request.META.get('HTTP_CF_IPCITY', default_city),
                'calling_code': COUNTRY_CALLING_CODES.get(cc, '234' if cc == 'NG' else '233'),
            }

    # 2. Check Cache
    cache_key = f"geoip_{ip_address}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    # 3. Resolve via accurate public IP API (ipwho.is with fallback)
    target_url = "https://ipwho.is/" if is_private_ip(ip_address) else f"https://ipwho.is/{ip_address}"
    geo_result = {
        'country': 'Nigeria',
        'country_code': 'NG',
        'city': 'Lagos',
        'calling_code': '234',
    }
    try:
        req = urllib.request.Request(target_url, headers={'User-Agent': 'Kodafriq-GeoResolver/1.0'})
        with urllib.request.urlopen(req, timeout=2.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if data.get('success', False) or data.get('country'):
                    geo_result = {
                        'country': data.get('country', 'Nigeria'),
                        'country_code': data.get('country_code', 'NG'),
                        'city': data.get('city', 'Lagos'),
                        'calling_code': data.get('calling_code', '234'),
                    }
    except Exception:
        # Secondary fallback
        try:
            req_alt = urllib.request.Request("https://api.country.is/", headers={'User-Agent': 'Kodafriq-GeoResolver/1.0'})
            with urllib.request.urlopen(req_alt, timeout=1.5) as resp_alt:
                if resp_alt.status == 200:
                    d_alt = json.loads(resp_alt.read().decode('utf-8'))
                    cc = d_alt.get('country', 'NG')
                    geo_result = {
                        'country': COUNTRY_CODE_MAP.get(cc, 'Nigeria'),
                        'country_code': cc,
                        'city': 'Lagos',
                        'calling_code': '234' if cc == 'NG' else '233',
                    }
        except Exception:
            pass

    # Cache result for 24 hours
    cache.set(cache_key, geo_result, 86400)
    return geo_result


def is_private_ip(ip):
    """Check if an IP address is loopback or private."""
    if not ip or ip in ('127.0.0.1', '::1', 'localhost'):
        return True
    return (
        ip.startswith('10.') or
        ip.startswith('192.168.') or
        ip.startswith('172.16.') or
        ip.startswith('172.17.') or
        ip.startswith('172.18.') or
        ip.startswith('172.19.') or
        ip.startswith('172.2') or
        ip.startswith('172.30.') or
        ip.startswith('172.31.') or
        ip.startswith('169.254.')
    )
