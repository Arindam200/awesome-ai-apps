"""Exa connector: semantic web search for blog posts, newsletters, and recaps
mentioning the project — the venues HN Algolia and Reddit can't see.

Optional: silently no-ops without EXA_API_KEY. Capped at 10 queries/run so a
free project costs cents.
"""

import logging
from datetime import datetime
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.connectors.base import RawItem

logger = logging.getLogger(__name__)

API = "https://api.exa.ai/search"
MAX_QUERIES = 10
# Covered by dedicated connectors / the repo-state engine — exclude to avoid dupes.
EXCLUDE_DOMAINS = ["github.com", "reddit.com", "news.ycombinator.com"]


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch(project_config: dict, since: datetime) -> list[RawItem]:
    if not settings.exa_api_key:
        return []

    # Keywords already carry the project name for real configs; honor an
    # optional dedicated list too.
    community = project_config.get("community") or {}
    keywords = project_config.get("keywords") or []
    queries = (community.get("web_queries") or keywords)[:MAX_QUERIES]
    # The project's own site isn't a "mention around the web". By convention the
    # first keyword is the project name → meshery excludes meshery.io etc.
    self_hints = [k.lower().replace(" ", "") for k in keywords[:1] if k]
    self_hints += [d.lower() for d in (community.get("exclude_domains") or [])]
    items: list[RawItem] = []
    seen_urls: set[str] = set()

    with httpx.Client(timeout=25.0) as client:
        for query in queries:
            try:
                resp = client.post(
                    API,
                    headers={"x-api-key": settings.exa_api_key},
                    json={
                        "query": query,
                        "type": "auto",
                        "numResults": 10,
                        "startPublishedDate": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "excludeDomains": EXCLUDE_DOMAINS,
                        "contents": {"text": {"maxCharacters": 1000}},
                    },
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
            except Exception:
                logger.exception("exa search failed for query %r (continuing)", query)
                continue

            for r in results:
                url = (r.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                domain = urlparse(url).netloc.removeprefix("www.").lower()
                if any(h and h in domain for h in self_hints):
                    continue  # project's own site — self-content, not a mention
                items.append(
                    RawItem(
                        source_kind="web",
                        source_url=url,
                        title=r.get("title") or url,
                        body=(r.get("text") or "")[:2000],
                        author=r.get("author"),
                        observed_at=_parse_dt(r.get("publishedDate")),
                        extra={"query": query, "domain": domain, "score": r.get("score")},
                    )
                )

    logger.info("exa: %d raw items", len(items))
    return items
