"""GitHub connector: issues, PRs, releases, discussions via REST v3."""

import logging
from datetime import datetime

import httpx

from app.config import settings
from app.connectors.base import RawItem

logger = logging.getLogger(__name__)

API = "https://api.github.com"


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "maintainer-brief/0.1"}
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


def _get(client: httpx.Client, path: str, **params) -> list | dict:
    resp = client.get(f"{API}{path}", params=params, headers=_headers())
    resp.raise_for_status()
    return resp.json()


def _parse_dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def repo_metadata(repo: str) -> dict:
    """Validate a 'org/name' repo and return metadata for the create-project UI.
    Raises httpx.HTTPStatusError (404) if it doesn't exist."""
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(f"{API}/repos/{repo}", headers=_headers())
        resp.raise_for_status()
        d = resp.json()
    return {
        "full_name": d["full_name"],
        "name": d["name"],
        "description": d.get("description") or "",
        "topics": d.get("topics") or [],
        "stargazers_count": d.get("stargazers_count", 0),
        "language": d.get("language"),
        "owner_avatar": (d.get("owner") or {}).get("avatar_url"),
        "html_url": d.get("html_url"),
        "default_branch": d.get("default_branch"),
    }


def fetch(project_config: dict, since: datetime) -> list[RawItem]:
    repos = (project_config.get("github") or {}).get("repos") or []
    items: list[RawItem] = []
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    with httpx.Client(timeout=30.0) as client:
        for repo in repos:
            # Issues + PRs (the issues endpoint returns both; PRs carry a pull_request key)
            try:
                for issue in _get(client, f"/repos/{repo}/issues", since=since_iso, state="all", per_page=100):
                    is_pr = "pull_request" in issue
                    labels = [l["name"].lower() for l in issue.get("labels", [])]
                    items.append(
                        RawItem(
                            source_kind="github",
                            source_url=issue["html_url"],
                            title=issue["title"],
                            body=(issue.get("body") or "")[:2000],
                            author=(issue.get("user") or {}).get("login"),
                            observed_at=_parse_dt(issue.get("created_at")),
                            extra={
                                "repo": repo,
                                "kind": "pr" if is_pr else "issue",
                                "labels": labels,
                                "comments": issue.get("comments", 0),
                                "reactions": (issue.get("reactions") or {}).get("total_count", 0),
                                "state": issue.get("state"),
                            },
                        )
                    )
            except Exception:
                logger.exception("github issues fetch failed for %s", repo)

            # Discussions (REST; available on repos with discussions enabled)
            try:
                for disc in _get(client, f"/repos/{repo}/discussions", per_page=50):
                    created = _parse_dt(disc.get("created_at"))
                    if created and created < since:
                        continue
                    items.append(
                        RawItem(
                            source_kind="github",
                            source_url=disc["html_url"],
                            title=disc["title"],
                            body=(disc.get("body") or "")[:2000],
                            author=(disc.get("user") or {}).get("login"),
                            observed_at=created,
                            extra={
                                "repo": repo,
                                "kind": "discussion",
                                "category": (disc.get("category") or {}).get("name"),
                                "comments": disc.get("comments", 0),
                                "reactions": (disc.get("reactions") or {}).get("total_count", 0),
                            },
                        )
                    )
            except Exception:
                logger.warning("github discussions unavailable for %s (may be disabled)", repo)

            # Releases
            try:
                for rel in _get(client, f"/repos/{repo}/releases", per_page=10):
                    published = _parse_dt(rel.get("published_at"))
                    if published and published < since:
                        continue
                    items.append(
                        RawItem(
                            source_kind="github",
                            source_url=rel["html_url"],
                            title=f"Release: {rel.get('name') or rel.get('tag_name')}",
                            body=(rel.get("body") or "")[:2000],
                            author=(rel.get("author") or {}).get("login"),
                            observed_at=published,
                            extra={"repo": repo, "kind": "release", "tag": rel.get("tag_name")},
                        )
                    )
            except Exception:
                logger.exception("github releases fetch failed for %s", repo)

    logger.info("github: %d raw items", len(items))
    return items
