"""
apps/growth_os/services/scraper.py
Ethical, rate-limited career page and vacancy inspector for Kodafriq GrowthOS.
Discovers healthcare job openings, extracts required coding/billing skills,
and updates hiring signals.
"""
import re
import logging
from urllib.parse import urljoin, urlparse, urlunparse
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
from django.utils import timezone
from apps.growth_os.models import EmployerLead, LeadContact, HiringSignal, CRMActivity, normalize_company_domain
from apps.growth_os.services.intent import calculate_lead_intent_score
from apps.growth_os.services.matcher import compute_lead_reverse_matches

logger = logging.getLogger(__name__)

DEFAULT_SCRAPE_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36 (Kodafriq-GrowthOS/2.0)'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

IGNORED_EMAIL_DOMAINS = (
    'example.com', 'example.org', 'domain.com', 'email.com', 'sentry.io',
    'wixpress.com', 'squarespace.com', 'wordpress.org', 'schema.org',
    'w3.org', 'cloudflare.com', 'googleapis.com', 'gravatar.com',
)
IGNORED_EMAIL_EXTS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js', '.ico', '.woff')

CAREER_LINK_KEYWORDS = (
    'career', 'careers', 'jobs', 'hiring', 'openings', 'vacancies',
    'join-us', 'join-our-team', 'work-with-us', 'positions', 'opportunities', 'talent',
)
ATS_HOST_HINTS = (
    'boards.greenhouse.io', 'job-boards.greenhouse.io', 'jobs.lever.co',
    'apply.workable.com', 'bamboohr.com', 'ashbyhq.com', 'smartrecruiters.com',
    'recruitee.com', 'personio.de', 'personio.com', 'myworkdayjobs.com', 'icims.com',
)
CONTACT_LINK_KEYWORDS = ('contact', 'contact-us', 'get-in-touch', 'reach-us', 'about', 'about-us')

EMAIL_REGEX = re.compile(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,12}\b')
PHONE_REGEX = re.compile(
    r'(?:\+\d{1,3}[\s.\-()]*)?(?:\(?\d{2,4}\)?[\s.\-]+)\d{3,4}[\s.\-]\d{3,5}(?:[\s.\-]\d{1,4})?'
)

SOCIAL_PLATFORMS = (
    ('linkedin', re.compile(r'(?:^|\.)linkedin\.com/(?:company|school|in)/[A-Za-z0-9._\-/%]+', re.I), ('/share', '/feed/', '/learning/')),
    ('twitter', re.compile(r'(?:^|\.)(?:twitter\.com|x\.com)/[A-Za-z0-9_]{2,50}', re.I), ('/intent/', '/share', '/search', '/home', '/hashtag')),
    ('facebook', re.compile(r'(?:^|\.)(?:facebook\.com|fb\.com)/[A-Za-z0-9.\-_/]{2,80}', re.I), ('/sharer', '/tr?', '/plugins/', '/dialog/')),
    ('instagram', re.compile(r'(?:^|\.)instagram\.com/[A-Za-z0-9._]{2,50}', re.I), ('/p/', '/reel/', '/explore/', '/accounts/')),
    ('youtube', re.compile(r'(?:^|\.)youtube\.com/(?:@[A-Za-z0-9._\-]+|c/[A-Za-z0-9._\-]+|channel/[A-Za-z0-9._\-]+|user/[A-Za-z0-9._\-]+)', re.I), ('/watch', '/embed/')),
    ('github', re.compile(r'(?:^|\.)github\.com/[A-Za-z0-9._\-]{2,50}', re.I), ('/topics/', '/explore', '/features', '/pricing', '/login')),
)

# Healthcare job title patterns mapped to RoleCategory
ROLE_PATTERNS = [
    # Healthcare Operations
    (
        HiringSignal.RoleCategory.MEDICAL_CODER,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:inpatient|outpatient|clinical|medical|hcc|risk\s+adjustment|emergency|drg)?\s*(?:medical\s+)?(?:coding\s+specialist|coder|coding\s+auditor)\b', re.IGNORECASE)
    ),
    (
        HiringSignal.RoleCategory.MEDICAL_BILLER,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:medical|healthcare|physician|hospital|dental|claims)?\s*(?:biller|billing\s+specialist|billing\s+coordinator|billing\s+analyst)\b', re.IGNORECASE)
    ),
    (
        HiringSignal.RoleCategory.AR_SPECIALIST,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:accounts\s+receivable|a/?r|denial(?:s)?|collections?)\s*(?:specialist|analyst|representative|coordinator)\b', re.IGNORECASE)
    ),
    (
        HiringSignal.RoleCategory.RCM_SPECIALIST,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:revenue\s+cycle|rcm)\s*(?:specialist|analyst|manager|coordinator|operations\s+specialist)\b', re.IGNORECASE)
    ),
    (
        HiringSignal.RoleCategory.AUDITOR,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:clinical\s+documentation|cdi|drg|coding\s+compliance)\s*(?:auditor|specialist|analyst)\b', re.IGNORECASE)
    ),

    # Information Technology, Software & Engineering
    (
        HiringSignal.RoleCategory.SOFTWARE_ENGINEER,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+|principal\s+)?(?:fullstack|frontend|backend|software|web|python|react|node|django|mobile|flutter)?\s*(?:engineer|developer|programmer)\b', re.IGNORECASE)
    ),
    (
        HiringSignal.RoleCategory.DEVOPS_CLOUD,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:devops|cloud|sre|site\s+reliability|infrastructure|aws|azure|platform)\s*(?:engineer|architect|specialist)\b', re.IGNORECASE)
    ),
    (
        HiringSignal.RoleCategory.CYBERSECURITY,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:cybersecurity|information\s+security|infosec|security|soc|penetration\s+tester|incident\s+response)\s*(?:analyst|engineer|specialist|auditor)\b', re.IGNORECASE)
    ),
    (
        HiringSignal.RoleCategory.DATA_AI,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:data|business\s+intelligence|bi|analytics|machine\s+learning|ai)\s*(?:engineer|analyst|scientist)\b', re.IGNORECASE)
    ),
    (
        HiringSignal.RoleCategory.IT_SUPPORT,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:it\s+support|helpdesk|systems?\s+admin(?:istrator)?|desktop\s+support|technical\s+support)\s*(?:specialist|engineer|analyst|technician)?\b', re.IGNORECASE)
    ),
    (
        HiringSignal.RoleCategory.QA_ENGINEER,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:qa|quality\s+assurance|test|software\s+test)\s*(?:engineer|analyst|tester|automation\s+engineer)\b', re.IGNORECASE)
    ),

    # Finance, Accounting & Business Operations
    (
        HiringSignal.RoleCategory.ACCOUNTANT,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:staff\s+)?(?:accountant|bookkeeper|accounting\s+specialist|controller|accounts\s+payable|payroll\s+specialist)\b', re.IGNORECASE)
    ),
    (
        HiringSignal.RoleCategory.FINANCIAL_ANALYST,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:financial|finance|risk|compliance)\s*(?:analyst|specialist|manager|auditor)\b', re.IGNORECASE)
    ),
    (
        HiringSignal.RoleCategory.CUSTOMER_SUPPORT,
        re.compile(r'\b(?:senior\s+|lead\s+|remote\s+)?(?:customer\s+support|customer\s+success|client\s+operations|call\s+center)\s*(?:representative|agent|specialist|lead)\b', re.IGNORECASE)
    ),
]

# Universal cross-sector technical & operational skill keywords
SKILL_KEYWORDS = [
    # Healthcare Operations & Medical Coding
    'ICD-10', 'ICD-10-CM', 'ICD-10-PCS', 'CPT', 'HCPCS', 'DRG', 'HCC',
    'Epic', 'Cerner', 'Meditech', 'Athenahealth', 'eClinicalWorks', 'NextGen',
    'AAPC', 'AHIMA', 'CPC', 'CCS', 'RHIA', 'RHIT',
    'Denial Management', 'Prior Authorization', 'AR Follow-Up', 'Appeals',
    'Charge Capture', 'Claim Scrubbing', 'Clearinghouse', 'EDI 837', 'EDI 835',

    # Information Technology & Software Engineering
    'Python', 'Django', 'FastAPI', 'Flask', 'React', 'Vue', 'Angular', 'Next.js',
    'Node.js', 'TypeScript', 'JavaScript', 'Java', 'Spring Boot', 'Go', 'Golang',
    'Rust', 'C#', '.NET', 'PHP', 'Laravel', 'Flutter', 'React Native', 'REST API',
    'GraphQL', 'Tailwind', 'HTML5', 'CSS3',

    # Cloud, DevOps & Systems
    'AWS', 'Azure', 'Google Cloud', 'GCP', 'Docker', 'Kubernetes', 'Terraform',
    'Ansible', 'CI/CD', 'GitHub Actions', 'GitLab', 'Linux', 'Ubuntu', 'Bash',
    'Microservices', 'Serverless', 'Kafka', 'RabbitMQ',

    # Cybersecurity & Infrastructure
    'Cybersecurity', 'SOC', 'SIEM', 'Penetration Testing', 'Firewall', 'Zero Trust',
    'CompTIA Security+', 'CISSP', 'CEH', 'ISO 27001', 'Active Directory', 'Incident Response',
    'Vulnerability Assessment', 'Data Protection', 'GDPR', 'HIPAA Compliance',

    # Data, Analytics & AI
    'SQL', 'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Snowflake', 'BigQuery',
    'Power BI', 'Tableau', 'Pandas', 'Machine Learning', 'TensorFlow', 'PyTorch',

    # IT Support & Enterprise Operations
    'ServiceNow', 'Jira', 'Confluence', 'Zendesk', 'Office 365', 'ITIL',

    # Finance, Accounting & Business
    'QuickBooks', 'Xero', 'NetSuite', 'SAP', 'GAAP', 'IFRS', 'Financial Modeling',
    'Bookkeeping', 'Accounts Payable', 'Accounts Receivable', 'Payroll', 'CPA', 'ACCA'
]


def extract_skills_from_text(text: str) -> list:
    """Extracts identified technical, operational and domain skill keywords from text."""
    found = []
    text_upper = text.upper()
    for kw in SKILL_KEYWORDS:
        pattern = r'\b' + re.escape(kw.upper()) + r'\b'
        if re.search(pattern, text_upper):
            found.append(kw)
    return list(dict.fromkeys(found))


def _is_valid_email(email: str) -> bool:
    clean = (email or '').strip().lower()
    if not clean or '@' not in clean or len(clean) > 120:
        return False
    if any(clean.endswith(ext) for ext in IGNORED_EMAIL_EXTS):
        return False
    domain_part = clean.split('@', 1)[1]
    if any(bad in domain_part for bad in IGNORED_EMAIL_DOMAINS):
        return False
    return '.' in domain_part


def _normalize_phone(raw: str) -> str:
    candidate = re.sub(r'^tel:\s*', '', (raw or '').strip(), flags=re.I)
    candidate = re.sub(r'\s+', ' ', candidate).strip(' .,;|/')
    digits = re.sub(r'\D', '', candidate)
    if len(digits) < 8 or len(digits) > 15:
        return ''
    # Reject repetitive numbers or year ranges like 2020-2026
    if len(set(digits)) <= 2:
        return ''
    if re.fullmatch(r'(?:19|20)\d{2}[\s.\-](?:19|20)\d{2}', candidate):
        return ''
    return candidate[:60]


def _clean_social_url(href: str) -> str:
    parsed = urlparse(href.strip())
    if not parsed.scheme:
        parsed = urlparse('https://' + href.strip().lstrip('/'))
    clean_path = parsed.path.rstrip('/')
    return urlunparse((parsed.scheme or 'https', parsed.netloc.lower(), clean_path, '', '', ''))


def _rank_email(email: str, company_domain: str = '') -> tuple:
    local, dom = email.lower().split('@', 1)
    score = 0
    if company_domain and (dom == company_domain or dom.endswith('.' + company_domain)):
        score += 50
    for idx, prefix in enumerate(('careers', 'jobs', 'talent', 'recruiting', 'hr', 'hiring', 'info', 'contact', 'hello', 'sales')):
        if local.startswith(prefix):
            score += 30 - idx
            break
    if 'noreply' in local or 'no-reply' in local or 'donotreply' in local:
        score -= 40
    return (-score, len(email), email.lower())


def extract_website_contacts_from_soup(soup, base_url: str, company_domain: str = '') -> dict:
    """
    Extracts phones, emails, social media profiles, career page links, and
    contact page URLs from a full HTML page BEFORE stripping header/nav/footer.
    """
    emails = set()
    phones = []
    seen_phone_digits = set()
    social_links = {}
    career_urls = []
    contact_urls = []

    base_host = urlparse(base_url).netloc.lower().lstrip('www.')
    target_domain = (company_domain or base_host).lower()

    for a_tag in soup.find_all('a', href=True):
        href = (a_tag.get('href') or '').strip()
        if not href or href.startswith('#') or href.lower().startswith('javascript:'):
            continue

        href_lower = href.lower()
        anchor_text = a_tag.get_text(' ', strip=True).lower()

        if href_lower.startswith('mailto:'):
            addr = href.split(':', 1)[1].split('?', 1)[0].strip()
            if _is_valid_email(addr):
                emails.add(addr.lower())
            continue

        if href_lower.startswith('tel:'):
            phone_val = _normalize_phone(href)
            if phone_val:
                digits = re.sub(r'\D', '', phone_val)
                if digits not in seen_phone_digits:
                    seen_phone_digits.add(digits)
                    phones.append(phone_val)
            continue

        abs_url = urljoin(base_url, href)
        parsed = urlparse(abs_url)
        host = parsed.netloc.lower()
        host_and_path = f"{host}{parsed.path}"

        matched_social = False
        for key, pattern, excluded_parts in SOCIAL_PLATFORMS:
            if pattern.search(host_and_path):
                if not any(ex in abs_url.lower() for ex in excluded_parts):
                    if key not in social_links:
                        social_links[key] = _clean_social_url(abs_url)
                matched_social = True
                break
        if matched_social:
            continue

        clean_host = host.lstrip('www.')
        is_same_site = bool(target_domain and (clean_host == target_domain or clean_host.endswith('.' + target_domain)))
        is_ats = any(ats in clean_host for ats in ATS_HOST_HINTS)

        if is_ats or (is_same_site and any(k in parsed.path.lower() or k in anchor_text for k in CAREER_LINK_KEYWORDS)):
            if abs_url not in career_urls and len(abs_url) <= 300:
                career_urls.append(abs_url)
        elif is_same_site and any(k in parsed.path.lower() or k in anchor_text for k in CONTACT_LINK_KEYWORDS):
            if abs_url not in contact_urls and len(abs_url) <= 300:
                contact_urls.append(abs_url)

    # Scan visible full-page text (header, footer, body) for emails & phones
    # Exclude script/style/noscript for text regex scanning
    text_soup = BeautifulSoup(str(soup), 'html.parser')
    for hidden in text_soup(['script', 'style', 'noscript']):
        hidden.decompose()
    full_text = text_soup.get_text(separator=' ', strip=True)

    for raw_email in EMAIL_REGEX.findall(full_text):
        if _is_valid_email(raw_email):
            emails.add(raw_email.lower())

    for raw_phone in PHONE_REGEX.findall(full_text):
        phone_val = _normalize_phone(raw_phone)
        if phone_val:
            digits = re.sub(r'\D', '', phone_val)
            if digits not in seen_phone_digits:
                seen_phone_digits.add(digits)
                phones.append(phone_val)

    ranked_emails = sorted(emails, key=lambda e: _rank_email(e, target_domain))
    return {
        'phones': phones[:5],
        'emails': ranked_emails[:8],
        'social_links': social_links,
        'career_urls': career_urls[:5],
        'contact_urls': contact_urls[:5],
    }


def _fetch_html(url: str, timeout: int = 8) -> tuple[str, str]:
    """Fetches HTML safely and returns (final_url, html_text) or ('', '')."""
    try:
        response = requests.get(
            url,
            headers=DEFAULT_SCRAPE_HEADERS,
            timeout=timeout,
            allow_redirects=True,
            verify=False,
        )
        if getattr(response, 'status_code', 0) == 200 and getattr(response, 'text', ''):
            final_url = getattr(response, 'url', None)
            if not isinstance(final_url, str) or not final_url.startswith('http'):
                final_url = url
            return final_url, response.text
    except Exception as e:
        logger.debug(f"HTTP fetch skipped for {url}: {e}")
    return '', ''


def _save_scraped_contacts_to_lead(lead: EmployerLead, contact_info: dict) -> dict:
    """Persists newly discovered phone, email, social links, careers_url, and LeadContact."""
    phones = contact_info.get('phones') or []
    emails = contact_info.get('emails') or []
    social_links = contact_info.get('social_links') or {}
    career_urls = contact_info.get('career_urls') or []

    best_phone = phones[0] if phones else ''
    best_email = emails[0] if emails else ''
    discovered_careers = career_urls[0] if career_urls else ''

    update_fields = []
    if best_phone and not lead.phone:
        lead.phone = best_phone[:80]
        update_fields.append('phone')
    if best_email and not lead.contact_email:
        lead.contact_email = best_email
        update_fields.append('contact_email')
    if discovered_careers and not lead.careers_url:
        lead.careers_url = discovered_careers[:200]
        update_fields.append('careers_url')

    existing_socials = dict(lead.social_links or {}) if isinstance(lead.social_links, dict) else {}
    social_changed = False
    for platform, url in social_links.items():
        if url and not existing_socials.get(platform):
            existing_socials[platform] = url
            social_changed = True
    if social_changed:
        lead.social_links = existing_socials
        update_fields.append('social_links')

    lead.last_scraped_at = timezone.now()
    update_fields.append('last_scraped_at')
    lead.save(update_fields=update_fields)

    # Create or enrich a contact record when an email or hiring channel is discovered
    if best_email:
        existing_contact = lead.contacts.filter(email__iexact=best_email).first()
        if not existing_contact:
            local_part = best_email.split('@', 1)[0].lower()
            is_hr = any(k in local_part for k in ('career', 'job', 'talent', 'recruit', 'hr', 'hiring'))
            LeadContact.objects.create(
                lead=lead,
                full_name='Talent Acquisition / HR Desk' if is_hr else f"{lead.company_name[:60]} Contact Desk",
                job_title='Hiring & Talent Acquisition' if is_hr else 'General / Business Contact',
                email=best_email,
                phone=best_phone[:50] if best_phone else '',
                linkedin_url=existing_socials.get('linkedin', ''),
                is_primary=not lead.contacts.filter(is_primary=True).exists(),
                verification_status=LeadContact.VerificationStatus.UNVERIFIED,
            )

    return {
        'phone': lead.phone,
        'contact_email': lead.contact_email,
        'social_links': existing_socials,
        'careers_url': lead.careers_url,
    }


def inspect_lead_career_page(lead: EmployerLead, target_url: str = None, enrich_contacts: bool = True) -> dict:
    """
    Fetches and inspects an employer's website and career page to:
    1) Extract company contact details (phone numbers, HR/contact emails, social media profiles).
    2) Auto-discover the careers / jobs URL if missing.
    3) Detect active vacancies & skills across Healthcare, IT, Finance, and BPO.
    """
    if BeautifulSoup is None:
        return {'success': False, 'error': 'beautifulsoup4 is required for career page inspection. Please run pip install -r requirements.txt.'}

    url = target_url or lead.careers_url or lead.website
    if not url:
        return {'success': False, 'error': 'No website or careers URL specified for this employer.'}

    if not url.startswith('http://') and not url.startswith('https://'):
        url = f"https://{url}"

    html_content = ''
    try:
        response = requests.get(url, headers=DEFAULT_SCRAPE_HEADERS, timeout=8, verify=False)
        if response.status_code == 200:
            html_content = response.text
        else:
            # If careers_url failed or returned 404, try homepage/careers fallback
            if not target_url and lead.website and url != lead.website:
                fallback_url = lead.website.rstrip('/') + '/careers'
                _, html_content = _fetch_html(fallback_url, timeout=6)
                if html_content:
                    url = fallback_url
                else:
                    _, html_content = _fetch_html(lead.website, timeout=6)
                    if html_content:
                        url = lead.website
    except Exception as e:
        logger.warning(f"Error scraping {url}: {e}")
        return {'success': False, 'error': f"Failed to connect to {url}: {str(e)}"}

    if not html_content:
        return {'success': False, 'error': f"Could not retrieve webpage content from {url}."}

    full_soup = BeautifulSoup(html_content, 'html.parser')
    contact_bundle = extract_website_contacts_from_soup(full_soup, url, lead.domain or '')

    # If contacts/social profiles or careers links weren't on this page, also crawl homepage & discovered contact subpages
    if enrich_contacts:
        subpages_to_visit = []
        base_root = lead.website if (lead.website and lead.website.startswith('http')) else (f"https://{lead.domain}" if lead.domain else '')
        normalized_current = url.rstrip('/').lower()

        if base_root and base_root.rstrip('/').lower() != normalized_current:
            if not contact_bundle['phones'] or not contact_bundle['emails'] or not contact_bundle['social_links']:
                subpages_to_visit.append(base_root)

        for c_url in contact_bundle['contact_urls']:
            if c_url.rstrip('/').lower() != normalized_current and c_url not in subpages_to_visit:
                subpages_to_visit.append(c_url)

        visited = {normalized_current}
        for sub_url in subpages_to_visit[:2]:
            if sub_url.rstrip('/').lower() in visited:
                continue
            visited.add(sub_url.rstrip('/').lower())
            final_sub_url, sub_html = _fetch_html(sub_url, timeout=6)
            if sub_html:
                sub_soup = BeautifulSoup(sub_html, 'html.parser')
                sub_info = extract_website_contacts_from_soup(sub_soup, final_sub_url or sub_url, lead.domain or '')
                for ph in sub_info['phones']:
                    if ph not in contact_bundle['phones']:
                        contact_bundle['phones'].append(ph)
                for em in sub_info['emails']:
                    if em not in contact_bundle['emails']:
                        contact_bundle['emails'].append(em)
                for plat, slink in sub_info['social_links'].items():
                    contact_bundle['social_links'].setdefault(plat, slink)
                for curl in sub_info['career_urls']:
                    if curl not in contact_bundle['career_urls']:
                        contact_bundle['career_urls'].append(curl)

        # If a career URL was discovered while scanning the homepage, inspect it too for open roles
        if contact_bundle['career_urls'] and url.rstrip('/').lower() == (base_root or '').rstrip('/').lower():
            career_target = contact_bundle['career_urls'][0]
            if career_target.rstrip('/').lower() not in visited:
                _, career_html = _fetch_html(career_target, timeout=6)
                if career_html:
                    html_content = html_content + "\n" + career_html
                    full_soup = BeautifulSoup(html_content, 'html.parser')

    saved_contacts = _save_scraped_contacts_to_lead(lead, contact_bundle)

    # Remove script, style, nav, footer tags AFTER contact/social/career extraction
    for tag in full_soup(['script', 'style', 'nav', 'footer', 'noscript']):
        tag.decompose()

    detected_roles = []
    page_text = full_soup.get_text(separator=' ', strip=True)
    extracted_page_skills = extract_skills_from_text(page_text)

    # Inspect headers and links that often contain job titles
    candidate_elements = full_soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'a', 'p', 'li'])

    seen_titles = set()
    for el in candidate_elements:
        text = el.get_text(strip=True)
        if not text or len(text) > 90 or len(text) < 5:
            continue

        for role_category, regex in ROLE_PATTERNS:
            match = regex.search(text)
            if match:
                title = text.strip()
                title = re.sub(r'[\r\n\t]+', ' ', title)[:150]
                norm_title = title.lower()

                if norm_title not in seen_titles:
                    seen_titles.add(norm_title)
                    job_link = el.get('href') if el.name == 'a' else ''
                    if job_link and not job_link.startswith('http'):
                        base_domain = f"https://{lead.domain}"
                        job_link = base_domain.rstrip('/') + '/' + job_link.lstrip('/')

                    detected_roles.append({
                        'title': title,
                        'category': role_category,
                        'skills': extracted_page_skills[:6],
                        'url': job_link or url
                    })
                break

    # Record or update detected vacancies in database
    created_count = 0
    for role in detected_roles:
        vac, created = HiringSignal.objects.get_or_create(
            lead=lead,
            job_title=role['title'],
            defaults={
                'role_category': role['category'],
                'job_url': role['url'],
                'extracted_skills': role['skills'],
                'days_open': 1,
                'is_active': True,
                'raw_description': f"Discovered via automated web scan of {url} on {timezone.now().strftime('%Y-%m-%d')}."
            }
        )
        if created:
            created_count += 1
        else:
            vac.days_open += 1
            if vac.days_open >= 30:
                vac.is_persistent = True
            vac.is_active = True
            vac.save(update_fields=['days_open', 'is_persistent', 'is_active'])

    # Recalculate Intent Score & Reverse Matches
    new_intent = calculate_lead_intent_score(lead)
    new_fit = compute_lead_reverse_matches(lead)

    # Log CRM Activity
    if detected_roles or saved_contacts['phone'] or saved_contacts['contact_email'] or saved_contacts['social_links']:
        contact_notes = []
        if saved_contacts['phone']:
            contact_notes.append(f"Phone: {saved_contacts['phone']}")
        if saved_contacts['contact_email']:
            contact_notes.append(f"Email: {saved_contacts['contact_email']}")
        if saved_contacts['social_links']:
            contact_notes.append(f"Socials: {', '.join(saved_contacts['social_links'].keys())}")
        contact_summary = " | ".join(contact_notes) if contact_notes else "No new contact metadata"
        CRMActivity.objects.create(
            lead=lead,
            activity_type=CRMActivity.ActivityType.NOTE,
            summary=f"Automated scan completed: {len(detected_roles)} active vacancy signal(s) detected",
            details=(
                f"Scanned URL: {url}. New vacancies added: {created_count}. "
                f"Contacts: {contact_summary}. Hiring Intent: {new_intent}/100, Talent Fit: {new_fit}/100."
            )
        )

    return {
        'success': True,
        'url_scanned': url,
        'vacancies_detected': len(detected_roles),
        'new_vacancies_added': created_count,
        'roles': [r['title'] for r in detected_roles],
        'phone': saved_contacts['phone'],
        'contact_email': saved_contacts['contact_email'],
        'social_links': saved_contacts['social_links'],
        'careers_url': saved_contacts['careers_url'],
        'intent_score': new_intent,
        'fit_score': new_fit,
        'priority_tier': lead.priority_tier
    }

