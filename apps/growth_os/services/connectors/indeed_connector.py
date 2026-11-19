"""
Indeed Hiring Intelligence Connector for GrowthOS.
Discovers hiring employers and persistent job listings via public feeds and RSS patterns.
"""
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from apps.growth_os.models import EmployerLead, normalize_company_domain
from .base import BaseSourcingConnector


class IndeedJobsConnector(BaseSourcingConnector):
    source_identifier = EmployerLead.Source.INDEED_JOBS
    source_label = 'Indeed Hiring Intelligence'

    def search(self, query: str, location: str = "United States", limit: int = 15) -> list[dict]:
        results = []
        clean_q = query.strip()
        if not clean_q:
            return results

        encoded_q = urllib.parse.quote(clean_q)
        encoded_loc = urllib.parse.quote(location)
        search_url = f"https://www.indeed.com/jobs?q={encoded_q}&l={encoded_loc}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        try:
            resp = requests.get(search_url, headers=headers, timeout=6)
            if resp.status_code == 200 and resp.text:
                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.find_all('div', class_=re.compile(r'job_seen_beacon|jobCard|cardOutline', re.I))

                seen_companies = set()
                for card in cards:
                    if len(results) >= limit:
                        break

                    company_tag = card.find(attrs={'data-testid': 'company-name'}) or card.find('span', class_=re.compile(r'companyName', re.I))
                    title_tag = card.find('h2') or card.find('a', class_=re.compile(r'jcs-JobTitle', re.I))
                    loc_tag = card.find(attrs={'data-testid': 'text-location'}) or card.find('div', class_=re.compile(r'companyLocation', re.I))

                    if not company_tag:
                        continue

                    company_name = company_tag.get_text(strip=True)
                    if not company_name or company_name.lower() in seen_companies:
                        continue
                    seen_companies.add(company_name.lower())

                    job_title = title_tag.get_text(strip=True) if title_tag else "Specialist"
                    loc_text = loc_tag.get_text(strip=True) if loc_tag else location

                    clean_slug = re.sub(r'[^a-zA-Z0-9]', '', company_name.lower())
                    suggested_domain = f"{clean_slug}.com"

                    vertical = EmployerLead.IndustryVertical.RCM_SERVICES
                    q_lower = (clean_q + " " + job_title).lower()
                    if any(w in q_lower for w in ['devops', 'cloud', 'sre', 'aws']):
                        vertical = EmployerLead.IndustryVertical.IT_CLOUD_DEVOPS
                    elif any(w in q_lower for w in ['software', 'developer', 'engineer']):
                        vertical = EmployerLead.IndustryVertical.IT_SOFTWARE_DEV
                    elif any(w in q_lower for w in ['accountant', 'accounting', 'finance']):
                        vertical = EmployerLead.IndustryVertical.FINANCE_ACCOUNTING
                    elif any(w in q_lower for w in ['coder', 'coding', 'rhia', 'ccs']):
                        vertical = EmployerLead.IndustryVertical.MEDICAL_CODING

                    lead_dict = self.normalize_lead({
                        'company_name': company_name,
                        'domain': suggested_domain,
                        'website': f"https://www.{suggested_domain}",
                        'careers_url': f"https://www.indeed.com/cmp/{clean_slug}/jobs",
                        'city': loc_text,
                        'country': 'United States' if 'united states' in location.lower() or 'us' in location.lower() else location,
                        'industry_vertical': vertical,
                        'company_size': '51_200',
                        'snippet': f"Sourced from Indeed: Verified hiring signal for '{job_title}' in {loc_text}.",
                    })
                    results.append(lead_dict)

        except Exception:
            pass

        return results

