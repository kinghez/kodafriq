"""
Indeed Worldwide Hiring Intelligence Connector for GrowthOS.
Routes across regional Indeed portals worldwide (US, UK, Canada, EU, UAE, Africa, APAC).
"""
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from apps.growth_os.models import EmployerLead
from .base import (
    BaseSourcingConnector,
    classify_industry_vertical,
    infer_country_from_location,
    is_worldwide_location,
)

REGIONAL_INDEED_HOSTS = {
    'united kingdom': 'uk.indeed.com',
    'uk': 'uk.indeed.com',
    'canada': 'ca.indeed.com',
    'australia': 'au.indeed.com',
    'germany': 'de.indeed.com',
    'netherlands': 'nl.indeed.com',
    'ireland': 'ie.indeed.com',
    'france': 'fr.indeed.com',
    'united arab emirates': 'ae.indeed.com',
    'uae': 'ae.indeed.com',
    'south africa': 'za.indeed.com',
    'nigeria': 'ng.indeed.com',
    'india': 'in.indeed.com',
    'singapore': 'sg.indeed.com',
}


class IndeedJobsConnector(BaseSourcingConnector):
    source_identifier = EmployerLead.Source.INDEED_JOBS
    source_label = 'Indeed Hiring Intelligence'

    def _get_host(self, location: str) -> str:
        loc_lower = (location or '').strip().lower()
        for key, host in REGIONAL_INDEED_HOSTS.items():
            if key in loc_lower:
                return host
        return 'www.indeed.com'

    def search(self, query: str, location: str = "Worldwide", limit: int = 15) -> list[dict]:
        results = []
        clean_q = (query or '').strip()
        if not clean_q:
            return results

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        target_locations = ['Remote', 'London', 'Toronto'] if (is_worldwide_location(location) and limit > 10) else [
            'Remote' if is_worldwide_location(location) else location
        ]
        seen_companies = set()

        for loc_query in target_locations[:2]:
            if len(results) >= limit:
                break
            host = self._get_host(loc_query)
            encoded_q = urllib.parse.quote(clean_q)
            encoded_loc = urllib.parse.quote(loc_query)
            search_url = f"https://{host}/jobs?q={encoded_q}&l={encoded_loc}"

            try:
                resp = requests.get(search_url, headers=headers, timeout=4)
                if resp.status_code != 200 or not resp.text:
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.find_all('div', class_=re.compile(r'job_seen_beacon|jobCard|cardOutline', re.I))

                for card in cards:
                    if len(results) >= limit:
                        break

                    company_tag = card.find(attrs={'data-testid': 'company-name'}) or card.find('span', class_=re.compile(r'companyName', re.I))
                    title_tag = card.find('h2') or card.find('a', class_=re.compile(r'jcs-JobTitle', re.I))
                    loc_tag = card.find(attrs={'data-testid': 'text-location'}) or card.find('div', class_=re.compile(r'companyLocation', re.I))
                    link_tag = card.find('a', class_=re.compile(r'jcs-JobTitle', re.I)) or card.find('a', href=True)

                    if not company_tag:
                        continue

                    company_name = company_tag.get_text(strip=True)
                    if not company_name or company_name.lower() in seen_companies:
                        continue
                    seen_companies.add(company_name.lower())

                    job_title = title_tag.get_text(strip=True) if title_tag else "Specialist"
                    loc_text = loc_tag.get_text(strip=True) if loc_tag else loc_query
                    job_href = link_tag.get('href', '') if link_tag else ''
                    if job_href and not job_href.startswith('http'):
                        job_href = f"https://{host}{job_href}"

                    clean_slug = re.sub(r'[^a-zA-Z0-9]', '', company_name.lower())
                    if not clean_slug:
                        continue
                    suggested_domain = f"{clean_slug}.com"

                    vertical = classify_industry_vertical(f"{clean_q} {job_title}")
                    country_val = infer_country_from_location(loc_text, fallback='Worldwide' if is_worldwide_location(location) else location)

                    results.append(self.normalize_lead({
                        'company_name': company_name,
                        'domain': suggested_domain,
                        'website': f"https://www.{suggested_domain}",
                        'careers_url': job_href or f"https://{host}/cmp/{clean_slug}/jobs",
                        'city': loc_text,
                        'country': country_val,
                        'industry_vertical': vertical,
                        'company_size': EmployerLead.CompanySize.SIZE_51_200,
                        'snippet': f"Sourced from Indeed ({host}): Hiring '{job_title}' in {loc_text}.",
                        'job_title': job_title,
                        'job_url': job_href,
                    }))
            except Exception:
                continue

        return results
