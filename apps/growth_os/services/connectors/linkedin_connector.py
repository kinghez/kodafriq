"""
LinkedIn Jobs & Company Sourcing Connector for GrowthOS.
Discovers hiring employers globally across North America, Europe/UK, Africa, EMEA,
and APAC via LinkedIn public guest job search endpoints.
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

GLOBAL_LINKEDIN_HUBS = [
    'Worldwide',
    'United Kingdom',
    'Canada',
    'Germany',
    'United Arab Emirates',
    'Nigeria',
]


class LinkedInJobsConnector(BaseSourcingConnector):
    source_identifier = EmployerLead.Source.LINKEDIN_JOBS
    source_label = 'LinkedIn Public Jobs & Companies'

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

        if is_worldwide_location(location):
            locations_to_query = ['Worldwide']
            if limit > 10:
                locations_to_query.extend(GLOBAL_LINKEDIN_HUBS[1:3])
        else:
            locations_to_query = [location]

        seen_companies = set()

        for target_loc in locations_to_query:
            if len(results) >= limit:
                break

            starts = [0, 25] if (limit > 20 and len(locations_to_query) == 1) else [0]
            for start_offset in starts:
                if len(results) >= limit:
                    break

                encoded_q = urllib.parse.quote(clean_q)
                encoded_loc = urllib.parse.quote(target_loc)
                search_url = (
                    f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                    f"?keywords={encoded_q}&location={encoded_loc}&start={start_offset}"
                )

                try:
                    resp = requests.get(search_url, headers=headers, timeout=4)
                    if resp.status_code != 200 or not resp.text:
                        continue

                    soup = BeautifulSoup(resp.text, 'html.parser')
                    cards = soup.find_all('li')
                    if not cards:
                        break

                    for card in cards:
                        if len(results) >= limit:
                            break

                        company_tag = card.find('h4', class_=re.compile(r'base-search-card__subtitle|job-search-card__company-name', re.I))
                        if not company_tag:
                            company_tag = card.find('h4') or card.find('a', class_=re.compile(r'hidden-nested-link', re.I))

                        title_tag = card.find('h3', class_=re.compile(r'base-search-card__title', re.I)) or card.find('h3')
                        loc_tag = card.find('span', class_=re.compile(r'job-search-card__location', re.I)) or card.find('span')
                        link_tag = card.find('a', class_=re.compile(r'base-card__full-link', re.I))

                        if not company_tag:
                            continue

                        company_name = company_tag.get_text(strip=True)
                        if not company_name or company_name.lower() in seen_companies:
                            continue
                        seen_companies.add(company_name.lower())

                        job_title = title_tag.get_text(strip=True) if title_tag else "Specialist"
                        loc_text = loc_tag.get_text(strip=True) if loc_tag else target_loc
                        job_url = link_tag.get('href', '').split('?')[0] if link_tag else ''

                        clean_slug = re.sub(r'[^a-zA-Z0-9]', '', company_name.lower())
                        if not clean_slug:
                            continue
                        suggested_domain = f"{clean_slug}.com"

                        country_val = infer_country_from_location(
                            loc_text,
                            fallback=target_loc if not is_worldwide_location(target_loc) else 'Worldwide',
                        )
                        vertical = classify_industry_vertical(f"{clean_q} {job_title}")

                        results.append(self.normalize_lead({
                            'company_name': company_name,
                            'domain': suggested_domain,
                            'website': f"https://www.{suggested_domain}",
                            'careers_url': job_url or f"https://www.linkedin.com/company/{clean_slug}/jobs",
                            'city': loc_text,
                            'country': country_val,
                            'industry_vertical': vertical,
                            'company_size': EmployerLead.CompanySize.SIZE_51_200,
                            'snippet': f"Sourced from LinkedIn Jobs: Actively recruiting '{job_title}' in {loc_text}.",
                            'job_title': job_title,
                            'job_url': job_url,
                        }))
                except Exception:
                    continue

        return results
