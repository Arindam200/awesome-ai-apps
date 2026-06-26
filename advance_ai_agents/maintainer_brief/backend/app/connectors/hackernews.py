"""Hacker News connector via Algolia search API. No key needed."""

import logging
from datetime import datetime, timezone

import httpx

from app.connectors.base import RawItem

logger = logging.getLogger(__name__)

API = "https://hn.algolia.com/api/v1/search_by_date"


def fetch(project_config: dict, since: datetime) -> list[RawItem]:
    queries = (project_config.get("community") or {}).get("hn_queries") or []
    items: list[RawItem] = []
    since_i = int(since.timestamp())
    seen_urls: set[str] = set()

    with httpx.Client(timeout=20.0) as client:
        for query in queries:
            try:
                resp = client.get(
                    API,
                    params={
                        "query": query,
                        "tags": "(story,comment)",
                        "numericFilters": f"created_at_i>{since_i}",
                        "hitsPerPage": 50,
                    },
                )
                resp.raise_for_status()
                hits = resp.json().get("hits", [])
            except Exception:
                logger.exception("HN fetch failed for query %s", query)
                continue

            for hit in hits:
                url = f"https://news.ycombinator.com/item?id={hit['objectID']}"
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                title = hit.get("title") or hit.get("story_title") or "(comment)"
                items.append(
                    RawItem(
                        source_kind="hackernews",
                        source_url=url,
                        title=title,
                        body=(hit.get("comment_text") or hit.get("story_text") or "")[:2000],
                        author=hit.get("author"),
                        observed_at=datetime.fromtimestamp(hit["created_at_i"], tz=timezone.utc),
                        extra={"points": hit.get("points"), "query": query,
                               "kind": "comment" if hit.get("comment_text") else "story"},
                    )
                )

    logger.info("hackernews: %d raw items", len(items))
    return items
