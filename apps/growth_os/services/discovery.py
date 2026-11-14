"""
apps/growth_os/services/discovery.py
Multi-Source Lead Sourcing & Discovery Engine for Kodafriq GrowthOS.
Integrates search engines (Google Custom Search, SerpAPI), curated directories,
and CSV bulk ingestion pipelines.
"""
import io
import csv
import re
import logging
import requests
from django.conf import settings
from django.utils import timezone
from apps.growth_os.models import (
    EmployerLead, LeadContact, CRMOpportunity, CRMActivity,
    normalize_company_domain
)
from apps.growth_os.services.intent import calculate_lead_intent_score
from apps.growth_os.services.matcher import compute_lead_reverse_matches

logger = logging.getLogger(__name__)

# Comprehensive curated catalogue of high-value US Healthcare RCM, Medical Billing, and Coding targets
CURATED_HEALTHCARE_EMPLOYERS = [
    {
        'company_name': 'Omega Healthcare Management Services',
        'domain': 'omegahms.com',
        'website': 'https://www.omegahms.com',
        'careers_url': 'https://www.omegahms.com/careers',
        'city': 'Boca Raton, FL',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Premier healthcare management solutions, outsourced medical billing, clinical coding, and accounts receivable follow-up.'
    },
    {
        'company_name': 'GeBBS Healthcare Solutions',
        'domain': 'gebbs.com',
        'website': 'https://gebbs.com',
        'careers_url': 'https://gebbs.com/careers',
        'city': 'Culver City, CA',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.HEALTHCARE_BPO,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Forward-thinking healthcare BPO providing revenue cycle management, health information management, and inpatient coding audits.'
    },
    {
        'company_name': 'Ensemble Health Partners',
        'domain': 'ensemblehp.com',
        'website': 'https://www.ensemblehp.com',
        'careers_url': 'https://www.ensemblehp.com/careers',
        'city': 'Cincinnati, OH',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Industry-leading healthcare revenue cycle management company providing end-to-end RCM operations and denials reduction.'
    },
    {
        'company_name': 'Coronis Health',
        'domain': 'coronishealth.com',
        'website': 'https://www.coronishealth.com',
        'careers_url': 'https://www.coronishealth.com/careers',
        'city': 'Sykesville, MD',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_BILLING,
        'company_size': EmployerLead.CompanySize.SIZE_201_500,
        'snippet': 'Top medical billing and revenue cycle management company specializing in specialty physician groups and hospital billing.'
    },
    {
        'company_name': 'AQuity Solutions',
        'domain': 'aquitysolutions.com',
        'website': 'https://aquitysolutions.com',
        'careers_url': 'https://aquitysolutions.com/careers',
        'city': 'Cary, NC',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_CODING,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Clinical documentation, medical coding, interim management, and auditing services for hospitals and physician networks.'
    },
    {
        'company_name': 'Conifer Health Solutions',
        'domain': 'coniferhealth.com',
        'website': 'https://coniferhealth.com',
        'careers_url': 'https://coniferhealth.com/careers',
        'city': 'Frisco, TX',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Enterprise revenue cycle management, physician revenue solutions, and clinical coding integration across Texas and nationwide.'
    },
    {
        'company_name': 'Medusind Solutions',
        'domain': 'medusind.com',
        'website': 'https://www.medusind.com',
        'careers_url': 'https://www.medusind.com/careers',
        'city': 'Miami, FL',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_BILLING,
        'company_size': EmployerLead.CompanySize.SIZE_201_500,
        'snippet': 'Medical billing, dental billing, and RCM technology services for healthcare providers and multi-specialty clinics.'
    },
    {
        'company_name': 'Harris Data Integrity Solutions',
        'domain': 'harrisdataintegrity.com',
        'website': 'https://harrisdataintegrity.com',
        'careers_url': 'https://harrisdataintegrity.com/careers',
        'city': 'Lakeland, FL',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_CODING,
        'company_size': EmployerLead.CompanySize.SIZE_51_200,
        'snippet': 'Health Information Management (HIM) consulting, master patient index (MPI) cleanup, and medical coding auditing services.'
    },
    {
        'company_name': 'R1 RCM Inc.',
        'domain': 'r1rcm.com',
        'website': 'https://www.r1rcm.com',
        'careers_url': 'https://www.r1rcm.com/careers',
        'city': 'Murray, UT',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Technology-enabled revenue cycle management services serving hospitals, health systems, and physician groups.'
    },
    {
        'company_name': 'MedHealth Billing & Consulting',
        'domain': 'medhealthbilling.com',
        'website': 'https://medhealthbilling.com',
        'careers_url': 'https://medhealthbilling.com/jobs',
        'city': 'Dallas, TX',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_BILLING,
        'company_size': EmployerLead.CompanySize.SIZE_11_50,
        'snippet': 'Independent clinical practice billing, credentialing, coding compliance, and claim denial appeal services.'
    },
    {
        'company_name': 'Apex Revenue Cycle Management',
        'domain': 'apexrcm.com',
        'website': 'https://apexrcm.com',
        'careers_url': 'https://apexrcm.com/careers',
        'city': 'Atlanta, GA',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
        'company_size': EmployerLead.CompanySize.SIZE_51_200,
        'snippet': 'Specialty clinic revenue cycle management, AR resolution, fee schedule analysis, and coding audit support.'
    },
    {
        'company_name': 'Pacific Coast Medical Billing',
        'domain': 'pacificbilling.com',
        'website': 'https://pacificbilling.com',
        'careers_url': 'https://pacificbilling.com/careers',
        'city': 'San Diego, CA',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_BILLING,
        'company_size': EmployerLead.CompanySize.SIZE_11_50,
        'snippet': 'California healthcare provider billing solutions, worker comp billing, and outpatient ICD-10 coding support.'
    },
    # Information Technology, Software & Cloud Consultancies
    {
        'company_name': 'EPAM Systems',
        'domain': 'epam.com',
        'website': 'https://www.epam.com',
        'careers_url': 'https://www.epam.com/careers',
        'city': 'Newtown, PA',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.IT_SOFTWARE_DEV,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global digital platform engineering, enterprise software development, cloud computing, and DevOps transformation consulting.'
    },
    {
        'company_name': 'Slalom Consulting',
        'domain': 'slalom.com',
        'website': 'https://www.slalom.com',
        'careers_url': 'https://www.slalom.com/careers',
        'city': 'Seattle, WA',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.IT_CLOUD_DEVOPS,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Modern cloud infrastructure, AWS & Azure migration, Kubernetes containerization, and data architecture solutions.'
    },
    {
        'company_name': 'CrowdStrike Holdings',
        'domain': 'crowdstrike.com',
        'website': 'https://www.crowdstrike.com',
        'careers_url': 'https://www.crowdstrike.com/careers',
        'city': 'Austin, TX',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.IT_CYBERSECURITY,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global cybersecurity leader providing cloud-native endpoint security, threat intelligence, and next-gen SOC operations.'
    },
    {
        'company_name': 'BDO USA Advisory & Accounting',
        'domain': 'bdo.com',
        'website': 'https://www.bdo.com',
        'careers_url': 'https://www.bdo.com/careers',
        'city': 'Chicago, IL',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.FINANCE_ACCOUNTING,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Financial assurance, tax advisory, outsourced accounting, GAAP auditing, and corporate bookkeeping services.'
    }
]


def search_healthcare_employers(query: str, limit: int = 10, country: str = 'United States') -> list:
    """
    Executes an employer discovery search across active APIs or curated database.
    Returns a normalized list of target company records.
    """
    google_key = getattr(settings, 'GOOGLE_CUSTOM_SEARCH_API_KEY', None)
    google_cx = getattr(settings, 'GOOGLE_CUSTOM_SEARCH_CX', None)
    serpapi_key = getattr(settings, 'SERPAPI_API_KEY', None)

    # 1. Check Google Custom Search API
    if google_key and google_cx:
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': google_key,
                'cx': google_cx,
                'q': f"{query} healthcare {country}",
                'num': min(10, limit)
            }
            res = requests.get(url, params=params, timeout=6)
            if res.status_code == 200:
                data = res.json()
                items = []
                for item in data.get('items', []):
                    link = item.get('link', '')
                    domain = normalize_company_domain(link)
                    if domain and not any(ign in domain for ign in ['linkedin.com', 'indeed.com', 'glassdoor.com', 'facebook.com', 'wikipedia.org']):
                        items.append({
                            'company_name': item.get('title', '').split(' - ')[0].split(' | ')[0].strip(),
                            'domain': domain,
                            'website': link,
                            'careers_url': '',
                            'city': 'United States',
                            'country': country,
                            'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
                            'company_size': EmployerLead.CompanySize.SIZE_51_200,
                            'snippet': item.get('snippet', '')
                        })
                if items:
                    return items[:limit]
        except Exception as e:
            logger.warning(f"Google Search API query failed: {e}")

    # 2. Check SerpAPI
    if serpapi_key:
        try:
            url = "https://serpapi.com/search"
            params = {
                'api_key': serpapi_key,
                'engine': 'google',
                'q': f"{query} healthcare company {country}",
                'num': limit
            }
            res = requests.get(url, params=params, timeout=6)
            if res.status_code == 200:
                data = res.json()
                items = []
                for r in data.get('organic_results', []):
                    link = r.get('link', '')
                    domain = normalize_company_domain(link)
                    if domain and not any(ign in domain for ign in ['linkedin.com', 'indeed.com', 'glassdoor.com', 'facebook.com', 'wikipedia.org']):
                        items.append({
                            'company_name': r.get('title', '').split(' - ')[0].split(' | ')[0].strip(),
                            'domain': domain,
                            'website': link,
                            'careers_url': '',
                            'city': 'United States',
                            'country': country,
                            'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
                            'company_size': EmployerLead.CompanySize.SIZE_51_200,
                            'snippet': r.get('snippet', '')
                        })
                if items:
                    return items[:limit]
        except Exception as e:
            logger.warning(f"SerpAPI query failed: {e}")

    # 3. Fallback: Query matching across Curated Index
    q_words = [w.lower() for w in re.split(r'[\s,]+', query) if len(w) > 2]
    matched = []

    for comp in CURATED_HEALTHCARE_EMPLOYERS:
        comp_text = f"{comp['company_name']} {comp['city']} {comp['country']} {comp['snippet']} {comp['domain']}".lower()
        if not q_words or any(w in comp_text for w in q_words):
            matched.append(comp.copy())

    if not matched:
        # Fallback to general list if no strict match
        matched = [c.copy() for c in CURATED_HEALTHCARE_EMPLOYERS]

    return matched[:limit]


def import_discovered_lead(data: dict, assigned_staff=None) -> tuple:
    """
    Ingests a discovered company dict into GrowthOS.
    Deduplicates by normalized domain, computes initial scores, and initializes CRM tracking.
    Returns (lead, created: bool).
    """
    domain = normalize_company_domain(data.get('domain') or data.get('website', ''))
    if not domain:
        raise ValueError("Invalid company domain for ingestion.")

    company_name = data.get('company_name', '').strip() or domain.split('.')[0].capitalize()
    website = data.get('website') or f"https://{domain}"

    lead, created = EmployerLead.objects.get_or_create(
        domain=domain,
        defaults={
            'company_name': company_name,
            'website': website,
            'careers_url': data.get('careers_url', ''),
            'city': data.get('city', ''),
            'country': data.get('country', 'United States'),
            'industry_vertical': data.get('industry_vertical', EmployerLead.IndustryVertical.RCM_SERVICES),
            'company_size': data.get('company_size', EmployerLead.CompanySize.SIZE_51_200),
            'source': EmployerLead.Source.GOOGLE_SEARCH,
            'status': EmployerLead.Status.LEAD,
            'assigned_staff': assigned_staff,
            'notes': data.get('snippet', '')
        }
    )

    if not created:
        # Update missing fields
        updated_fields = []
        if not lead.careers_url and data.get('careers_url'):
            lead.careers_url = data['careers_url']
            updated_fields.append('careers_url')
        if not lead.city and data.get('city'):
            lead.city = data['city']
            updated_fields.append('city')
        if updated_fields:
            lead.save(update_fields=updated_fields)
    else:
        # Auto-create Opportunity
        CRMOpportunity.objects.get_or_create(
            lead=lead,
            defaults={'stage': CRMOpportunity.Stage.STAGE_1_DISCOVERED}
        )

        # Compute initial Intent Score and Reverse Talent Matches
        calculate_lead_intent_score(lead)
        compute_lead_reverse_matches(lead)

        # Audit activity
        staff_str = assigned_staff.get_full_name() or assigned_staff.email if assigned_staff else "Discovery Engine"
        CRMActivity.objects.create(
            lead=lead,
            activity_type=CRMActivity.ActivityType.NOTE,
            summary=f"Discovered and imported into GrowthOS by {staff_str}",
            performed_by=assigned_staff
        )

    return (lead, created)


def import_leads_from_csv(csv_content_or_file, assigned_staff=None) -> dict:
    """
    Parses and ingests employer leads in bulk from a CSV file or string content.
    Handles column variations, deduplication, contact creation, and score calculation.
    """
    if isinstance(csv_content_or_file, bytes):
        content = csv_content_or_file.decode('utf-8', errors='ignore')
    elif hasattr(csv_content_or_file, 'read'):
        raw = csv_content_or_file.read()
        content = raw.decode('utf-8', errors='ignore') if isinstance(raw, bytes) else raw
    else:
        content = str(csv_content_or_file)

    reader = csv.DictReader(io.StringIO(content))
    total = 0
    created = 0
    updated = 0
    skipped = 0
    errors = []

    for row_idx, row in enumerate(reader, start=2):
        total += 1
        # Normalize column keys
        clean_row = {re.sub(r'[^a-z0-9]', '', k.lower()): v.strip() for k, v in row.items() if k}

        # Resolve company name
        company_name = (
            clean_row.get('companyname') or
            clean_row.get('company') or
            clean_row.get('name') or
            clean_row.get('organization') or ''
        )

        if not company_name:
            skipped += 1
            errors.append(f"Row {row_idx}: Skipped due to missing company name.")
            continue

        # Resolve website / domain
        website = (
            clean_row.get('website') or
            clean_row.get('domain') or
            clean_row.get('url') or
            clean_row.get('web') or ''
        )

        domain = normalize_company_domain(website or company_name)
        if not domain or not ('.' in domain):
            skipped += 1
            errors.append(f"Row {row_idx}: Skipped due to missing or invalid company domain.")
            continue

        # Resolve vertical
        raw_vertical = clean_row.get('industryvertical') or clean_row.get('vertical') or clean_row.get('industry') or clean_row.get('sector') or ''
        vertical = EmployerLead.IndustryVertical.RCM_SERVICES
        v_upper = raw_vertical.upper()
        if 'BILL' in v_upper:
            vertical = EmployerLead.IndustryVertical.MEDICAL_BILLING
        elif 'CODE' in v_upper or 'CODING' in v_upper:
            vertical = EmployerLead.IndustryVertical.MEDICAL_CODING
        elif 'CYBER' in v_upper or 'SECURITY' in v_upper:
            vertical = EmployerLead.IndustryVertical.IT_CYBERSECURITY
        elif 'CLOUD' in v_upper or 'DEVOPS' in v_upper or 'SRE' in v_upper:
            vertical = EmployerLead.IndustryVertical.IT_CLOUD_DEVOPS
        elif 'DATA' in v_upper or 'AI' in v_upper or 'ANALYTIC' in v_upper:
            vertical = EmployerLead.IndustryVertical.IT_DATA_AI
        elif 'IT' in v_upper or 'SOFTWARE' in v_upper or 'DEV' in v_upper or 'TECH' in v_upper or 'ENGINEER' in v_upper:
            vertical = EmployerLead.IndustryVertical.IT_SOFTWARE_DEV
        elif 'HELPDESK' in v_upper or 'DESKTOP' in v_upper or 'SYSTEMS' in v_upper:
            vertical = EmployerLead.IndustryVertical.IT_HELPDESK_SUPPORT
        elif 'QA' in v_upper or 'TEST' in v_upper:
            vertical = EmployerLead.IndustryVertical.IT_QA_TESTING
        elif 'ACCOUNT' in v_upper or 'BOOKKEEP' in v_upper:
            vertical = EmployerLead.IndustryVertical.FINANCE_ACCOUNTING
        elif 'FINANCE' in v_upper or 'FINTECH' in v_upper or 'BANK' in v_upper:
            vertical = EmployerLead.IndustryVertical.FINANCIAL_SERVICES
        elif 'BPO' in v_upper or 'OUTSOURC' in v_upper or 'CUSTOMER' in v_upper:
            vertical = EmployerLead.IndustryVertical.BUSINESS_BPO
        elif 'HOSPITAL' in v_upper or 'CLINIC' in v_upper:
            vertical = EmployerLead.IndustryVertical.HOSPITAL_CLINIC

        lead_data = {
            'company_name': company_name,
            'domain': domain,
            'website': website if website.startswith('http') else f"https://{domain}",
            'careers_url': clean_row.get('careersurl') or clean_row.get('careers') or clean_row.get('jobs') or '',
            'city': clean_row.get('city') or clean_row.get('location') or '',
            'country': clean_row.get('country') or 'United States',
            'industry_vertical': vertical,
            'company_size': clean_row.get('companysize') or clean_row.get('size') or EmployerLead.CompanySize.SIZE_51_200,
            'snippet': clean_row.get('notes') or clean_row.get('description') or 'Imported via CSV bulk ledger'
        }

        try:
            lead, is_new = import_discovered_lead(lead_data, assigned_staff=assigned_staff)
            if is_new:
                created += 1
            else:
                updated += 1

            # Check if contact columns exist
            contact_name = clean_row.get('contactname') or clean_row.get('contact') or clean_row.get('fullname') or ''
            contact_email = clean_row.get('contactemail') or clean_row.get('email') or ''
            contact_title = clean_row.get('contacttitle') or clean_row.get('title') or clean_row.get('jobtitle') or ''
            contact_phone = clean_row.get('phone') or clean_row.get('telephone') or ''
            contact_linkedin = clean_row.get('linkedin') or clean_row.get('linkedinurl') or ''

            if contact_name or contact_email:
                c_name = contact_name or (contact_email.split('@')[0].replace('.', ' ').title() if contact_email else 'Executive')
                contact, _ = LeadContact.objects.get_or_create(
                    lead=lead,
                    full_name=c_name,
                    defaults={
                        'job_title': contact_title,
                        'email': contact_email,
                        'phone': contact_phone,
                        'linkedin_url': contact_linkedin,
                        'is_primary': not lead.contacts.filter(is_primary=True).exists(),
                        'verification_status': LeadContact.VerificationStatus.VERIFIED_VALID if contact_email else LeadContact.VerificationStatus.UNVERIFIED
                    }
                )
                calculate_lead_intent_score(lead)

        except Exception as e:
            errors.append(f"Row {row_idx} ({company_name}): {str(e)}")
            skipped += 1

    return {
        'total': total,
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'errors': errors
    }
