"""
Worldwide Live Public Job-Board Connectors for Kodafriq GrowthOS.
Pulls live actively-hiring companies worldwide across Healthcare, IT/Cloud/Security,
Finance, and BPO without requiring paid API keys:
- Remotive Global Remote API
- Arbeitnow Global & European Job Board API
- Jobicy Worldwide Remote Jobs API
- Himalayas Global Remote API
- RemoteOK Worldwide Feed API
"""
import re
import logging
import requests
from apps.growth_os.models import EmployerLead
from .base import (
    BaseSourcingConnector,
    classify_industry_vertical,
    extract_company_website_from_html,
    infer_country_from_location,
    is_worldwide_location,
    location_matches,
    suggest_company_domain,
)

logger = logging.getLogger(__name__)

API_HEADERS = {
    'User-Agent': 'Kodafriq-GrowthOS/2.0 (https://kodafriq.com)',
    'Accept': 'application/json',
}


def _safe_json_get(url: str, params: dict = None, timeout: int = 4):
    """Performs GET and returns decoded dict/list, or None if response is HTML/mock/error."""
    try:
        resp = requests.get(url, params=params, headers=API_HEADERS, timeout=timeout)
        if getattr(resp, 'status_code', 0) != 200:
            return None
        data = resp.json()
        if isinstance(data, (dict, list)):
            return data
    except Exception as e:
        logger.debug(f"JSON board fetch skipped for {url}: {e}")
    return None


def _build_query_tokens(query: str) -> list[str]:
    stop = {'and', 'the', 'for', 'with', 'all', 'services', 'global', 'worldwide', 'company', 'companies', 'firm', 'firms'}
    tokens = [w.lower() for w in re.split(r'[\s,/|]+', query or '') if len(w) >= 3 and w.lower() not in stop]
    return tokens


def _entry_relevance_score(searchable_text: str, tokens: list[str]) -> int:
    if not tokens:
        return 1
    lower = searchable_text.lower()
    hits = sum(1 for tok in tokens if tok in lower)
    return hits


def _make_domain(company_name: str, description_html: str = '', apply_url: str = '') -> tuple[str, str]:
    site, dom = extract_company_website_from_html(description_html, company_name)
    if dom:
        return site, dom
    dom = suggest_company_domain(company_name)
    if not dom:
        return '', ''
    return f"https://www.{dom}", dom


class _BaseFeedBoardConnector(BaseSourcingConnector):
    """Shared filter, deduplication, and normalization loop for global job API feeds."""

    def _finalize_items(self, raw_entries: list[dict], query: str, location: str, limit: int) -> list[dict]:
        tokens = _build_query_tokens(query)
        scored = []
        seen_companies = set()

        for entry in raw_entries:
            company_name = (entry.get('company_name') or '').strip()
            if not company_name:
                continue
            comp_key = company_name.lower()
            if comp_key in seen_companies:
                continue

            loc_raw = entry.get('location') or 'Worldwide'
            if not is_worldwide_location(location) and not location_matches(loc_raw, location):
                continue

            searchable = f"{company_name} {entry.get('title', '')} {entry.get('category', '')} {entry.get('tags', '')} {loc_raw}"
            rel = _entry_relevance_score(searchable, tokens)
            scored.append((rel, entry))

        # Prefer strict keyword matches first; backfill with general global active-hiring employers when needed
        strict = [item for rel, item in scored if rel > 0]
        broad = [item for rel, item in scored if rel == 0]
        ordered = strict + (broad if len(strict) < limit else [])

        results = []
        for entry in ordered:
            company_name = entry['company_name'].strip()
            comp_key = company_name.lower()
            if comp_key in seen_companies:
                continue
            seen_companies.add(comp_key)

            title = (entry.get('title') or 'Specialist').strip()[:140]
            loc_raw = (entry.get('location') or 'Remote / Worldwide').strip()
            desc_html = entry.get('description') or ''
            job_url = entry.get('job_url') or ''

            website, domain = _make_domain(company_name, desc_html, job_url)
            if not domain:
                continue

            inferred_country = infer_country_from_location(
                loc_raw,
                fallback=location if not is_worldwide_location(location) else 'Worldwide',
            )
            vertical = classify_industry_vertical(f"{query} {title} {entry.get('category', '')} {entry.get('tags', '')}")

            results.append(self.normalize_lead({
                'company_name': company_name,
                'domain': domain,
                'website': website,
                'careers_url': job_url,
                'city': loc_raw[:100],
                'country': inferred_country,
                'industry_vertical': vertical,
                'company_size': EmployerLead.CompanySize.SIZE_51_200,
                'snippet': f"Sourced from {self.source_label}: Actively hiring '{title}' ({loc_raw}).",
                'job_title': title,
                'job_url': job_url,
            }))
            if len(results) >= limit:
                break
        return results


class RemotiveJobsConnector(_BaseFeedBoardConnector):
    source_identifier = EmployerLead.Source.REMOTIVE
    source_label = 'Remotive Global Jobs'

    def search(self, query: str, location: str = "Worldwide", limit: int = 15) -> list[dict]:
        tokens = _build_query_tokens(query)
        search_param = ' '.join(tokens[:2]) if tokens else ''
        data = _safe_json_get('https://remotive.com/api/remote-jobs', params={'search': search_param} if search_param else None)
        jobs = data.get('jobs', []) if isinstance(data, dict) else []
        if not jobs and search_param:
            broad_data = _safe_json_get('https://remotive.com/api/remote-jobs', params={'limit': 50})
            if isinstance(broad_data, dict):
                jobs = broad_data.get('jobs', [])

        entries = [
            {
                'company_name': j.get('company_name', ''),
                'title': j.get('title', ''),
                'category': j.get('category', ''),
                'tags': ' '.join(j.get('tags') or []),
                'location': j.get('candidate_required_location') or 'Worldwide',
                'description': j.get('description', ''),
                'job_url': j.get('url', ''),
            }
            for j in jobs if isinstance(j, dict)
        ]
        return self._finalize_items(entries, query, location, limit)


class ArbeitnowJobsConnector(_BaseFeedBoardConnector):
    source_identifier = EmployerLead.Source.ARBEITNOW
    source_label = 'Arbeitnow Global & EMEA Jobs'

    def search(self, query: str, location: str = "Worldwide", limit: int = 15) -> list[dict]:
        jobs = []
        max_pages = 2 if limit > 12 else 1
        for page in range(1, max_pages + 1):
            data = _safe_json_get('https://www.arbeitnow.com/api/job-board-api', params={'page': page})
            page_jobs = data.get('data', []) if isinstance(data, dict) else []
            if not page_jobs:
                break
            jobs.extend(page_jobs)

        entries = [
            {
                'company_name': j.get('company_name', ''),
                'title': j.get('title', ''),
                'category': ' '.join(j.get('job_types') or []),
                'tags': ' '.join(j.get('tags') or []),
                'location': j.get('location') or ('Remote' if j.get('remote') else 'Europe'),
                'description': j.get('description', ''),
                'job_url': j.get('url', ''),
            }
            for j in jobs if isinstance(j, dict)
        ]
        return self._finalize_items(entries, query, location, limit)


class JobicyJobsConnector(_BaseFeedBoardConnector):
    source_identifier = EmployerLead.Source.JOBICY
    source_label = 'Jobicy Worldwide Remote Jobs'

    def search(self, query: str, location: str = "Worldwide", limit: int = 15) -> list[dict]:
        data = _safe_json_get('https://jobicy.com/api/v2/remote-jobs', params={'count': 50})
        jobs = data.get('jobs', []) if isinstance(data, dict) else []
        entries = [
            {
                'company_name': j.get('companyName', ''),
                'title': j.get('jobTitle', ''),
                'category': ' '.join(j.get('jobIndustry') or []) if isinstance(j.get('jobIndustry'), list) else str(j.get('jobIndustry') or ''),
                'tags': j.get('jobLevel', ''),
                'location': j.get('jobGeo') or 'Anywhere',
                'description': j.get('jobDescription', '') or j.get('jobExcerpt', ''),
                'job_url': j.get('url', ''),
            }
            for j in jobs if isinstance(j, dict)
        ]
        return self._finalize_items(entries, query, location, limit)


class HimalayasJobsConnector(_BaseFeedBoardConnector):
    source_identifier = EmployerLead.Source.HIMALAYAS
    source_label = 'Himalayas Global Remote Jobs'

    def search(self, query: str, location: str = "Worldwide", limit: int = 15) -> list[dict]:
        data = _safe_json_get('https://himalayas.app/jobs/api', params={'limit': 50})
        jobs = data.get('jobs', []) if isinstance(data, dict) else []
        entries = []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            loc_list = j.get('locationRestrictions') or []
            loc_str = ', '.join(loc_list) if isinstance(loc_list, list) and loc_list else 'Worldwide'
            cats = (j.get('parentCategories') or []) + (j.get('categories') or [])
            entries.append({
                'company_name': j.get('companyName', ''),
                'title': j.get('title', ''),
                'category': ' '.join(cats) if isinstance(cats, list) else str(cats),
                'tags': j.get('employmentType', ''),
                'location': loc_str,
                'description': j.get('description', '') or j.get('excerpt', ''),
                'job_url': j.get('applicationLink') or j.get('guid') or '',
            })
        return self._finalize_items(entries, query, location, limit)


class RemoteOKJobsConnector(_BaseFeedBoardConnector):
    source_identifier = EmployerLead.Source.REMOTEOK
    source_label = 'RemoteOK Worldwide Jobs'

    def search(self, query: str, location: str = "Worldwide", limit: int = 15) -> list[dict]:
        data = _safe_json_get('https://remoteok.com/api')
        jobs = data[1:] if isinstance(data, list) and len(data) > 1 else []
        entries = [
            {
                'company_name': j.get('company', ''),
                'title': j.get('position', ''),
                'category': '',
                'tags': ' '.join(j.get('tags') or []),
                'location': j.get('location') or 'Worldwide',
                'description': j.get('description', ''),
                'job_url': j.get('apply_url') or j.get('url') or '',
            }
            for j in jobs if isinstance(j, dict) and j.get('company')
        ]
        return self._finalize_items(entries, query, location, limit)
