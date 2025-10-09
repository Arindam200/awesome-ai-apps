"""
Conference platform detection and metadata extraction
"""
from typing import Dict, Any
from urllib.parse import urlparse, urljoin
import re

from bs4 import BeautifulSoup
import aiohttp
class ConferenceDetector:

    PLATFORM_SIGNATURES = {
        'sched': {
            'domains': ['sched.com'],
            'url_patterns': ['/event/', '/list/'],
            'html_signatures': ['sched-event-details', 'eventdetails', 'sched-container']
        },
        'sessionize': {
            'domains': ['sessionize.com'],
            'url_patterns': ['/view/', '/session/'],
            'api_patterns': ['/api/v2/']
        },
        'whova': {
            'domains': ['whova.com'],
            'url_patterns': ['/agenda/', '/session/'],
            'html_signatures': ['whova-agenda', 'session-detail']
        }
    }

    async def detect_platform(self, url: str) -> str:
        """Auto-detect conference platform"""

        # Step 1: Domain-based detection
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        # Normalize to strip leading 'www.'
        if host.startswith("www."):
            host = host[4:]
        for platform, signatures in self.PLATFORM_SIGNATURES.items():
            if any(host == d or host.endswith(f".{d}") for d in signatures["domains"]):
                return platform
        # Step 2: HTML structure analysis for unknown domains
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()

                        for platform, signatures in self.PLATFORM_SIGNATURES.items():
                            if any(sig in html.lower() for sig in signatures.get('html_signatures', [])):
                                return platform
        except Exception as e:
            print(f"Error detecting platform for {url}: {str(e)}")

        return 'generic'  # Fallback to generic parser

    async def extract_conference_info(self, url: str, platform: str) -> Dict[str, Any]:
        """Extract conference metadata"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        return self._default_conference_info(url)

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Extract title from various sources
                    title = self._extract_title(soup, url)

                    # Extract year from URL or content
                    year = self._extract_year(url, soup)

                    # Generate conference ID
                    conf_id = self._generate_conference_id(title, year)

                    return {
                        'id': conf_id,
                        'name': title,
                        'year': year,
                        'platform': platform,
                        'base_url': url,
                        'domain': urlparse(url).netloc
                    }

        except Exception as e:
            print(f"Error extracting conference info: {str(e)}")
            return self._default_conference_info(url)

    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        """Extract conference title from various sources"""

        # Try different title sources
        title_sources = [
            soup.find('title'),
            soup.find('h1'),
            soup.find('meta', {'property': 'og:title'}),
            soup.find('meta', {'name': 'title'})
        ]

        for source in title_sources:
            if source:
                if source.name == 'meta':
                    title = source.get('content', '').strip()
                else:
                    title = source.get_text().strip()

                if title and len(title) > 3:
                    # Clean up common suffixes
                    title = re.sub(r'\s*-\s*(Schedule|Agenda|Program).*$', '', title, flags=re.IGNORECASE)
                    return title[:100]  # Limit length

        # Fallback: extract from URL
        parsed = urlparse(url)
        domain_parts = parsed.netloc.split('.')
        if len(domain_parts) > 0:
            return domain_parts[0].title().replace('-', ' ')

        return 'Unknown Conference'

    def _extract_year(self, url: str, soup: BeautifulSoup) -> str:
        """Extract year from URL or content"""

        # Try to find year in URL
        year_match = re.search(r'20\d{2}', url)
        if year_match:
            return year_match.group()

        # Try to find year in page content
        text_content = soup.get_text()
        year_matches = re.findall(r'20\d{2}', text_content)
        if year_matches:
            # Return the most recent year found
            return max(year_matches)

        # Default to current year
        from datetime import datetime
        return str(datetime.now().year)

    def _generate_conference_id(self, title: str, year: str) -> str:
        """Generate a clean conference ID"""

        # Clean title for ID
        clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', title.lower())
        clean_title = re.sub(r'\s+', '_', clean_title.strip())

        # Limit length and add year
        if len(clean_title) > 30:
            clean_title = clean_title[:30]

        return f"{clean_title}_{year}"

    def _default_conference_info(self, url: str) -> Dict[str, Any]:
        """Return default conference info when extraction fails"""

        from datetime import datetime
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')

        return {
            'id': f"conference_{domain.replace('.', '_')}_{datetime.now().year}",
            'name': f"Conference from {domain}",
            'year': str(datetime.now().year),
            'platform': 'generic',
            'base_url': url,
            'domain': parsed.netloc
        }