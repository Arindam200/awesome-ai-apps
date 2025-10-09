"""
Parallel conference crawler with rate limiting and batch processing
"""
from typing import List, Dict, Any, Optional

from datetime import datetime
import aiohttp
import asyncio
import time

from .conference_detector import ConferenceDetector
from .platform_adapters import get_platform_adapter
class ParallelConferenceCrawler:
    def __init__(self, batch_size: int = 10, rate_limit_delay: float = 1.0):
        self.batch_size = batch_size
        self.rate_limit_delay = rate_limit_delay
        self.detector = ConferenceDetector()
        self.stats = {
            'total_urls': 0,
            'successful_crawls': 0,
            'failed_crawls': 0,
            'start_time': None,
            'end_time': None
        }

    async def crawl_conference(self, conference_url: str) -> Dict[str, Any]:
        """Complete conference crawling pipeline"""

        self.stats['start_time'] = datetime.utcnow()
        print(f"🚀 Starting conference crawl for: {conference_url}")

        try:
            # Step 1: Detect platform and extract metadata
            print("📡 Detecting conference platform...")
            platform = await self.detector.detect_platform(conference_url)
            conf_info = await self.detector.extract_conference_info(conference_url, platform)

            print(f"✅ Detected platform: {platform}")
            print(f"📋 Conference: {conf_info['name']} ({conf_info['year']})")

            # Step 2: Get appropriate adapter
            print(f"🔧 Initializing {platform} adapter...")
            adapter = get_platform_adapter(platform, conference_url)

            # Step 3: Extract talk URLs or data
            print("🔍 Extracting talk URLs...")
            talk_data = await adapter.extract_talk_urls()

            if not talk_data:
                print("❌ No talks found!")
                return {
                    'conference': conf_info,
                    'talks': [],
                    'stats': self._finalize_stats(),
                    'success': False,
                    'error': 'No talks extracted'
                }

            self.stats['total_urls'] = len(talk_data)
            print(f"📊 Found {len(talk_data)} talks to process")

            # Step 4: Parse talk content
            print("⚡ Starting parallel talk parsing...")
            talks = await self._parse_talks_parallel(adapter, talk_data)

            # Step 5: Filter successful talks
            successful_talks = [talk for talk in talks if talk.get('title') != 'Failed to Parse']
            self.stats['successful_crawls'] = len(successful_talks)
            self.stats['failed_crawls'] = len(talks) - len(successful_talks)

            print(f"✅ Successfully parsed {self.stats['successful_crawls']} talks")
            print(f"❌ Failed to parse {self.stats['failed_crawls']} talks")

            return {
                'conference': conf_info,
                'talks': successful_talks,
                'stats': self._finalize_stats(),
                'success': True
            }

        except Exception as e:
            print(f"❌ Critical error during crawling: {str(e)}")
            return {
                'conference': conf_info if 'conf_info' in locals() else {'id': 'error', 'name': 'Error'},
                'talks': [],
                'stats': self._finalize_stats(),
                'success': False,
                'error': str(e)
            }

    async def _parse_talks_parallel(self, adapter, talk_data: List) -> List[Dict[str, Any]]:
        """Parse talks in parallel batches with rate limiting"""

        all_talks = []

        # Handle different data types (URLs vs pre-parsed data)
        if isinstance(talk_data[0], dict) and 'platform' in talk_data[0]:
            # Sessionize API data - already parsed
            return talk_data

        # URLs - need to parse
        talk_urls = talk_data if isinstance(talk_data[0], str) else talk_data

        for i in range(0, len(talk_urls), self.batch_size):
            batch = talk_urls[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(talk_urls) + self.batch_size - 1) // self.batch_size

            print(f"🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} talks)")

            # Process batch in parallel
            tasks = [self._parse_single_talk(adapter, talk_url) for talk_url in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle results and exceptions
            for result in batch_results:
                if isinstance(result, Exception):
                    print(f"⚠️  Exception in batch: {str(result)}")
                    all_talks.append(self._error_talk_data(str(result)))
                else:
                    all_talks.append(result)

            # Rate limiting between batches
            if i + self.batch_size < len(talk_urls):
                print(f"⏳ Rate limiting... waiting {self.rate_limit_delay}s")
                await asyncio.sleep(self.rate_limit_delay)

        return all_talks

    async def _parse_single_talk(self, adapter, talk_url: str) -> Dict[str, Any]:
        """Parse a single talk with timeout and error handling"""

        try:
            # Add timeout wrapper
            return await asyncio.wait_for(
                adapter.parse_talk_page(talk_url),
                timeout=15.0
            )
        except asyncio.TimeoutError:
            print(f"⏰ Timeout parsing: {talk_url}")
            return self._error_talk_data(talk_url, "Timeout")
        except Exception as e:
            print(f"❌ Error parsing {talk_url}: {str(e)}")
            return self._error_talk_data(talk_url, str(e))

    def _error_talk_data(self, url: str, error: str = "Unknown error") -> Dict[str, Any]:
        """Generate error talk data structure"""
        return {
            'title': 'Failed to Parse',
            'description': f'Error: {error}',
            'speaker': 'Unknown',
            'category': 'Error',
            'time_slot': 'Unknown',
            'room': 'Unknown',
            'url': url,
            'platform': 'error',
            'crawled_at': datetime.utcnow().isoformat()
        }

    def _finalize_stats(self) -> Dict[str, Any]:
        """Finalize crawling statistics"""
        self.stats['end_time'] = datetime.utcnow()

        if self.stats['start_time']:
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            self.stats['duration_seconds'] = duration
            self.stats['talks_per_second'] = self.stats['successful_crawls'] / duration if duration > 0 else 0

        return self.stats.copy()

    def print_summary(self, result: Dict[str, Any]):
        """Print a nice summary of crawling results"""

        print("\n" + "="*60)
        print("📊 CRAWLING SUMMARY")
        print("="*60)

        conf = result['conference']
        stats = result['stats']

        print(f"🏢 Conference: {conf['name']}")
        print(f"📅 Year: {conf['year']}")
        print(f"🔧 Platform: {conf['platform']}")
        print(f"🌐 URL: {conf['base_url']}")
        print()

        print(f"📈 Total URLs Found: {stats['total_urls']}")
        print(f"✅ Successfully Parsed: {stats['successful_crawls']}")
        print(f"❌ Failed to Parse: {stats['failed_crawls']}")

        if stats.get('duration_seconds'):
            print(f"⏱️  Duration: {stats['duration_seconds']:.1f} seconds")
            print(f"🚀 Speed: {stats['talks_per_second']:.2f} talks/second")

        success_rate = (stats['successful_crawls'] / stats['total_urls'] * 100) if stats['total_urls'] > 0 else 0
        print(f"📊 Success Rate: {success_rate:.1f}%")

        print("="*60)

        if not result['success']:
            print(f"❌ ERROR: {result.get('error', 'Unknown error')}")

        print()

# Convenience function for single conference crawling
async def crawl_single_conference(
    conference_url: str,
    batch_size: int = 10,
    rate_limit_delay: float = 1.0,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Crawl a single conference with default settings

    Args:
        conference_url: URL of the conference schedule
        batch_size: Number of talks to process in parallel
        rate_limit_delay: Delay between batches in seconds
        verbose: Whether to print detailed progress

    Returns:
        Dictionary with conference info, talks, and stats
    """

    crawler = ParallelConferenceCrawler(batch_size, rate_limit_delay)
    result = await crawler.crawl_conference(conference_url)

    if verbose:
        crawler.print_summary(result)

    return result

# CLI interface for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m scrapers.parallel_crawler <conference_url>")
        sys.exit(1)

    conference_url = sys.argv[1]

    async def main():
        result = await crawl_single_conference(conference_url)

        # Save results to file
        import json
        filename = f"crawl_results_{result['conference']['id']}.json"
        with open(filename, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"💾 Results saved to: {filename}")

    asyncio.run(main())