"""
Exa AI Search MCP Server

This server provides access to the Exa AI Search API through the Model Context Protocol (MCP).
It exposes tools for intelligent web search using Exa's neural and keyword search capabilities.

Features:
- Neural and keyword search types
- Content retrieval with highlights and summaries
- Category-specific searches
- Date filtering
- Domain inclusion/exclusion
- Text filtering
- Comprehensive error handling
"""

from typing import Optional, Literal, List, Dict, Any
import httpx
import logging
import os

from datetime import datetime
from enum import Enum
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP(
    name="exa-search-server",
    instructions="A Model Context Protocol server for accessing Exa AI Search API. Provides intelligent web search with neural and keyword capabilities."
)

# Supported search types
SEARCH_TYPES = ["neural", "keyword", "auto", "fast"]

# Supported categories
CATEGORIES = [
    "company", "research paper", "news", "pdf", "github",
    "tweet", "personal site", "linkedin profile", "financial report"
]

class ExaSearchResult(BaseModel):
    """Represents a single search result from Exa"""
    title: str
    url: str
    id: str
    publishedDate: Optional[str] = None
    author: Optional[str] = None
    image: Optional[str] = None
    favicon: Optional[str] = None
    text: Optional[str] = None
    highlights: Optional[List[str]] = None
    highlightScores: Optional[List[float]] = None
    summary: Optional[str] = None

class ExaSearchResponse(BaseModel):
    """Represents an Exa search API response"""
    requestId: str
    resolvedSearchType: str
    results: List[ExaSearchResult]
    searchType: Optional[str] = None
    context: Optional[str] = None
    costDollars: Optional[Dict[str, Any]] = None

def get_api_key() -> str:
    """Get the Exa API key from environment variables"""
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        raise ValueError(
            "EXA_API_KEY environment variable is required. "
            "Get your API key from https://exa.ai/"
        )
    return api_key

async def make_exa_request(endpoint: str, payload: dict) -> dict:
    """Make a request to the Exa API"""
    api_key = get_api_key()

    # Base URL for Exa API
    base_url = "https://api.exa.ai"
    url = f"{base_url}/{endpoint}"

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Making request to {endpoint} with payload: {payload}")
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Successfully retrieved {len(data.get('results', []))} results")
                return data
            else:
                error_msg = f"Exa API error: {response.status_code}"
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg += f" - {error_data['error']}"
                    elif "message" in error_data:
                        error_msg += f" - {error_data['message']}"
                except:
                    error_msg += f" - {response.text}"

                logger.error(error_msg)
                raise Exception(error_msg)

    except httpx.RequestError as e:
        error_msg = f"Network error connecting to Exa API: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)

@mcp.tool()
async def exa_search(
    query: str = Field(description="The search query string"),
    search_type: Optional[Literal["neural", "keyword", "auto", "fast"]] = Field(
        default="auto",
        description="Type of search: 'neural' (embeddings-based), 'keyword' (traditional), 'auto' (intelligent mix), 'fast' (streamlined)"
    ),
    category: Optional[Literal["company", "research paper", "news", "pdf", "github", "tweet", "personal site", "linkedin profile", "financial report"]] = Field(
        default=None,
        description="Data category to focus on"
    ),
    num_results: Optional[int] = Field(
        default=10,
        description="Number of results to return (up to 100)"
    ),
    include_domains: Optional[List[str]] = Field(
        default=None,
        description="List of domains to include (e.g., ['arxiv.org', 'github.com'])"
    ),
    exclude_domains: Optional[List[str]] = Field(
        default=None,
        description="List of domains to exclude from results"
    ),
    start_crawl_date: Optional[str] = Field(
        default=None,
        description="Include links crawled after this date (ISO 8601 format)"
    ),
    end_crawl_date: Optional[str] = Field(
        default=None,
        description="Include links crawled before this date (ISO 8601 format)"
    ),
    start_published_date: Optional[str] = Field(
        default=None,
        description="Include links published after this date (ISO 8601 format)"
    ),
    end_published_date: Optional[str] = Field(
        default=None,
        description="Include links published before this date (ISO 8601 format)"
    ),
    include_text: Optional[List[str]] = Field(
        default=None,
        description="List of strings that must be present in webpage text (max 1 string, up to 5 words)"
    ),
    exclude_text: Optional[List[str]] = Field(
        default=None,
        description="List of strings that must not be present in webpage text (max 1 string, up to 5 words)"
    ),
    include_content: Optional[bool] = Field(
        default=True,
        description="Include webpage text content in results"
    ),
    include_highlights: Optional[bool] = Field(
        default=True,
        description="Include highlights of relevant text passages"
    ),
    include_summary: Optional[bool] = Field(
        default=True,
        description="Include AI-generated summaries of the content"
    ),
    user_location: Optional[str] = Field(
        default=None,
        description="Two-letter ISO country code of the user (e.g., 'US')"
    ),
    use_context: Optional[bool] = Field(
        default=False,
        description="Format results as context string ready for LLMs"
    )
) -> dict:
    """
    Search the web using Exa AI's intelligent search capabilities.

    This tool provides access to Exa's neural and keyword search engines,
    which can find relevant content based on meaning rather than just keywords.

    Search Types:
    - neural: Uses embeddings to find semantically similar content
    - keyword: Traditional Google-like search
    - auto: Intelligently combines neural and keyword search
    - fast: Streamlined versions of neural and keyword models

    The tool supports various filtering options including domains, dates,
    content types, and text requirements. Results can include full content,
    highlights, and AI-generated summaries.
    """

    # Validate parameters
    if search_type and search_type not in SEARCH_TYPES:
        raise ValueError(f"Unsupported search type '{search_type}'. Supported types: {', '.join(SEARCH_TYPES)}")

    if category and category not in CATEGORIES:
        raise ValueError(f"Unsupported category '{category}'. Supported categories: {', '.join(CATEGORIES)}")

    if num_results and (num_results < 1 or num_results > 100):
        raise ValueError("Number of results must be between 1 and 100")

    if include_text and len(include_text) > 1:
        raise ValueError("Only 1 string is supported for include_text, up to 5 words")

    if exclude_text and len(exclude_text) > 1:
        raise ValueError("Only 1 string is supported for exclude_text, up to 5 words")

    # Build request payload
    payload = {
        "query": query,
        "type": search_type,
        "numResults": num_results
    }

    # Add optional parameters
    if category:
        payload["category"] = category
    if include_domains:
        payload["includeDomains"] = include_domains
    if exclude_domains:
        payload["excludeDomains"] = exclude_domains
    if start_crawl_date:
        payload["startCrawlDate"] = start_crawl_date
    if end_crawl_date:
        payload["endCrawlDate"] = end_crawl_date
    if start_published_date:
        payload["startPublishedDate"] = start_published_date
    if end_published_date:
        payload["endPublishedDate"] = end_published_date
    if include_text:
        payload["includeText"] = include_text
    if exclude_text:
        payload["excludeText"] = exclude_text
    if user_location:
        payload["userLocation"] = user_location
    if use_context:
        payload["context"] = True

    # Handle content options
    contents = {}
    if include_content:
        contents["text"] = True
    if include_highlights:
        contents["highlights"] = True
    if include_summary:
        contents["summary"] = True

    if contents:
        payload["contents"] = contents

    try:
        result = await make_exa_request("search", payload)
        return {
            "success": True,
            "query": query,
            "search_type": search_type,
            "resolved_search_type": result.get("resolvedSearchType"),
            "request_id": result.get("requestId"),
            "num_results": len(result.get("results", [])),
            "results": result.get("results", []),
            "context": result.get("context"),
            "cost_dollars": result.get("costDollars"),
            "parameters_used": payload
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "search_type": search_type,
            "parameters_used": payload
        }

@mcp.tool()
async def exa_get_contents(
    ids: List[str] = Field(description="List of Exa result IDs to get content for"),
    include_text: Optional[bool] = Field(default=True, description="Include webpage text content"),
    include_highlights: Optional[bool] = Field(default=True, description="Include highlights of relevant passages"),
    include_summary: Optional[bool] = Field(default=True, description="Include AI-generated summaries"),
    livecrawl: Optional[bool] = Field(default=False, description="Use live crawling for the most up-to-date content")
) -> dict:
    """
    Retrieve full content for specific Exa search results.

    This tool allows you to get detailed content for specific search results
    identified by their Exa IDs. You can control what type of content to include
    and whether to use live crawling for the most current information.

    The IDs can be obtained from previous search results and are used to fetch
    the complete content, highlights, and summaries for those specific pages.
    """

    if not ids:
        raise ValueError("At least one ID must be provided")

    # Build request payload
    payload = {
        "ids": ids
    }

    # Handle content options
    contents = {}
    if include_text:
        contents["text"] = True
    if include_highlights:
        contents["highlights"] = True
    if include_summary:
        contents["summary"] = True
    if livecrawl:
        contents["livecrawl"] = True

    if contents:
        payload["contents"] = contents

    try:
        result = await make_exa_request("contents", payload)
        return {
            "success": True,
            "request_id": result.get("requestId"),
            "num_results": len(result.get("results", [])),
            "results": result.get("results", []),
            "cost_dollars": result.get("costDollars"),
            "parameters_used": payload
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "ids": ids,
            "parameters_used": payload
        }

@mcp.tool()
async def exa_find_similar(
    url: str = Field(description="URL to find similar links to"),
    num_results: Optional[int] = Field(default=10, description="Number of similar results to return (up to 100)"),
    include_domains: Optional[List[str]] = Field(default=None, description="List of domains to include"),
    exclude_domains: Optional[List[str]] = Field(default=None, description="List of domains to exclude"),
    start_crawl_date: Optional[str] = Field(default=None, description="Include links crawled after this date (ISO 8601)"),
    end_crawl_date: Optional[str] = Field(default=None, description="Include links crawled before this date (ISO 8601)"),
    start_published_date: Optional[str] = Field(default=None, description="Include links published after this date (ISO 8601)"),
    end_published_date: Optional[str] = Field(default=None, description="Include links published before this date (ISO 8601)"),
    include_content: Optional[bool] = Field(default=True, description="Include webpage text content"),
    include_highlights: Optional[bool] = Field(default=True, description="Include highlights"),
    include_summary: Optional[bool] = Field(default=True, description="Include AI summaries")
) -> dict:
    """
    Find links similar to a given URL using Exa's similarity search.

    This tool finds web pages that are semantically similar to the provided URL.
    It's useful for discovering related content, research papers, or similar
    resources based on the content and topic of the reference URL.

    The similarity is determined by Exa's neural understanding of content,
    not just keyword matching, making it effective for finding truly related
    content even when the exact terms differ.
    """

    if not url:
        raise ValueError("URL parameter is required")

    if num_results and (num_results < 1 or num_results > 100):
        raise ValueError("Number of results must be between 1 and 100")

    # Build request payload
    payload = {
        "url": url,
        "numResults": num_results
    }

    # Add optional parameters
    if include_domains:
        payload["includeDomains"] = include_domains
    if exclude_domains:
        payload["excludeDomains"] = exclude_domains
    if start_crawl_date:
        payload["startCrawlDate"] = start_crawl_date
    if end_crawl_date:
        payload["endCrawlDate"] = end_crawl_date
    if start_published_date:
        payload["startPublishedDate"] = start_published_date
    if end_published_date:
        payload["endPublishedDate"] = end_published_date

    # Handle content options
    contents = {}
    if include_content:
        contents["text"] = True
    if include_highlights:
        contents["highlights"] = True
    if include_summary:
        contents["summary"] = True

    if contents:
        payload["contents"] = contents

    try:
        result = await make_exa_request("findSimilar", payload)
        return {
            "success": True,
            "reference_url": url,
            "request_id": result.get("requestId"),
            "num_results": len(result.get("results", [])),
            "results": result.get("results", []),
            "cost_dollars": result.get("costDollars"),
            "parameters_used": payload
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "reference_url": url,
            "parameters_used": payload
        }