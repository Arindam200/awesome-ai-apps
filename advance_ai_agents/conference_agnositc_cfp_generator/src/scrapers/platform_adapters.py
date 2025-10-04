"""
Platform-specific adapters for different conference systems
"""
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import json
import re

from abc import ABC, abstractmethod
from bs4 import BeautifulSoup
from datetime import datetime
import aiohttp
import asyncio
class BaseConferenceAdapter(ABC):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = None

    @abstractmethod
    async def extract_talk_urls(self) -> List[str]:
        """Extract all individual talk URLs"""
        pass

    @abstractmethod
    async def parse_talk_page(self, talk_url: str) -> Dict[str, Any]:
        """Parse individual talk page content"""
        pass

class SchedAdapter(BaseConferenceAdapter):
    """Adapter for Sched.com platforms (KubeCon, DockerCon, etc.)"""

    async def extract_talk_urls(self) -> List[str]:
        """Extract talk URLs from Sched.com"""

        # Try multiple Sched endpoints
        endpoints = [
            "/list/descriptions/",
            "/directory/",
            "/"
        ]

        all_urls = set()

        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    url = f"{self.base_url}{endpoint}"
                    async with session.get(url, timeout=15) as response:
                        if response.status == 200:
                            html = await response.text()
                            urls = self._extract_sched_urls(html)
                            all_urls.update(urls)

                            if len(urls) > 0:  # If we found URLs, prioritize this endpoint
                                break

                except Exception as e:
                    print(f"Error fetching {endpoint}: {str(e)}")
                    continue

        return list(all_urls)

    def _extract_sched_urls(self, html: str) -> List[str]:
        """Extract Sched event URLs from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        urls = set()

        # Look for event links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('event/') or '/event/' in href:
                if not href.startswith('http'):
                    full_url = f"{self.base_url}/{href.lstrip('/')}"
                else:
                    full_url = href
                urls.add(full_url)

        return list(urls)

    async def parse_talk_page(self, talk_url: str) -> Dict[str, Any]:
        """Parse Sched talk page"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(talk_url, timeout=10) as response:
                    if response.status != 200:
                        return self._empty_talk_data(talk_url)

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    return {
                        'title': self._extract_sched_title(soup),
                        'description': self._extract_sched_description(soup),
                        'speaker': self._extract_sched_speakers(soup),
                        'category': self._extract_sched_category(soup),
                        'time_slot': self._extract_sched_time(soup),
                        'room': self._extract_sched_room(soup),
                        'url': talk_url,
                        'platform': 'sched',
                        'crawled_at': datetime.utcnow().isoformat()
                    }

        except Exception as e:
            print(f"Error parsing Sched talk {talk_url}: {str(e)}")
            return self._empty_talk_data(talk_url)

    def _extract_sched_title(self, soup: BeautifulSoup) -> str:
        selectors = [
            'span.event a.name',
            'h1.event-title',
            '.event-name',
            'h1',
            '.session-title'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()

        return "Unknown Title"

    def _extract_sched_description(self, soup: BeautifulSoup) -> str:
        selectors = [
            '.tip-description',
            '.event-description',
            '.description',
            '.abstract'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()

        return "No description available"

    def _extract_sched_speakers(self, soup: BeautifulSoup) -> str:
        speakers = []

        # Try different speaker selectors
        speaker_selectors = [
            '.sched-event-details-roles h2 a',
            '.speaker-name',
            '.presenters a',
            '.event-speakers a'
        ]

        for selector in speaker_selectors:
            speaker_elems = soup.select(selector)
            for elem in speaker_elems:
                speaker_name = elem.get_text().strip()
                if speaker_name and speaker_name not in speakers:
                    speakers.append(speaker_name)

        return ' & '.join(speakers) if speakers else 'Unknown Speaker'

    def _extract_sched_category(self, soup: BeautifulSoup) -> str:
        selectors = [
            '.sched-event-type a',
            '.event-category',
            '.track',
            '.category'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()

        return "Uncategorized"

    def _extract_sched_time(self, soup: BeautifulSoup) -> str:
        selectors = [
            '.sched-event-details-timeandplace',
            '.event-time',
            '.time-slot'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                time_text = elem.get_text().split('\n')[0].strip()
                if time_text:
                    return time_text

        return "Unknown Time"

    def _extract_sched_room(self, soup: BeautifulSoup) -> str:
        selectors = [
            '.sched-event-details-timeandplace a',
            '.event-location',
            '.room'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()

        return "Unknown Room"

    def _empty_talk_data(self, url: str) -> Dict[str, Any]:
        return {
            'title': 'Failed to Parse',
            'description': 'Error occurred while parsing this talk',
            'speaker': 'Unknown',
            'category': 'Error',
            'time_slot': 'Unknown',
            'room': 'Unknown',
            'url': url,
            'platform': 'sched',
            'crawled_at': datetime.utcnow().isoformat()
        }

class SessionizeAdapter(BaseConferenceAdapter):
    """Adapter for Sessionize.com platforms"""

from typing import List, Union, Dict, Any

     async def extract_talk_urls(self) -> List[Union[str, Dict[str, Any]]]:
         """Extract talks from Sessionize API or web scraping"""

         # Try to find sessionize ID from URL
         sessionize_id = self._extract_sessionize_id()

         if sessionize_id:
             # Try API first
             talks_data = await self._fetch_from_api(sessionize_id)
             if talks_data:
                 return talks_data  # Return talk data directly for API

         # Fallback to web scraping
         return await self._scrape_sessionize_web()
    def _extract_sessionize_id(self) -> Optional[str]:
        """Extract Sessionize event ID from URL"""
        # Sessionize URLs often have format: https://sessionize.com/event-name/
        parsed = urlparse(self.base_url)
        path_parts = parsed.path.strip('/').split('/')

        if len(path_parts) > 0 and path_parts[0]:
            return path_parts[0]

        return None

    async def _fetch_from_api(self, sessionize_id: str) -> Optional[List[Dict]]:
        """Fetch from Sessionize public API"""

        api_url = f"https://sessionize.com/api/v2/{sessionize_id}/view/Sessions"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_sessionize_api_data(data)
        except Exception as e:
            print(f"Error fetching Sessionize API: {str(e)}")

        return None

    def _parse_sessionize_api_data(self, sessions_data: List[Dict]) -> List[Dict]:
        """Parse Sessionize API response into talk data"""
        talks = []

        for day in sessions_data:
            for room in day.get('rooms', []):
                for session in room.get('sessions', []):
                    if not session.get('isPlenumSession', False):  # Skip plenary sessions
                        talk_data = {
                            'title': session.get('title', 'Unknown Title'),
                            'description': session.get('description', 'No description available'),
                            'speaker': ' & '.join([s.get('name', '') for s in session.get('speakers', [])]),
                            'category': ', '.join([c.get('name', '') for c in session.get('categories', [])]),
                            'time_slot': f"{session.get('startsAt', '')} - {session.get('endsAt', '')}",
                            'room': room.get('name', 'Unknown Room'),
                            'url': f"{self.base_url}/session/{session.get('id', '')}",
                            'platform': 'sessionize',
                            'crawled_at': datetime.utcnow().isoformat()
                        }
                        talks.append(talk_data)

        return talks

    async def _scrape_sessionize_web(self) -> List[str]:
        """Fallback web scraping for Sessionize"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, timeout=15) as response:
                    if response.status != 200:
                        return []

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    urls = set()
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if '/session/' in href or 'session' in href.lower():
                            if not href.startswith('http'):
                                href = urljoin(self.base_url, href)
                            urls.add(href)

                    return list(urls)

        except Exception as e:
            print(f"Error scraping Sessionize: {str(e)}")
            return []

    async def parse_talk_page(self, talk_data: Any) -> Dict[str, Any]:
        """For Sessionize, data might already be parsed from API"""

        if isinstance(talk_data, dict) and 'platform' in talk_data:
            return talk_data  # Already parsed from API

        # If it's a URL, scrape it
        if isinstance(talk_data, str):
            return await self._scrape_sessionize_talk(talk_data)

        return self._empty_talk_data(str(talk_data))

    async def _scrape_sessionize_talk(self, talk_url: str) -> Dict[str, Any]:
        """Scrape individual Sessionize talk page"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(talk_url, timeout=10) as response:
                    if response.status != 200:
                        return self._empty_talk_data(talk_url)

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    return {
                        'title': self._extract_generic_title(soup),
                        'description': self._extract_generic_description(soup),
                        'speaker': self._extract_generic_speakers(soup),
                        'category': self._extract_generic_category(soup),
                        'time_slot': self._extract_generic_time(soup),
                        'room': self._extract_generic_room(soup),
                        'url': talk_url,
                        'platform': 'sessionize',
                        'crawled_at': datetime.utcnow().isoformat()
                    }

        except Exception as e:
            print(f"Error scraping Sessionize talk {talk_url}: {str(e)}")
            return self._empty_talk_data(talk_url)

    def _extract_generic_title(self, soup: BeautifulSoup) -> str:
        selectors = ['h1', '.session-title', '.title', 'h2']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()
        return "Unknown Title"

    def _extract_generic_description(self, soup: BeautifulSoup) -> str:
        selectors = ['.description', '.abstract', '.session-description', 'p']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and len(elem.get_text().strip()) > 50:  # Ensure substantial content
                return elem.get_text().strip()
        return "No description available"

    def _extract_generic_speakers(self, soup: BeautifulSoup) -> str:
        speakers = []
        selectors = ['.speaker', '.presenter', '.author']
        for selector in selectors:
            elems = soup.select(selector)
            for elem in elems:
                speaker = elem.get_text().strip()
                if speaker and speaker not in speakers:
                    speakers.append(speaker)
        return ' & '.join(speakers) if speakers else 'Unknown Speaker'

    def _extract_generic_category(self, soup: BeautifulSoup) -> str:
        selectors = ['.category', '.track', '.tag']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()
        return "Uncategorized"

    def _extract_generic_time(self, soup: BeautifulSoup) -> str:
        selectors = ['.time', '.schedule', '.when']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()
        return "Unknown Time"

    def _extract_generic_room(self, soup: BeautifulSoup) -> str:
        selectors = ['.room', '.location', '.where']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()
        return "Unknown Room"

    def _empty_talk_data(self, url: str) -> Dict[str, Any]:
        return {
            'title': 'Failed to Parse',
            'description': 'Error occurred while parsing this talk',
            'speaker': 'Unknown',
            'category': 'Error',
            'time_slot': 'Unknown',
            'room': 'Unknown',
            'url': url,
            'platform': 'sessionize',
            'crawled_at': datetime.utcnow().isoformat()
        }

class GenericAdapter(BaseConferenceAdapter):
    """Generic adapter for unknown platforms using heuristic parsing"""

    async def extract_talk_urls(self) -> List[str]:
        """Heuristic URL extraction for unknown platforms"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, timeout=15) as response:
                    if response.status != 200:
                        return []

                    html = await response.text()
                    return self._heuristic_link_extraction(html)

        except Exception as e:
            print(f"Error extracting URLs from generic platform: {str(e)}")
            return []

    def _heuristic_link_extraction(self, html: str) -> List[str]:
        """Extract potential talk links using heuristics"""

        soup = BeautifulSoup(html, 'html.parser')
        potential_urls = set()

        # Keywords that suggest talk/session content
        talk_keywords = [
            'session', 'talk', 'presentation', 'speaker', 'agenda',
            'schedule', 'program', 'workshop', 'keynote', 'panel'
        ]

        for link in soup.find_all('a', href=True):
            href = link['href']
            link_text = link.get_text().lower().strip()

            # Skip obviously non-talk links
            if any(skip in href.lower() for skip in ['mailto:', 'tel:', 'javascript:', '#']):
                continue

            # Check if URL or text suggests it's a talk
            is_talk_link = (
                any(keyword in href.lower() for keyword in talk_keywords) or
                any(keyword in link_text for keyword in talk_keywords) or
                (len(link_text) > 20 and len(link_text) < 200)  # Reasonable title length
            )

            if is_talk_link:
                if not href.startswith('http'):
                    href = urljoin(self.base_url, href)
                potential_urls.add(href)

        return list(potential_urls)

    async def parse_talk_page(self, talk_url: str) -> Dict[str, Any]:
        """Generic talk page parsing"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(talk_url, timeout=10) as response:
                    if response.status != 200:
                        return self._empty_talk_data(talk_url)

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    return {
                        'title': self._extract_generic_title(soup),
                        'description': self._extract_generic_description(soup),
                        'speaker': self._extract_generic_speakers(soup),
                        'category': self._extract_generic_category(soup),
                        'time_slot': self._extract_generic_time(soup),
                        'room': self._extract_generic_room(soup),
                        'url': talk_url,
                        'platform': 'generic',
                        'crawled_at': datetime.utcnow().isoformat()
                    }

        except Exception as e:
            print(f"Error parsing generic talk {talk_url}: {str(e)}")
            return self._empty_talk_data(talk_url)

    def _extract_generic_title(self, soup: BeautifulSoup) -> str:
        # Try multiple title extraction strategies
        selectors = [
            'h1', 'h2', '.title', '.session-title', '.talk-title',
            '.event-title', '.presentation-title'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text().strip():
                title = elem.get_text().strip()
                if 5 < len(title) < 200:  # Reasonable title length
                    return title

        # Fallback to page title
        title_elem = soup.find('title')
        if title_elem:
            return title_elem.get_text().strip()

        return "Unknown Title"

    def _extract_generic_description(self, soup: BeautifulSoup) -> str:
        selectors = [
            '.description', '.abstract', '.summary', '.content',
            '.talk-description', '.session-description'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and len(elem.get_text().strip()) > 50:
                return elem.get_text().strip()

        # Fallback: look for longest paragraph
        paragraphs = soup.find_all('p')
        longest_p = max(paragraphs, key=lambda p: len(p.get_text()), default=None)
        if longest_p and len(longest_p.get_text().strip()) > 50:
            return longest_p.get_text().strip()

        return "No description available"

    def _extract_generic_speakers(self, soup: BeautifulSoup) -> str:
        speakers = []
        selectors = [
            '.speaker', '.presenter', '.author', '.speaker-name'
        ]

        for selector in selectors:
            elems = soup.select(selector)
            for elem in elems:
                speaker = elem.get_text().strip()
                if speaker and len(speaker) < 100 and speaker not in speakers:
                    speakers.append(speaker)

        return ' & '.join(speakers) if speakers else 'Unknown Speaker'

    def _extract_generic_category(self, soup: BeautifulSoup) -> str:
        selectors = ['.category', '.track', '.tag', '.topic']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()
        return "Uncategorized"

    def _extract_generic_time(self, soup: BeautifulSoup) -> str:
        selectors = ['.time', '.schedule', '.when', '.datetime']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()
        return "Unknown Time"

    def _extract_generic_room(self, soup: BeautifulSoup) -> str:
        selectors = ['.room', '.location', '.venue', '.where']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()
        return "Unknown Room"

    def _empty_talk_data(self, url: str) -> Dict[str, Any]:
        return {
            'title': 'Failed to Parse',
            'description': 'Error occurred while parsing this talk',
            'speaker': 'Unknown',
            'category': 'Error',
            'time_slot': 'Unknown',
            'room': 'Unknown',
            'url': url,
            'platform': 'generic',
            'crawled_at': datetime.utcnow().isoformat()
        }

def get_platform_adapter(platform: str, base_url: str) -> BaseConferenceAdapter:
    """Factory function to get the appropriate adapter"""

    adapters = {
        'sched': SchedAdapter,
        'sessionize': SessionizeAdapter,
        'generic': GenericAdapter
    }

    adapter_class = adapters.get(platform, GenericAdapter)
    return adapter_class(base_url)