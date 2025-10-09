"""
Web scraping module for conference data extraction
"""

from .conference_detector import ConferenceDetector
from .platform_adapters import (
    BaseConferenceAdapter,
    SchedAdapter,
    SessionizeAdapter,
    GenericAdapter,
    get_platform_adapter
)
from .parallel_crawler import ParallelConferenceCrawler, crawl_single_conference

__all__ = [
    'ConferenceDetector',
    'BaseConferenceAdapter',
    'SchedAdapter',
    'SessionizeAdapter',
    'GenericAdapter',
    'get_platform_adapter',
    'ParallelConferenceCrawler',
    'crawl_single_conference'
]