"""
Connector Registry and Unified Multi-Channel Sourcing Coordinator.
"""
from apps.growth_os.models import EmployerLead
from apps.growth_os.services.discovery import search_healthcare_employers
from .linkedin_connector import LinkedInJobsConnector
from .indeed_connector import IndeedJobsConnector

CONNECTOR_REGISTRY = {
    'GOOGLE_SEARCH': {
        'label': 'Google Search & Places API',
        'handler': lambda q, loc, lim: search_healthcare_employers(q, limit=lim, country=loc)
    },
    'LINKEDIN_JOBS': {
        'label': 'LinkedIn Jobs & Companies',
        'handler': lambda q, loc, lim: LinkedInJobsConnector().search(q, location=loc, limit=lim)
    },
    'INDEED_JOBS': {
        'label': 'Indeed Hiring Intelligence',
        'handler': lambda q, loc, lim: IndeedJobsConnector().search(q, location=loc, limit=lim)
    }
}


def get_sourcing_connector(channel_key: str):
    return CONNECTOR_REGISTRY.get(channel_key)


def search_all_connectors(query: str, location: str = "United States", limit_per_source: int = 8, source_key: str = None) -> list[dict]:
    """
    Executes search across registered channels (or a single requested source)
    and merges results with deduplication by company domain.
    """
    combined_results = []
    seen_domains = set()

    connectors_to_run = {}
    if source_key and source_key in CONNECTOR_REGISTRY:
        connectors_to_run[source_key] = CONNECTOR_REGISTRY[source_key]
    else:
        connectors_to_run = CONNECTOR_REGISTRY

    for key, connector in connectors_to_run.items():
        try:
            items = connector['handler'](query, location, limit_per_source)
            for item in items:
                if 'source' not in item or not item['source']:
                    item['source'] = key
                domain = item.get('domain', '').lower()
                if domain and domain not in seen_domains:
                    seen_domains.add(domain)
                    combined_results.append(item)
                elif not domain:
                    combined_results.append(item)
        except Exception:
            continue

    return combined_results
