"""Reddit connector via public JSON endpoints. Best-effort, non-critical:
generic-UA throttling is expected — failures are logged and dropped."""

import logging
import time
from datetime import datetime, timezone

import httpx

from app.connectors.base import RawItem

logger = logging.getLogger(__name__)

UA = "maintainer-brief/0.1 (open source ecosystem monitor)"


def fetch(project_config: dict, since: datetime) -> list[RawItem]:
    community = project_config.get("community") or {}
    subreddits = community.get("subreddits") or []
    keywords = project_config.get("keywords") or []
    if not subreddits or not keywords:
        return []

    items: list[RawItem] = []
    seen: set[str] = set()
    query = " OR ".join(f'"{k}"' if " " in k else k for k in keywords[:4])

    with httpx.Client(timeout=20.0, headers={"User-Agent": UA}, follow_redirects=True) as client:
        for sub in subreddits:
            try:
                resp = client.get(
                    f"https://www.reddit.com/r/{sub}/search.json",
                    params={"q": query, "restrict_sr": 1, "sort": "new", "limit": 25},
                )
                resp.raise_for_status()
                posts = resp.json().get("data", {}).get("children", [])
            except Exception:
                logger.warning("reddit fetch failed for r/%s (non-critical, skipping)", sub)
                continue

            for post in posts:
                d = post.get("data", {})
                created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
                url = f"https://www.reddit.com{d.get('permalink', '')}"
                if created < since or url in seen:
                    continue
                seen.add(url)
                items.append(
                    RawItem(
                        source_kind="reddit",
                        source_url=url,
                        title=d.get("title", ""),
                        body=(d.get("selftext") or "")[:2000],
                        author=d.get("author"),
                        observed_at=created,
                        extra={"subreddit": sub, "score": d.get("score"), "num_comments": d.get("num_comments")},
                    )
                )
            time.sleep(2)  # stay polite, unauthenticated

    logger.info("reddit: %d raw items", len(items))
    return items
