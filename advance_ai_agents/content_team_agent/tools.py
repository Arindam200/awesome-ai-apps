from serpapi import GoogleSearch
import os
from dotenv import load_dotenv
from typing import Dict, List, Optional
import trafilatura
import httpx
load_dotenv()

def google_ai_mode_search(query: str) -> dict:
    """Search Google AI Mode for a query and return results."""
    params = {
        "engine": "google_ai_mode",
        "q": query,
        "api_key": os.getenv("SERPAPI_API_KEY"),
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    return results


def google_ai_overview_search(query: str) -> dict:
    """Search Google AI Overview for a query and return results."""
    params = {
        "engine": "google_ai_overview",
        "q": query,
        "api_key": os.getenv("SERPAPI_API_KEY"),
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    return results

def extract_text_from_url(url: str) -> str:
    """
    Extract readable article text from a URL.

    Args:
        url: The URL to extract content from

    Returns:
        Extracted article text, or empty string if extraction fails
    """
    try:
        # First, try using trafilatura with custom headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # Try fetching with httpx first for better control
        try:
            with httpx.Client(
                timeout=30.0, headers=headers, follow_redirects=True
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                html_content = response.text
        except Exception as http_error:
            print(f"HTTP error fetching URL {url}: {http_error}")
            # Fallback to trafilatura's fetch_url
            html_content = trafilatura.fetch_url(url, no_ssl=True)
            if not html_content:
                return ""

        if html_content:
            # Extract text using trafilatura
            text = trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=True,
                include_links=False,
                include_images=False,
            )
            if text and len(text.strip()) > 100:  # Ensure we got meaningful content
                return text.strip()
            else:
                print(f"Warning: Extracted text too short or empty from {url}")
                return ""
        else:
            print(f"Warning: Failed to fetch HTML content from {url}")
            return ""

    except Exception as e:
        print(f"Error extracting text from URL {url}: {e}")
        import traceback

        traceback.print_exc()
        return ""
