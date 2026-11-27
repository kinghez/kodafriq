"""
Connector Registry and Unified Worldwide Multi-Channel Sourcing Coordinator.
Runs global channels concurrently and deduplicates employers by normalized domain.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from .linkedin_connector import LinkedInJobsConnector
from .indeed_connector import IndeedJobsConnector
from .global_boards_connector import (
    RemotiveJobsConnector,
    ArbeitnowJobsConnector,
    JobicyJobsConnector,
    HimalayasJobsConnector,
    RemoteOKJobsConnector,
)


def _web_search_handler(query: str, location: str, limit: int) -> list[dict]:
    from apps.growth_os.services.discovery import search_healthcare_employers
    return search_healthcare_employers(query, limit=limit, country=location)


CONNECTOR_REGISTRY = {
    'GOOGLE_SEARCH': {
        'label': 'Web Search & Global Directory',
        'handler': _web_search_handler,
    },
    'LINKEDIN_JOBS': {
        'label': 'LinkedIn Jobs & Companies',
        'handler': lambda q, loc, lim: LinkedInJobsConnector().search(q, location=loc, limit=lim),
    },
    'INDEED_JOBS': {
        'label': 'Indeed Worldwide Hiring Intelligence',
        'handler': lambda q, loc, lim: IndeedJobsConnector().search(q, location=loc, limit=lim),
    },
    'REMOTIVE': {
        'label': 'Remotive Global Remote Jobs',
        'handler': lambda q, loc, lim: RemotiveJobsConnector().search(q, location=loc, limit=lim),
    },
    'ARBEITNOW': {
        'label': 'Arbeitnow Global & EMEA Jobs',
        'handler': lambda q, loc, lim: ArbeitnowJobsConnector().search(q, location=loc, limit=lim),
    },
    'JOBICY': {
        'label': 'Jobicy Worldwide Remote Jobs',
        'handler': lambda q, loc, lim: JobicyJobsConnector().search(q, location=loc, limit=lim),
    },
    'HIMALAYAS': {
        'label': 'Himalayas Global Remote Jobs',
        'handler': lambda q, loc, lim: HimalayasJobsConnector().search(q, location=loc, limit=lim),
    },
    'REMOTEOK': {
        'label': 'RemoteOK Worldwide Jobs',
        'handler': lambda q, loc, lim: RemoteOKJobsConnector().search(q, location=loc, limit=lim),
    },
}


def get_sourcing_connector(channel_key: str):
    return CONNECTOR_REGISTRY.get(channel_key)


def search_all_connectors(
    query: str,
    location: str = "Worldwide",
    limit_per_source: int = 10,
    source_key: str = None,
) -> list[dict]:
    """
    Executes search concurrently across registered channels (or a single requested source)
    and merges results with deduplication by normalized company domain.
    """
    combined_results = []
    seen_domains = set()

    if source_key and source_key in CONNECTOR_REGISTRY:
        connectors_to_run = {source_key: CONNECTOR_REGISTRY[source_key]}
    else:
        connectors_to_run = CONNECTOR_REGISTRY

    ordered_batches = {}
    if len(connectors_to_run) == 1:
        key, connector = next(iter(connectors_to_run.items()))
        try:
            ordered_batches[key] = connector['handler'](query, location, limit_per_source) or []
        except Exception:
            ordered_batches[key] = []
    else:
        with ThreadPoolExecutor(max_workers=min(8, len(connectors_to_run))) as pool:
            future_map = {
                pool.submit(connector['handler'], query, location, limit_per_source): key
                for key, connector in connectors_to_run.items()
            }
            for future in as_completed(future_map):
                key = future_map[future]
                try:
                    ordered_batches[key] = future.result() or []
                except Exception:
                    ordered_batches[key] = []

    for key in connectors_to_run:
        for item in ordered_batches.get(key, []):
            if not item.get('source'):
                item['source'] = key
            domain = (item.get('domain') or '').lower()
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                combined_results.append(item)
            elif not domain:
                combined_results.append(item)

    return combined_results
