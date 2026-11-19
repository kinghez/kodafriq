"""
GrowthOS Multi-Source Sourcing Connectors Package
Provides structured search integrations across Google Search, LinkedIn Jobs, and Indeed.
"""
from .base import BaseSourcingConnector
from .linkedin_connector import LinkedInJobsConnector
from .indeed_connector import IndeedJobsConnector
from .registry import get_sourcing_connector, search_all_connectors, CONNECTOR_REGISTRY

__all__ = [
    'BaseSourcingConnector',
    'LinkedInJobsConnector',
    'IndeedJobsConnector',
    'get_sourcing_connector',
    'search_all_connectors',
    'CONNECTOR_REGISTRY',
]

