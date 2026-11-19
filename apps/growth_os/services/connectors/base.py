"""
Base Sourcing Connector Class for GrowthOS.
"""
from abc import ABC, abstractmethod
from apps.growth_os.models import normalize_company_domain


class BaseSourcingConnector(ABC):
    """
    Standard interface for all prospective employer sourcing connectors.
    """
    source_identifier = 'BASE'
    source_label = 'Base Sourcing Connector'

    @abstractmethod
    def search(self, query: str, location: str = "United States", limit: int = 15) -> list[dict]:
        """
        Executes a search query against the channel and returns a list of normalized lead dicts:
        [{
            'company_name': str,
            'domain': str,
            'website': str,
            'careers_url': str,
            'city': str,
            'country': str,
            'industry_vertical': str,
            'company_size': str,
            'snippet': str,
            'source': str
        }, ...]
        """
        pass

    def normalize_lead(self, raw: dict) -> dict:
        """Ensures every result adheres to the standard GrowthOS lead schema."""
        website = raw.get('website', '').strip()
        domain = raw.get('domain', '').strip()
        if not domain and website:
            domain = normalize_company_domain(website)

        return {
            'company_name': raw.get('company_name', '').strip(),
            'domain': domain,
            'website': website,
            'careers_url': raw.get('careers_url', '').strip(),
            'city': raw.get('city', '').strip(),
            'country': raw.get('country', 'United States').strip(),
            'industry_vertical': raw.get('industry_vertical', 'RCM_SERVICES'),
            'company_size': raw.get('company_size', '11_50'),
            'snippet': raw.get('snippet', '').strip(),
            'source': self.source_identifier
        }

