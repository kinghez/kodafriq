"""
apps/growth_os/services/scraper.py
Ethical, rate-limited career page and vacancy inspector for Kodafriq GrowthOS.
Discovers healthcare job openings, extracts required coding/billing skills,
and updates hiring signals.
"""
import re
import logging
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from apps.growth_os.models import EmployerLead, HiringSignal, CRMActivity
from apps.growth_os.services.intent import calculate_lead_intent_score
from apps.growth_os.services.matcher import compute_lead_reverse_matches

logger = logging.getLogger(__name__)

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
    return list(dict.fromkeys(found))


def inspect_lead_career_page(lead: EmployerLead, target_url: str = None) -> dict:
    """
    Fetches and inspects an employer's career page or website to detect active
    medical coding, billing, and RCM vacancies.
    """
    url = target_url or lead.careers_url or lead.website
    if not url:
        return {'success': False, 'error': 'No website or careers URL specified for this employer.'}

    if not url.startswith('http://') and not url.startswith('https://'):
        url = f"https://{url}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 (Kodafriq-GrowthOS/1.0)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    html_content = ''
    try:
        response = requests.get(url, headers=headers, timeout=8, verify=False)
        if response.status_code == 200:
            html_content = response.text
        else:
            # If careers_url failed or returned 404, try homepage/careers fallback
            if not target_url and lead.website and url != lead.website:
                fallback_url = lead.website.rstrip('/') + '/careers'
                fb_res = requests.get(fallback_url, headers=headers, timeout=6, verify=False)
                if fb_res.status_code == 200:
                    html_content = fb_res.text
                    url = fallback_url
    except Exception as e:
        logger.warning(f"Error scraping {url}: {e}")
        return {'success': False, 'error': f"Failed to connect to {url}: {str(e)}"}

    if not html_content:
        return {'success': False, 'error': f"Could not retrieve webpage content from {url}."}

    soup = BeautifulSoup(html_content, 'html.parser')

    # Remove script, style, nav, footer tags
    for tag in soup(['script', 'style', 'nav', 'footer', 'noscript']):
        tag.decompose()

    detected_roles = []
    page_text = soup.get_text(separator=' ', strip=True)
    extracted_page_skills = extract_skills_from_text(page_text)

    # Strategy 1: Inspect headers and links that often contain job titles
    candidate_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'a', 'p', 'li'])

    seen_titles = set()
    for el in candidate_elements:
        text = el.get_text(strip=True)
        if not text or len(text) > 90 or len(text) < 5:
            continue

        for role_category, regex in ROLE_PATTERNS:
            match = regex.search(text)
            if match:
                title = text.strip()
                # Clean title punctuation
                title = re.sub(r'[\r\n\t]+', ' ', title)
                title = title[:150]
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
        # Check if vacancy already exists
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
            # If existed, increment days_open if active
            vac.days_open += 1
            if vac.days_open >= 30:
                vac.is_persistent = True
            vac.is_active = True
            vac.save(update_fields=['days_open', 'is_persistent', 'is_active'])

    # Recalculate Intent Score & Reverse Matches
    new_intent = calculate_lead_intent_score(lead)
    new_fit = compute_lead_reverse_matches(lead)

    # Log CRM Activity
    if detected_roles:
        CRMActivity.objects.create(
            lead=lead,
            activity_type=CRMActivity.ActivityType.NOTE,
            summary=f"Automated scan completed: {len(detected_roles)} active vacancy signal(s) detected",
            details=f"Scanned URL: {url}. New vacancies added: {created_count}. Hiring Intent: {new_intent}/100, Talent Fit: {new_fit}/100."
        )

    return {
        'success': True,
        'url_scanned': url,
        'vacancies_detected': len(detected_roles),
        'new_vacancies_added': created_count,
        'roles': [r['title'] for r in detected_roles],
        'intent_score': new_intent,
        'fit_score': new_fit,
        'priority_tier': lead.priority_tier
    }

