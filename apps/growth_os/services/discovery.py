"""
apps/growth_os/services/discovery.py
Worldwide Multi-Source Lead Sourcing & Discovery Engine for Kodafriq GrowthOS.
Integrates search engines (Google Custom Search, SerpAPI, DuckDuckGo Live Web Index),
worldwide multi-sector directory coverage, and CSV bulk ingestion pipelines.
"""
import io
import csv
import re
import logging
from urllib.parse import parse_qs, urlparse
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
from django.conf import settings
from django.utils import timezone
from apps.growth_os.models import (
    EmployerLead, LeadContact, HiringSignal, CRMOpportunity, CRMActivity,
    normalize_company_domain
)
from apps.growth_os.services.intent import calculate_lead_intent_score
from apps.growth_os.services.matcher import compute_lead_reverse_matches
from apps.growth_os.services.connectors.base import (
    AGGREGATOR_DOMAINS,
    classify_industry_vertical,
    infer_country_from_location,
    is_worldwide_location,
    location_matches,
)

logger = logging.getLogger(__name__)

SEARCH_NOISE_DOMAINS = AGGREGATOR_DOMAINS + (
    'bloomberg.com', 'forbes.com', 'clutch.co', 'g2.com', 'goodfirms.co',
    'builtin.com', 'indeed.co.uk', 'ambitionbox.com', 'comparably.com',
)

WEB_SEARCH_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Comprehensive Worldwide Multi-Sector Employer Directory (Healthcare RCM/Billing/Coding,
# IT/Software/Cloud/Cybersecurity/Data/QA, Finance & Accounting, BPO & Support)
CURATED_WORLDWIDE_EMPLOYERS = [
    # --- UNITED STATES ---
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
        'company_name': 'Access Healthcare',
        'domain': 'accesshealthcare.com',
        'website': 'https://www.accesshealthcare.com',
        'careers_url': 'https://www.accesshealthcare.com/careers',
        'city': 'Dallas, TX',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global healthcare business process services, medical billing, coding, and denials management across Texas and India.'
    },
    {
        'company_name': 'CareCloud',
        'domain': 'carecloud.com',
        'website': 'https://www.carecloud.com',
        'careers_url': 'https://www.carecloud.com/careers',
        'city': 'Somerset, NJ',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_BILLING,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Healthcare IT, cloud EHR, practice management, and revenue cycle medical billing solutions.'
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
        'company_name': 'EPAM Systems',
        'domain': 'epam.com',
        'website': 'https://www.epam.com',
        'careers_url': 'https://www.epam.com/careers',
        'city': 'Newtown, PA',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.IT_SOFTWARE_DEV,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global digital platform engineering, enterprise software development, cloud computing, and DevOps consulting worldwide.'
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
        'company_name': 'BDO Advisory & Accounting',
        'domain': 'bdo.com',
        'website': 'https://www.bdo.com',
        'careers_url': 'https://www.bdo.com/careers',
        'city': 'Chicago, IL',
        'country': 'United States',
        'industry_vertical': EmployerLead.IndustryVertical.FINANCE_ACCOUNTING,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Financial assurance, tax advisory, outsourced accounting, GAAP auditing, and corporate bookkeeping services.'
    },
    # --- UNITED KINGDOM & EUROPE ---
    {
        'company_name': 'Bupa Global & UK Healthcare',
        'domain': 'bupa.com',
        'website': 'https://www.bupa.com',
        'careers_url': 'https://careers.bupa.co.uk',
        'city': 'London',
        'country': 'United Kingdom',
        'industry_vertical': EmployerLead.IndustryVertical.HEALTHCARE_BPO,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'International healthcare group hiring clinical claims specialists, medical billing auditors, health data analysts, and IT engineers.'
    },
    {
        'company_name': 'Cera Care UK',
        'domain': 'ceracare.co.uk',
        'website': 'https://www.ceracare.co.uk',
        'careers_url': 'https://www.ceracare.co.uk/careers',
        'city': 'London',
        'country': 'United Kingdom',
        'industry_vertical': EmployerLead.IndustryVertical.HEALTHCARE_BPO,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Digital-first healthcare operator in the UK hiring health data engineers, software developers, and clinical coordinators.'
    },
    {
        'company_name': 'Dedalus Healthcare Group',
        'domain': 'dedalus.com',
        'website': 'https://www.dedalus.com',
        'careers_url': 'https://www.dedalus.com/global/en/careers/',
        'city': 'London / Milan',
        'country': 'United Kingdom',
        'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_CODING,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Leading European healthcare software, EHR interoperability, clinical coding, and hospital billing systems provider.'
    },
    {
        'company_name': 'Wise Payments Ltd',
        'domain': 'wise.com',
        'website': 'https://wise.com',
        'careers_url': 'https://wise.jobs',
        'city': 'London',
        'country': 'United Kingdom',
        'industry_vertical': EmployerLead.IndustryVertical.IT_SOFTWARE_DEV,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global cross-border fintech platform hiring software engineers, cloud SREs, financial compliance, and customer support teams.'
    },
    {
        'company_name': 'Snyk',
        'domain': 'snyk.io',
        'website': 'https://snyk.io',
        'careers_url': 'https://snyk.io/careers/',
        'city': 'London',
        'country': 'United Kingdom',
        'industry_vertical': EmployerLead.IndustryVertical.IT_CYBERSECURITY,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Developer cybersecurity & DevSecOps platform hiring application security engineers and cloud researchers worldwide.'
    },
    {
        'company_name': 'CompuGroup Medical SE',
        'domain': 'cgm.com',
        'website': 'https://www.cgm.com',
        'careers_url': 'https://www.cgm.com/corp_en/career.html',
        'city': 'Koblenz / Berlin',
        'country': 'Germany',
        'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Major eHealth and medical practice software provider across Germany, UK, US, and Europe supporting medical billing and HIS.'
    },
    {
        'company_name': 'Celonis SE',
        'domain': 'celonis.com',
        'website': 'https://www.celonis.com',
        'careers_url': 'https://www.celonis.com/careers/',
        'city': 'Munich',
        'country': 'Germany',
        'industry_vertical': EmployerLead.IndustryVertical.IT_DATA_AI,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Enterprise process mining and AI analytics leader hiring data engineers, Python/Java developers, and finance analysts.'
    },
    {
        'company_name': 'Doctolib',
        'domain': 'doctolib.com',
        'website': 'https://www.doctolib.com',
        'careers_url': 'https://careers.doctolib.com',
        'city': 'Paris / Berlin',
        'country': 'France',
        'industry_vertical': EmployerLead.IndustryVertical.IT_SOFTWARE_DEV,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'European healthtech platform serving clinics and hospitals with digital patient scheduling, telehealth, and engineering roles.'
    },
    {
        'company_name': 'Philips Healthcare',
        'domain': 'philips.com',
        'website': 'https://www.philips.com',
        'careers_url': 'https://www.careers.philips.com',
        'city': 'Amsterdam',
        'country': 'Netherlands',
        'industry_vertical': EmployerLead.IndustryVertical.HEALTHCARE_BPO,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global health technology organization hiring clinical informatics, cloud software, cybersecurity, and RCM finance specialists.'
    },
    {
        'company_name': 'Adyen N.V.',
        'domain': 'adyen.com',
        'website': 'https://www.adyen.com',
        'careers_url': 'https://careers.adyen.com',
        'city': 'Amsterdam',
        'country': 'Netherlands',
        'industry_vertical': EmployerLead.IndustryVertical.FINANCE_ACCOUNTING,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global enterprise payments and fintech infrastructure hiring accounting controllers, risk analysts, and platform engineers.'
    },
    {
        'company_name': 'GitLab Inc.',
        'domain': 'gitlab.com',
        'website': 'https://about.gitlab.com',
        'careers_url': 'https://about.gitlab.com/jobs/',
        'city': 'Remote EMEA / Global',
        'country': 'Worldwide',
        'industry_vertical': EmployerLead.IndustryVertical.IT_CLOUD_DEVOPS,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'All-remote DevSecOps platform hiring globally across software engineering, cloud SRE, security compliance, and support.'
    },
    # --- CANADA ---
    {
        'company_name': 'TELUS Health',
        'domain': 'telushealth.com',
        'website': 'https://www.telushealth.com',
        'careers_url': 'https://www.telushealth.com/careers',
        'city': 'Toronto, ON',
        'country': 'Canada',
        'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Leading Canadian healthcare technology, EHR, claims adjudication, medical billing software, and clinical services employer.'
    },
    {
        'company_name': 'Bench Accounting',
        'domain': 'bench.co',
        'website': 'https://www.bench.co',
        'careers_url': 'https://www.bench.co/careers',
        'city': 'Vancouver, BC',
        'country': 'Canada',
        'industry_vertical': EmployerLead.IndustryVertical.FINANCE_ACCOUNTING,
        'company_size': EmployerLead.CompanySize.SIZE_201_500,
        'snippet': 'Cloud bookkeeping, tax compliance, financial reporting, and accounting software specialists across North America.'
    },
    {
        'company_name': 'Shopify Inc.',
        'domain': 'shopify.com',
        'website': 'https://www.shopify.com',
        'careers_url': 'https://www.shopify.com/careers',
        'city': 'Ottawa / Remote Global',
        'country': 'Canada',
        'industry_vertical': EmployerLead.IndustryVertical.IT_SOFTWARE_DEV,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global commerce platform hiring full-stack engineers, data scientists, SREs, and remote support advisors worldwide.'
    },
    # --- AFRICA (NIGERIA, KENYA, GHANA, SOUTH AFRICA) ---
    {
        'company_name': 'Reliance Health',
        'domain': 'getreliancehealth.com',
        'website': 'https://getreliancehealth.com',
        'careers_url': 'https://getreliancehealth.com/careers',
        'city': 'Lagos / Global Remote',
        'country': 'Nigeria',
        'industry_vertical': EmployerLead.IndustryVertical.HEALTHCARE_BPO,
        'company_size': EmployerLead.CompanySize.SIZE_201_500,
        'snippet': 'Fast-growing healthtech and health insurance platform hiring claims operations, medical coding, software, and clinical staff.'
    },
    {
        'company_name': 'Helium Health',
        'domain': 'heliumhealth.com',
        'website': 'https://heliumhealth.com',
        'careers_url': 'https://heliumhealth.com/careers',
        'city': 'Lagos',
        'country': 'Nigeria',
        'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
        'company_size': EmployerLead.CompanySize.SIZE_51_200,
        'snippet': 'Hospital EHR, digital health financing, and medical billing infrastructure serving clinics across West & East Africa.'
    },
    {
        'company_name': 'Paystack',
        'domain': 'paystack.com',
        'website': 'https://paystack.com',
        'careers_url': 'https://paystack.com/careers',
        'city': 'Lagos / Accra / Dubai',
        'country': 'Nigeria',
        'industry_vertical': EmployerLead.IndustryVertical.IT_SOFTWARE_DEV,
        'company_size': EmployerLead.CompanySize.SIZE_201_500,
        'snippet': 'African fintech payments infrastructure hiring backend engineers, QA engineers, security specialists, and finance operations.'
    },
    {
        'company_name': 'Flutterwave',
        'domain': 'flutterwave.com',
        'website': 'https://flutterwave.com',
        'careers_url': 'https://flutterwave.com/us/careers',
        'city': 'Lagos / London / US',
        'country': 'Nigeria',
        'industry_vertical': EmployerLead.IndustryVertical.IT_CLOUD_DEVOPS,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global cross-border payments infrastructure hiring cloud engineers, cybersecurity analysts, accountants, and support teams.'
    },
    {
        'company_name': 'mPharma',
        'domain': 'mpharma.com',
        'website': 'https://mpharma.com',
        'careers_url': 'https://mpharma.com/careers',
        'city': 'Accra',
        'country': 'Ghana',
        'industry_vertical': EmployerLead.IndustryVertical.HEALTHCARE_BPO,
        'company_size': EmployerLead.CompanySize.SIZE_201_500,
        'snippet': 'Pan-African healthcare and pharmacy operations network hiring health operations analysts, software engineers, and finance staff.'
    },
    {
        'company_name': 'Ilara Health',
        'domain': 'ilarahealth.com',
        'website': 'https://www.ilarahealth.com',
        'careers_url': 'https://www.ilarahealth.com/careers',
        'city': 'Nairobi',
        'country': 'Kenya',
        'industry_vertical': EmployerLead.IndustryVertical.HEALTHCARE_BPO,
        'company_size': EmployerLead.CompanySize.SIZE_51_200,
        'snippet': 'Primary healthcare diagnostics and clinic network across East Africa hiring medical operations and engineering talent.'
    },
    {
        'company_name': 'Discovery Health South Africa',
        'domain': 'discovery.co.za',
        'website': 'https://www.discovery.co.za',
        'careers_url': 'https://careers.discovery.co.za',
        'city': 'Johannesburg',
        'country': 'South Africa',
        'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_CODING,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Leading South African health administrator hiring medical claims assessors, ICD-10 clinical coders, actuaries, and developers.'
    },
    {
        'company_name': 'Andela',
        'domain': 'andela.com',
        'website': 'https://www.andela.com',
        'careers_url': 'https://www.andela.com/careers',
        'city': 'Global Remote / Africa',
        'country': 'Worldwide',
        'industry_vertical': EmployerLead.IndustryVertical.IT_SOFTWARE_DEV,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global distributed engineering and technology marketplace hiring talent operations, cloud engineers, and QA leaders.'
    },
    # --- MIDDLE EAST & APAC (UAE, AUSTRALIA, INDIA, SINGAPORE, NEW ZEALAND, PHILIPPINES) ---
    {
        'company_name': 'Vezeeta',
        'domain': 'vezeeta.com',
        'website': 'https://www.vezeeta.com',
        'careers_url': 'https://careers.vezeeta.com',
        'city': 'Dubai / Cairo',
        'country': 'United Arab Emirates',
        'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
        'company_size': EmployerLead.CompanySize.SIZE_201_500,
        'snippet': 'MENA healthcare booking and clinic management platform hiring healthcare RCM analysts, software developers, and support teams.'
    },
    {
        'company_name': 'Telstra Health',
        'domain': 'telstrahealth.com',
        'website': 'https://www.telstrahealth.com',
        'careers_url': 'https://www.telstrahealth.com/content/telstrahealth/en/home/careers.html',
        'city': 'Melbourne',
        'country': 'Australia',
        'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_CODING,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Australia largest eHealth provider specializing in hospital administration, clinical coding, analytics, and health IT.'
    },
    {
        'company_name': 'Healius Healthcare',
        'domain': 'healius.com.au',
        'website': 'https://www.healius.com.au',
        'careers_url': 'https://www.healius.com.au/careers/',
        'city': 'Sydney',
        'country': 'Australia',
        'industry_vertical': EmployerLead.IndustryVertical.HEALTHCARE_BPO,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Diagnostic imaging and pathology healthcare network across Australia hiring medical billing, claims, and IT specialists.'
    },
    {
        'company_name': 'Xero Limited',
        'domain': 'xero.com',
        'website': 'https://www.xero.com',
        'careers_url': 'https://www.xero.com/careers/',
        'city': 'Wellington / Global',
        'country': 'New Zealand',
        'industry_vertical': EmployerLead.IndustryVertical.FINANCE_ACCOUNTING,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global cloud accounting software leader hiring product engineers, DevOps cloud architects, and accounting specialists.'
    },
    {
        'company_name': 'IKS Health',
        'domain': 'ikshealth.com',
        'website': 'https://www.ikshealth.com',
        'careers_url': 'https://www.ikshealth.com/careers/',
        'city': 'Mumbai / Global US',
        'country': 'India',
        'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global healthcare enablement and RCM delivery partner specializing in medical coding, denials management, and prior auth.'
    },
    {
        'company_name': 'Practo Technologies',
        'domain': 'practo.com',
        'website': 'https://www.practo.com',
        'careers_url': 'https://www.practo.com/company/careers',
        'city': 'Bengaluru',
        'country': 'India',
        'industry_vertical': EmployerLead.IndustryVertical.IT_SOFTWARE_DEV,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Digital healthcare and clinic ERP network across India & APAC hiring engineers, QA, and clinical support operations.'
    },
    {
        'company_name': 'Doctor Anywhere',
        'domain': 'doctoranywhere.com',
        'website': 'https://doctoranywhere.com',
        'careers_url': 'https://doctoranywhere.com/careers',
        'city': 'Singapore',
        'country': 'Singapore',
        'industry_vertical': EmployerLead.IndustryVertical.HEALTHCARE_BPO,
        'company_size': EmployerLead.CompanySize.SIZE_201_500,
        'snippet': 'Southeast Asian omnichannel healthcare provider hiring medical claims operations, developers, and clinical coordinators.'
    },
    {
        'company_name': 'TaskUs Global BPO',
        'domain': 'taskus.com',
        'website': 'https://www.taskus.com',
        'careers_url': 'https://www.taskus.com/careers/',
        'city': 'Manila / Global',
        'country': 'Philippines',
        'industry_vertical': EmployerLead.IndustryVertical.BUSINESS_BPO,
        'company_size': EmployerLead.CompanySize.SIZE_501_PLUS,
        'snippet': 'Global outsourced digital customer support, healthcare BPO operations, AI operations, and trust & safety teams.'
    },
]

# Backward-compatible alias for existing imports
CURATED_HEALTHCARE_EMPLOYERS = CURATED_WORLDWIDE_EMPLOYERS


def _unwrap_ddg_href(raw_href: str) -> str:
    if not raw_href:
        return ''
    if raw_href.startswith('//'):
        raw_href = 'https:' + raw_href
    parsed = urlparse(raw_href)
    if 'duckduckgo.com' in parsed.netloc and parsed.path.startswith('/l/'):
        qs = parse_qs(parsed.query)
        uddg = qs.get('uddg')
        if uddg:
            return uddg[0]
    return raw_href


def _build_web_query(query: str, country: str) -> str:
    clean_q = (query or '').strip() or 'medical billing software engineering accounting'
    if is_worldwide_location(country):
        return f"{clean_q} company careers"
    return f"{clean_q} company {country}"


def _search_duckduckgo_web(search_q: str, query_text: str, country: str, limit: int) -> list[dict]:
    if BeautifulSoup is None:
        return []
    try:
        resp = requests.get(
            'https://html.duckduckgo.com/html/',
            params={'q': search_q},
            headers=WEB_SEARCH_HEADERS,
            timeout=4,
        )
        if getattr(resp, 'status_code', 0) != 200 or not getattr(resp, 'text', ''):
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        links = soup.select('a.result__a')
        if not links:
            return []

        results = []
        seen_domains = set()
        for a_tag in links:
            raw_href = a_tag.get('href', '')
            link = _unwrap_ddg_href(raw_href)
            domain = normalize_company_domain(link)
            if not domain or '.' not in domain:
                continue
            if any(ign in domain for ign in SEARCH_NOISE_DOMAINS):
                continue
            if domain in seen_domains:
                continue
            seen_domains.add(domain)

            parent_result = a_tag.find_parent(class_=re.compile(r'result'))
            snippet_tag = parent_result.select_one('.result__snippet') if parent_result else None
            snippet = snippet_tag.get_text(' ', strip=True) if snippet_tag else ''
            title_text = a_tag.get_text(' ', strip=True)
            company_name = re.split(r'\s+[-|—:]\s+', title_text)[0].strip()[:120] or domain.split('.')[0].capitalize()

            parsed = urlparse(link)
            root_site = f"{parsed.scheme or 'https'}://{parsed.netloc}" if parsed.netloc else f"https://{domain}"
            inferred_country = infer_country_from_location(
                f"{title_text} {snippet} {country}",
                fallback=country if not is_worldwide_location(country) else 'Worldwide',
            )
            vertical = classify_industry_vertical(f"{query_text} {title_text} {snippet}")

            results.append({
                'company_name': company_name,
                'domain': domain,
                'website': root_site,
                'careers_url': link if any(k in link.lower() for k in ('career', 'job', 'hiring')) else '',
                'city': inferred_country if inferred_country != 'Worldwide' else 'Global',
                'country': inferred_country,
                'industry_vertical': vertical,
                'company_size': EmployerLead.CompanySize.SIZE_51_200,
                'snippet': snippet or f"Discovered via live web index for '{query_text}'.",
                'source': EmployerLead.Source.WEB_SEARCH,
            })
            if len(results) >= limit:
                break
        return results
    except Exception as e:
        logger.debug(f"DuckDuckGo live web search skipped: {e}")
        return []


def search_healthcare_employers(query: str, limit: int = 25, country: str = 'Worldwide') -> list:
    """
    Executes a worldwide multi-sector employer discovery search across live web APIs
    (Google Custom Search, SerpAPI, DuckDuckGo live web index) plus curated global
    employers across Healthcare, IT/Cloud/Security, Finance, and BPO.
    """
    clean_query = (query or '').strip()
    search_q = _build_web_query(clean_query, country)
    target_country = country if not is_worldwide_location(country) else 'Worldwide'

    google_key = getattr(settings, 'GOOGLE_CUSTOM_SEARCH_API_KEY', None)
    google_cx = getattr(settings, 'GOOGLE_CUSTOM_SEARCH_CX', None)
    serpapi_key = getattr(settings, 'SERPAPI_API_KEY', None)

    web_items = []

    # 1. Check Google Custom Search API (if configured)
    if google_key and google_cx:
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': google_key,
                'cx': google_cx,
                'q': search_q,
                'num': min(10, limit),
            }
            res = requests.get(url, params=params, timeout=6)
            if res.status_code == 200:
                data = res.json()
                for item in data.get('items', []):
                    link = item.get('link', '')
                    domain = normalize_company_domain(link)
                    if domain and not any(ign in domain for ign in SEARCH_NOISE_DOMAINS):
                        snippet = item.get('snippet', '')
                        title_raw = item.get('title', '')
                        web_items.append({
                            'company_name': title_raw.split(' - ')[0].split(' | ')[0].strip(),
                            'domain': domain,
                            'website': link,
                            'careers_url': '',
                            'city': target_country if target_country != 'Worldwide' else 'Global',
                            'country': infer_country_from_location(f"{title_raw} {snippet}", fallback=target_country),
                            'industry_vertical': classify_industry_vertical(f"{clean_query} {title_raw} {snippet}"),
                            'company_size': EmployerLead.CompanySize.SIZE_51_200,
                            'snippet': snippet,
                            'source': EmployerLead.Source.GOOGLE_SEARCH,
                        })
        except Exception as e:
            logger.warning(f"Google Search API query failed: {e}")

    # 2. Check SerpAPI (if configured)
    if not web_items and serpapi_key:
        try:
            url = "https://serpapi.com/search"
            params = {
                'api_key': serpapi_key,
                'engine': 'google',
                'q': search_q,
                'num': limit,
            }
            res = requests.get(url, params=params, timeout=6)
            if res.status_code == 200:
                data = res.json()
                for r in data.get('organic_results', []):
                    link = r.get('link', '')
                    domain = normalize_company_domain(link)
                    if domain and not any(ign in domain for ign in SEARCH_NOISE_DOMAINS):
                        snippet = r.get('snippet', '')
                        title_raw = r.get('title', '')
                        web_items.append({
                            'company_name': title_raw.split(' - ')[0].split(' | ')[0].strip(),
                            'domain': domain,
                            'website': link,
                            'careers_url': '',
                            'city': target_country if target_country != 'Worldwide' else 'Global',
                            'country': infer_country_from_location(f"{title_raw} {snippet}", fallback=target_country),
                            'industry_vertical': classify_industry_vertical(f"{clean_query} {title_raw} {snippet}"),
                            'company_size': EmployerLead.CompanySize.SIZE_51_200,
                            'snippet': snippet,
                            'source': EmployerLead.Source.GOOGLE_SEARCH,
                        })
        except Exception as e:
            logger.warning(f"SerpAPI query failed: {e}")

    # 3. Free Live Web Index via DuckDuckGo HTML Search
    if not web_items:
        web_items = _search_duckduckgo_web(search_q, clean_query, country, limit=limit)

    # 4. Curated Worldwide Multi-Sector Directory Matching & Top-Up
    q_words = [
        w.lower() for w in re.split(r'[\s,/|]+', clean_query)
        if len(w) > 2 and w.lower() not in ('all', 'and', 'the', 'global', 'worldwide')
    ]
    strict_matches = []
    geo_matches = []

    for comp in CURATED_WORLDWIDE_EMPLOYERS:
        if not is_worldwide_location(country) and not location_matches(f"{comp['city']} {comp['country']}", country):
            continue
        comp_text = f"{comp['company_name']} {comp['city']} {comp['country']} {comp['snippet']} {comp['domain']} {comp['industry_vertical']}".lower()
        if not q_words or any(w in comp_text for w in q_words):
            strict_matches.append(comp.copy())
        else:
            geo_matches.append(comp.copy())

    curated_pool = strict_matches or geo_matches or [c.copy() for c in CURATED_WORLDWIDE_EMPLOYERS]

    # When querying Worldwide, interleave results across countries so small limits still cover multiple regions
    if is_worldwide_location(country) and len(curated_pool) > 1:
        by_country = {}
        for comp in curated_pool:
            c_key = comp.get('country') or 'Worldwide'
            by_country.setdefault(c_key, []).append(comp)
        diversified = []
        buckets = list(by_country.values())
        while buckets:
            next_buckets = []
            for b in buckets:
                diversified.append(b.pop(0))
                if b:
                    next_buckets.append(b)
            buckets = next_buckets
        curated_pool = diversified

    # Merge live web search results with curated directory deduplicated by domain
    combined = []
    seen_domains = set()
    for item in web_items + curated_pool:
        dom = (item.get('domain') or '').lower()
        if dom and dom in seen_domains:
            continue
        if dom:
            seen_domains.add(dom)
        combined.append(item)
        if len(combined) >= limit:
            break

    return combined[:limit]


def import_discovered_lead(data: dict, assigned_staff=None, scrape_website: bool = False) -> tuple:
    """
    Ingests a discovered company dict into GrowthOS.
    Deduplicates by normalized domain, saves contact/social details and active hiring
    signals when present, computes initial scores, and initializes CRM tracking.
    Returns (lead, created: bool).
    """
    domain = normalize_company_domain(data.get('domain') or data.get('website', ''))
    if not domain:
        raise ValueError("Invalid company domain for ingestion.")

    company_name = (data.get('company_name') or '').strip() or domain.split('.')[0].capitalize()
    website = data.get('website') or f"https://{domain}"
    raw_country = (data.get('country') or '').strip() or 'Worldwide'
    social_links = data.get('social_links') if isinstance(data.get('social_links'), dict) else {}

    lead, created = EmployerLead.objects.get_or_create(
        domain=domain,
        defaults={
            'company_name': company_name,
            'website': website,
            'careers_url': data.get('careers_url', ''),
            'phone': (data.get('phone') or '')[:80],
            'contact_email': data.get('contact_email') or '',
            'social_links': social_links,
            'city': (data.get('city') or '')[:100],
            'country': raw_country[:100],
            'industry_vertical': data.get('industry_vertical', EmployerLead.IndustryVertical.RCM_SERVICES),
            'company_size': data.get('company_size', EmployerLead.CompanySize.SIZE_51_200),
            'source': data.get('source') or EmployerLead.Source.GOOGLE_SEARCH,
            'status': EmployerLead.Status.LEAD,
            'assigned_staff': assigned_staff,
            'notes': data.get('snippet', '')
        }
    )

    if not created:
        updated_fields = []
        if not lead.careers_url and data.get('careers_url'):
            lead.careers_url = data['careers_url'][:200]
            updated_fields.append('careers_url')
        if not lead.city and data.get('city'):
            lead.city = data['city'][:100]
            updated_fields.append('city')
        if (not lead.country or lead.country == 'Worldwide') and raw_country and raw_country != 'Worldwide':
            lead.country = raw_country[:100]
            updated_fields.append('country')
        if not lead.phone and data.get('phone'):
            lead.phone = data['phone'][:80]
            updated_fields.append('phone')
        if not lead.contact_email and data.get('contact_email'):
            lead.contact_email = data['contact_email']
            updated_fields.append('contact_email')
        if social_links:
            merged_socials = dict(lead.social_links or {}) if isinstance(lead.social_links, dict) else {}
            changed = False
            for k, v in social_links.items():
                if v and not merged_socials.get(k):
                    merged_socials[k] = v
                    changed = True
            if changed:
                lead.social_links = merged_socials
                updated_fields.append('social_links')
        if updated_fields:
            lead.save(update_fields=updated_fields)
    else:
        CRMOpportunity.objects.get_or_create(
            lead=lead,
            defaults={'stage': CRMOpportunity.Stage.STAGE_1_DISCOVERED}
        )

        # Save active job title from job-board connectors directly as a HiringSignal
        job_title = (data.get('job_title') or '').strip()
        if job_title:
            from apps.growth_os.services.scraper import ROLE_PATTERNS, extract_skills_from_text
            role_cat = HiringSignal.RoleCategory.OTHER
            for cat, pattern in ROLE_PATTERNS:
                if pattern.search(job_title):
                    role_cat = cat
                    break
            HiringSignal.objects.get_or_create(
                lead=lead,
                job_title=job_title[:150],
                defaults={
                    'role_category': role_cat,
                    'job_url': (data.get('job_url') or data.get('careers_url') or '')[:200],
                    'extracted_skills': extract_skills_from_text(f"{job_title} {data.get('snippet', '')}")[:8],
                    'days_open': 1,
                    'is_active': True,
                    'raw_description': data.get('snippet', ''),
                }
            )

        calculate_lead_intent_score(lead)
        compute_lead_reverse_matches(lead)

        staff_str = assigned_staff.get_full_name() or assigned_staff.email if assigned_staff else "Discovery Engine"
        CRMActivity.objects.create(
            lead=lead,
            activity_type=CRMActivity.ActivityType.NOTE,
            summary=f"Discovered and imported into GrowthOS by {staff_str}",
            performed_by=assigned_staff
        )

    if scrape_website and (lead.website or lead.careers_url):
        try:
            from apps.growth_os.services.scraper import inspect_lead_career_page
            inspect_lead_career_page(lead)
        except Exception as e:
            logger.debug(f"Auto website contact scrape skipped for {lead.domain}: {e}")

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
