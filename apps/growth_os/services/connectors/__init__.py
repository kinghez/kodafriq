"""
GrowthOS Multi-Source Worldwide Sourcing Connectors Package
Provides structured search integrations across Web Search, LinkedIn, Indeed,
and live worldwide open job boards (Remotive, Arbeitnow, Jobicy, Himalayas, RemoteOK).
"""
from .base import (
    BaseSourcingConnector,
    classify_industry_vertical,
    infer_country_from_location,
    is_worldwide_location,
)
from .linkedin_connector import LinkedInJobsConnector
from .indeed_connector import IndeedJobsConnector
from .global_boards_connector import (
    RemotiveJobsConnector,
    ArbeitnowJobsConnector,
    JobicyJobsConnector,
    HimalayasJobsConnector,
    RemoteOKJobsConnector,
)
from .registry import get_sourcing_connector, search_all_connectors, CONNECTOR_REGISTRY

__all__ = [
    'BaseSourcingConnector',
    'LinkedInJobsConnector',
    'IndeedJobsConnector',
    'RemotiveJobsConnector',
    'ArbeitnowJobsConnector',
    'JobicyJobsConnector',
    'HimalayasJobsConnector',
    'RemoteOKJobsConnector',
    'get_sourcing_connector',
    'search_all_connectors',
    'CONNECTOR_REGISTRY',
    'classify_industry_vertical',
    'infer_country_from_location',
    'is_worldwide_location',
]
