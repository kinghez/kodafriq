"""
Base Sourcing Connector Class & Shared Normalization Helpers for GrowthOS.
"""
import re
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from apps.growth_os.models import EmployerLead, normalize_company_domain

AGGREGATOR_DOMAINS = (
    'linkedin.com', 'indeed.com', 'glassdoor.com', 'ziprecruiter.com',
    'remotive.com', 'arbeitnow.com', 'jobicy.com', 'himalayas.app', 'remoteok.com',
    'wellfound.com', 'angel.co', 'monster.com', 'careerbuilder.com', 'simplyhired.com',
    'greenhouse.io', 'lever.co', 'workable.com', 'bamboohr.com', 'ashbyhq.com',
    'smartrecruiters.com', 'myworkdayjobs.com', 'icims.com', 'recruitee.com',
    'personio.de', 'personio.com', 'facebook.com', 'twitter.com', 'x.com',
    'instagram.com', 'youtube.com', 'wikipedia.org', 'wikimedia.org',
    'reddit.com', 'quora.com', 'yelp.com', 'dnb.com', 'zoominfo.com', 'crunchbase.com',
)

COUNTRY_HINTS = [
    (('united kingdom', 'london', 'manchester', 'birmingham', 'uk ', ', uk', 'england', 'scotland', 'leeds', 'bristol'), 'United Kingdom'),
    (('united states', 'usa', 'u.s.', 'new york', 'texas', 'california', 'florida', 'chicago', 'austin', 'dallas', 'atlanta', 'seattle', 'boston', ', tx', ', ca', ', fl', ', ny', ', il', ', nc'), 'United States'),
    (('canada', 'toronto', 'vancouver', 'montreal', 'ottawa', 'calgary'), 'Canada'),
    (('germany', 'berlin', 'munich', 'frankfurt', 'hamburg', 'cologne', 'deutschland'), 'Germany'),
    (('netherlands', 'amsterdam', 'rotterdam', 'utrecht', 'eindhoven'), 'Netherlands'),
    (('france', 'paris', 'lyon', 'marseille'), 'France'),
    (('ireland', 'dublin', 'cork'), 'Ireland'),
    (('poland', 'warsaw', 'krakow', 'wroclaw'), 'Poland'),
    (('spain', 'madrid', 'barcelona'), 'Spain'),
    (('switzerland', 'zurich', 'geneva'), 'Switzerland'),
    (('nigeria', 'lagos', 'abuja', 'port harcourt', 'ibadan'), 'Nigeria'),
    (('kenya', 'nairobi', 'mombasa'), 'Kenya'),
    (('ghana', 'accra', 'kumasi'), 'Ghana'),
    (('south africa', 'cape town', 'johannesburg', 'durban', 'pretoria'), 'South Africa'),
    (('egypt', 'cairo', 'alexandria'), 'Egypt'),
    (('united arab emirates', 'dubai', 'abu dhabi', 'uae'), 'United Arab Emirates'),
    (('saudi arabia', 'riyadh', 'jeddah'), 'Saudi Arabia'),
    (('india', 'bengaluru', 'bangalore', 'mumbai', 'hyderabad', 'pune', 'chennai', 'delhi', 'noida'), 'India'),
    (('singapore',), 'Singapore'),
    (('australia', 'sydney', 'melbourne', 'brisbane', 'perth'), 'Australia'),
    (('new zealand', 'wellington', 'auckland'), 'New Zealand'),
    (('philippines', 'manila', 'cebu'), 'Philippines'),
    (('europe', 'emea', 'european'), 'Europe / EMEA'),
    (('latam', 'latin america', 'brazil', 'mexico', 'colombia', 'argentina'), 'Latin America'),
    (('apac', 'asia-pacific', 'asia'), 'Asia-Pacific'),
    (('africa',), 'Africa'),
]


def is_worldwide_location(location: str) -> bool:
    clean = (location or '').strip().lower()
    return clean in ('', 'all', 'worldwide', 'global', 'anywhere', 'remote worldwide', 'all markets', 'any')


def infer_country_from_location(location_text: str, fallback: str = 'Worldwide') -> str:
    text = f" {(location_text or '').strip().lower()} "
    if not text.strip():
        return fallback or 'Worldwide'
    for keywords, country_name in COUNTRY_HINTS:
        if any(kw in text for kw in keywords):
            # Prefer specific country match over broad continental/worldwide labels (e.g. "Nigeria, Africa, Worldwide" -> "Nigeria")
            if country_name in ('Europe / EMEA', 'Africa', 'Asia-Pacific', 'Latin America'):
                continent_match = country_name
                break
            return country_name
    else:
        continent_match = ''

    if any(tok in text for tok in ('worldwide', 'anywhere', 'global', 'anywhere in the world')):
        return 'Worldwide'
    if continent_match:
        return continent_match
    return fallback if (fallback and not is_worldwide_location(fallback)) else 'Worldwide'


def classify_industry_vertical(text: str, default: str = EmployerLead.IndustryVertical.RCM_SERVICES) -> str:
    lower = (text or '').lower()
    if any(w in lower for w in ['coder', 'coding', 'icd-10', 'cpt', 'rhia', 'ccs', 'cpc', 'ahima', 'aapc', 'drg', 'hcc']):
        return EmployerLead.IndustryVertical.MEDICAL_CODING
    if any(w in lower for w in ['medical billing', 'biller', 'denial', 'ar follow', 'claim scrubbing', 'prior auth', 'credentialing']):
        return EmployerLead.IndustryVertical.MEDICAL_BILLING
    if any(w in lower for w in ['healthcare bpo', 'health bpo', 'clinical staffing', 'medical transcription', 'telehealth']):
        return EmployerLead.IndustryVertical.HEALTHCARE_BPO
    if any(w in lower for w in ['revenue cycle', 'rcm', 'healthcare', 'hospital', 'clinic', 'medical', 'health tech', 'healthtech', 'pharma']):
        return EmployerLead.IndustryVertical.RCM_SERVICES
    if any(w in lower for w in ['cyber', 'infosec', 'soc analyst', 'penetration', 'devsecops', 'zero trust', 'security engineer']):
        return EmployerLead.IndustryVertical.IT_CYBERSECURITY
    if any(w in lower for w in ['devops', 'sre', 'site reliability', 'cloud', 'aws', 'azure', 'gcp', 'kubernetes', 'terraform', 'platform engineer']):
        return EmployerLead.IndustryVertical.IT_CLOUD_DEVOPS
    if any(w in lower for w in ['data engineer', 'data scientist', 'machine learning', 'artificial intelligence', 'analytics', 'snowflake', 'power bi', 'tableau']):
        return EmployerLead.IndustryVertical.IT_DATA_AI
    if any(w in lower for w in ['qa ', 'quality assurance', 'software test', 'automation test', 'sdet']):
        return EmployerLead.IndustryVertical.IT_QA_TESTING
    if any(w in lower for w in ['it support', 'helpdesk', 'sysadmin', 'systems admin', 'technical support']):
        return EmployerLead.IndustryVertical.IT_HELPDESK_SUPPORT
    if any(w in lower for w in ['software', 'developer', 'engineer', 'frontend', 'backend', 'fullstack', 'python', 'react', 'node', 'java', 'django', 'flutter', 'saas', 'fintech']):
        return EmployerLead.IndustryVertical.IT_SOFTWARE_DEV
    if any(w in lower for w in ['accountant', 'accounting', 'bookkeep', 'finance', 'financial', 'cpa', 'acca', 'payroll', 'audit', 'controller', 'ifrs', 'gaap']):
        return EmployerLead.IndustryVertical.FINANCE_ACCOUNTING
    if any(w in lower for w in ['customer support', 'customer success', 'bpo', 'support specialist', 'client operations']):
        return EmployerLead.IndustryVertical.BUSINESS_BPO
    return default


def extract_company_website_from_html(html_text: str, company_name: str = '') -> tuple[str, str]:
    """
    Finds a real company website URL and domain inside a job description or HTML snippet,
    ignoring job board / social / ATS domains. Returns (website, domain) or ('', '').
    """
    if not html_text:
        return '', ''
    urls = re.findall(r'https?://[A-Za-z0-9.\-_/?=&#+%]+', html_text)
    slug = re.sub(r'[^a-z0-9]', '', (company_name or '').lower())
    candidates = []
    for raw_url in urls:
        clean_url = raw_url.rstrip('.,;:"\')>')
        dom = normalize_company_domain(clean_url)
        if not dom or '.' not in dom:
            continue
        if any(agg in dom for agg in AGGREGATOR_DOMAINS):
            continue
        if any(ext in clean_url.lower() for ext in ('.png', '.jpg', '.jpeg', '.svg', '.gif', '.pdf', '.css', '.js')):
            continue
        parsed = urlparse(clean_url)
        root_site = f"{parsed.scheme or 'https'}://{parsed.netloc}"
        score = 2 if (slug and slug[:5] in dom.replace('.', '')) else 1
        candidates.append((score, root_site, dom))
    if not candidates:
        return '', ''
    candidates.sort(key=lambda x: -x[0])
    _, site, dom = candidates[0]
    return site, dom


def location_matches(candidate_loc: str, requested_location: str) -> bool:
    if is_worldwide_location(requested_location):
        return True
    req = requested_location.strip().lower()
    cand = (candidate_loc or '').strip().lower()
    if not cand or any(w in cand for w in ('worldwide', 'anywhere', 'global', 'remote')):
        return True
    if req in cand:
        return True
    inferred = infer_country_from_location(cand, fallback='').lower()
    return bool(inferred and (req in inferred or inferred in req))


class BaseSourcingConnector(ABC):
    """
    Standard interface for all prospective employer sourcing connectors.
    """
    source_identifier = 'BASE'
    source_label = 'Base Sourcing Connector'

    @abstractmethod
    def search(self, query: str, location: str = "Worldwide", limit: int = 15) -> list[dict]:
        """
        Executes a search query against the channel and returns a list of normalized lead dicts.
        """
        pass

    def normalize_lead(self, raw: dict) -> dict:
        """Ensures every result adheres to the standard GrowthOS lead schema."""
        website = (raw.get('website') or '').strip()
        domain = (raw.get('domain') or '').strip()
        if not domain and website:
            domain = normalize_company_domain(website)

        return {
            'company_name': (raw.get('company_name') or '').strip(),
            'domain': domain,
            'website': website,
            'careers_url': (raw.get('careers_url') or '').strip(),
            'city': (raw.get('city') or '').strip(),
            'country': (raw.get('country') or 'Worldwide').strip(),
            'industry_vertical': raw.get('industry_vertical', EmployerLead.IndustryVertical.RCM_SERVICES),
            'company_size': raw.get('company_size', EmployerLead.CompanySize.SIZE_51_200),
            'snippet': (raw.get('snippet') or '').strip(),
            'source': raw.get('source') or self.source_identifier,
            'job_title': (raw.get('job_title') or '').strip(),
            'job_url': (raw.get('job_url') or '').strip(),
            'phone': (raw.get('phone') or '').strip(),
            'contact_email': (raw.get('contact_email') or '').strip(),
            'social_links': raw.get('social_links') or {},
        }
