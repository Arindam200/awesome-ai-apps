"""Hacker News and DEV/Forem source clients."""

from __future__ import annotations

import asyncio
import html
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from models import DEVArticle, HNItem


HN_BASE_URL = "https://hn.algolia.com/api/v1"
DEV_ARTICLES_URL = "https://dev.to/api/articles"
DEV_LATEST_ARTICLES_URL = "https://dev.to/api/articles/latest"
SOURCE_LOOKBACK_DAYS = 365
MAX_DEV_DETAIL_FETCHES = 8
HN_NOISE_PATTERNS = (
    "ask hn: who wants to be hired",
    "ask hn: who is hiring",
    "ask hn: freelancer",
    "ask hn: freelancers",
    "who wants to be hired",
    "who is hiring",
    "freelancer? seeking freelancer",
)


def _since_datetime(lookback_days: int = SOURCE_LOOKBACK_DAYS) -> datetime:
    return datetime.now(UTC) - timedelta(days=lookback_days)


def _parse_source_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _hn_url(hit: dict[str, Any], source_type: str) -> str:
    if hit.get("url"):
        return str(hit["url"])
    object_id = hit.get("objectID") or hit.get("story_id")
    if source_type == "comment" and hit.get("story_id"):
        return f"https://news.ycombinator.com/item?id={hit['story_id']}"
    return f"https://news.ycombinator.com/item?id={object_id}"


def normalize_hn_hit(hit: dict[str, Any], source_type: str) -> HNItem:
    title = (
        hit.get("title")
        or hit.get("story_title")
        or hit.get("comment_text")
        or "Untitled Hacker News item"
    )
    text = hit.get("comment_text") or hit.get("story_text") or hit.get("text")
    return HNItem(
        title=html.unescape(str(title)),
        url=_hn_url(hit, source_type),
        author=hit.get("author"),
        points=hit.get("points"),
        num_comments=hit.get("num_comments"),
        created_at=hit.get("created_at"),
        text=html.unescape(str(text)) if text else None,
        source_type=source_type,
    )


async def search_hn(
    queries: list[str],
    limit: int = 10,
    timeout: float = 20.0,
    lookback_days: int = SOURCE_LOOKBACK_DAYS,
) -> list[HNItem]:
    per_query = max(1, min(limit, 20))
    since = _since_datetime(lookback_days)
    since_unix = int(since.timestamp())
    items: list[HNItem] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def fetch(query: str, source_type: str) -> list[HNItem]:
            response = await client.get(
                f"{HN_BASE_URL}/search_by_date",
                params={
                    "query": query,
                    "tags": source_type,
                    "hitsPerPage": per_query,
                    "numericFilters": f"created_at_i>{since_unix}",
                },
            )
            response.raise_for_status()
            payload = response.json()
            return [
                normalize_hn_hit(hit, source_type)
                for hit in payload.get("hits", [])
            ]

        batches = await asyncio.gather(
            *[
                fetch(query, source_type)
                for query in queries
                for source_type in ("story", "comment")
            ]
        )
        for batch in batches:
            items.extend(batch)
    recent = [
        item
        for item in _dedupe_hn_items(items)
        if (created := _parse_source_datetime(item.created_at)) is None or created >= since
    ]
    recent = [item for item in recent if not _is_noisy_hn_item(item)]
    recent = _filter_hn_relevance(recent, queries)
    recent.sort(key=lambda item: _parse_source_datetime(item.created_at) or since, reverse=True)
    return recent[: max(limit * 2, limit)]


def _is_noisy_hn_item(item: HNItem) -> bool:
    title = item.title.lower()
    text = (item.text or "").lower()
    haystack = f"{title} {text}"
    return any(pattern in haystack for pattern in HN_NOISE_PATTERNS)


def _query_terms(queries: list[str]) -> set[str]:
    stopwords = {
        "and",
        "the",
        "for",
        "with",
        "from",
        "that",
        "this",
        "tool",
        "tools",
        "platform",
        "product",
        "web",
        "app",
        "apps",
        "api",
        "real",
        "user",
        "users",
    }
    terms: set[str] = set()
    for query in queries:
        for token in re.findall(r"[a-z0-9]+", query.lower()):
            if len(token) > 2 and token not in stopwords:
                terms.add(token)
    return terms


def _query_phrases(queries: list[str]) -> set[str]:
    phrases: set[str] = set()
    for query in queries:
        normalized = " ".join(re.findall(r"[a-z0-9]+", query.lower()))
        words = normalized.split()
        if len(words) < 2:
            continue
        phrases.add(normalized)
        for index in range(len(words) - 1):
            pair = " ".join(words[index : index + 2])
            if not any(term in pair for term in ("and", "the", "tool", "platform")):
                phrases.add(pair)
    return phrases


def _filter_hn_relevance(items: list[HNItem], queries: list[str]) -> list[HNItem]:
    terms = _query_terms(queries)
    phrases = _query_phrases(queries)
    if not terms and not phrases:
        return items

    min_overlap = 1 if len(terms) <= 3 else 2
    matched: list[HNItem] = []
    for item in items:
        haystack = f"{item.title} {item.text or ''}".lower()
        phrase_match = any(phrase in haystack for phrase in phrases)
        overlap = sum(1 for term in terms if term in haystack)
        if phrase_match or overlap >= min_overlap:
            matched.append(item)
    return matched


def _dedupe_hn_items(items: list[HNItem]) -> list[HNItem]:
    seen: set[str] = set()
    unique: list[HNItem] = []
    for item in items:
        if item.url in seen:
            continue
        seen.add(item.url)
        unique.append(item)
    return unique


def normalize_dev_article(article: dict[str, Any]) -> DEVArticle:
    user = article.get("user") or {}
    raw_tags = article.get("tag_list") or article.get("tags") or []
    if isinstance(raw_tags, str):
        tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
    else:
        tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]

    body_excerpt = _article_body_excerpt(
        article.get("body_markdown")
        or article.get("body_html")
        or article.get("body")
    )
    return DEVArticle(
        title=str(article.get("title") or "Untitled DEV article"),
        url=str(article.get("url") or article.get("canonical_url") or ""),
        id=_safe_int(article.get("id")),
        path=article.get("path"),
        author=user.get("username") or user.get("name"),
        tags=tags,
        published_at=article.get("published_at") or article.get("published_timestamp"),
        positive_reactions_count=article.get("positive_reactions_count")
        or article.get("public_reactions_count"),
        comments_count=article.get("comments_count"),
        description=article.get("description"),
        body_excerpt=body_excerpt,
    )


async def search_dev_articles(
    queries: list[str],
    tags: list[str],
    limit: int = 10,
    api_key: str | None = None,
    timeout: float = 20.0,
    lookback_days: int = SOURCE_LOOKBACK_DAYS,
) -> list[DEVArticle]:
    headers = {"User-Agent": "EngineeringContentAgent/0.1"}
    if api_key:
        headers["api-key"] = api_key

    per_query = max(1, min(limit, 30))
    since = _since_datetime(lookback_days)
    articles: list[DEVArticle] = []
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        async def fetch_tag(tag: str) -> list[DEVArticle]:
            try:
                response = await client.get(
                    DEV_ARTICLES_URL,
                    params={
                        "tag": tag,
                        "top": lookback_days,
                        "per_page": per_query,
                        "page": 1,
                    },
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {404, 429}:
                    return []
                raise
            return [normalize_dev_article(item) for item in response.json()]

        if tags:
            batches = await asyncio.gather(
                *[fetch_tag(tag) for tag in tags[:6]]
            )
            for batch in batches:
                articles.extend(batch)
        else:
            response = await client.get(
                DEV_LATEST_ARTICLES_URL,
                params={"per_page": per_query, "page": 1},
            )
            response.raise_for_status()
            articles.extend(normalize_dev_article(item) for item in response.json())

        filtered = filter_dev_articles(articles, queries, tags)
        recent = [
            article
            for article in _dedupe_articles(filtered)
            if (published := _parse_source_datetime(article.published_at)) is None
            or published >= since
        ]
        recent.sort(
            key=lambda article: _parse_source_datetime(article.published_at) or since,
            reverse=True,
        )
        enriched = await _enrich_dev_article_details(
            client,
            recent[: max(limit * 2, limit)],
            max_details=min(MAX_DEV_DETAIL_FETCHES, max(limit, 1)),
        )
        return enriched[: max(limit * 2, limit)]


def filter_dev_articles(
    articles: list[DEVArticle],
    queries: list[str],
    tags: list[str],
) -> list[DEVArticle]:
    needles = _query_terms([*queries, *tags])
    phrases = _query_phrases(queries)
    if not needles and not phrases:
        return articles

    matched: list[DEVArticle] = []
    for article in articles:
        haystack = " ".join(
            [
                article.title,
                article.description or "",
                article.body_excerpt or "",
                " ".join(article.tags),
            ]
        ).lower()
        phrase_match = any(phrase in haystack for phrase in phrases)
        overlap = sum(1 for needle in needles if needle in haystack)
        if phrase_match or overlap >= 2:
            matched.append(article)
    return matched


def _dedupe_articles(articles: list[DEVArticle]) -> list[DEVArticle]:
    seen: set[str] = set()
    unique: list[DEVArticle] = []
    for article in articles:
        key = article.url or article.title
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)
    return unique


async def _enrich_dev_article_details(
    client: httpx.AsyncClient,
    articles: list[DEVArticle],
    max_details: int = MAX_DEV_DETAIL_FETCHES,
) -> list[DEVArticle]:
    candidates = [
        article
        for article in articles
        if article.id is not None and not article.body_excerpt
    ][:max_details]
    if not candidates:
        return articles

    async def fetch_detail(article: DEVArticle) -> DEVArticle:
        try:
            response = await client.get(f"{DEV_ARTICLES_URL}/{article.id}")
            response.raise_for_status()
        except httpx.HTTPError:
            return article
        detailed = normalize_dev_article(response.json())
        return DEVArticle(
            title=detailed.title or article.title,
            url=detailed.url or article.url,
            id=detailed.id or article.id,
            path=detailed.path or article.path,
            author=detailed.author or article.author,
            tags=detailed.tags or article.tags,
            published_at=detailed.published_at or article.published_at,
            positive_reactions_count=(
                detailed.positive_reactions_count
                if detailed.positive_reactions_count is not None
                else article.positive_reactions_count
            ),
            comments_count=(
                detailed.comments_count
                if detailed.comments_count is not None
                else article.comments_count
            ),
            description=detailed.description or article.description,
            body_excerpt=detailed.body_excerpt or article.body_excerpt,
        )

    enriched_by_url = {
        article.url: article for article in await asyncio.gather(
            *(fetch_detail(article) for article in candidates)
        )
    }
    return [enriched_by_url.get(article.url, article) for article in articles]


def _safe_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _article_body_excerpt(value: object, limit: int = 700) -> str | None:
    if not value:
        return None
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"#+\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    return text[:limit].rstrip()
