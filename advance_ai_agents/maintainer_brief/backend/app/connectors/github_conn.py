"""GitHub connector.

Two roles:
  1. fetch() — legacy RawItem stream (kept for HN/Reddit-style normalization path).
  2. fetch_repo_state() — GraphQL snapshot of a repo's *current* triage-relevant
     state (open issues, open PRs with review decisions, merges since last
     release). This is the data layer for the v2 signal engine, which turns a
     repo's live state into maintainer actions rather than commentary.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.connectors.base import RawItem

logger = logging.getLogger(__name__)

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"


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


# ── v2 signal engine: live repo-state snapshot via GraphQL ──────────────────


@dataclass
class GhIssue:
    number: int
    title: str
    url: str
    body: str
    author: str | None
    author_association: str
    comments: int
    reactions: int
    labels: list[str]
    created_at: datetime | None
    updated_at: datetime | None
    assigned: bool

    @property
    def age_days(self) -> int:
        if not self.created_at:
            return 0
        return (datetime.now(timezone.utc) - self.created_at).days


@dataclass
class GhPull:
    number: int
    title: str
    url: str
    author: str | None
    author_association: str
    review_decision: str | None  # APPROVED | CHANGES_REQUESTED | REVIEW_REQUIRED | None
    is_draft: bool
    additions: int
    deletions: int
    created_at: datetime | None
    updated_at: datetime | None
    merged_at: datetime | None = None

    @property
    def age_days(self) -> int:
        if not self.created_at:
            return 0
        return (datetime.now(timezone.utc) - self.created_at).days


@dataclass
class RepoState:
    repo: str
    stars: int
    open_issue_count: int
    open_pr_count: int
    latest_release_tag: str | None
    latest_release_at: datetime | None
    open_issues: list[GhIssue] = field(default_factory=list)
    open_prs: list[GhPull] = field(default_factory=list)
    merged_since_release: list[GhPull] = field(default_factory=list)
    error: str | None = None


# Kept deliberately light: no bodyText (expensive across 60 issues; titles +
# labels are enough for dup clustering), modest page sizes — big repos 502 on
# heavy GraphQL queries.
_REPO_STATE_QUERY = """
query($owner:String!, $name:String!) {
  repository(owner:$owner, name:$name) {
    nameWithOwner
    stargazerCount
    issues(states:OPEN, first:60, orderBy:{field:UPDATED_AT, direction:DESC}) {
      totalCount
      nodes {
        number title url createdAt updatedAt
        author { login }
        authorAssociation
        comments { totalCount }
        reactions { totalCount }
        assignees(first:1) { totalCount }
        labels(first:8) { nodes { name } }
      }
    }
    openPRs: pullRequests(states:OPEN, first:60, orderBy:{field:UPDATED_AT, direction:DESC}) {
      totalCount
      nodes {
        number title url createdAt updatedAt isDraft additions deletions
        author { login }
        authorAssociation
        reviewDecision
      }
    }
    mergedPRs: pullRequests(states:MERGED, first:30, orderBy:{field:UPDATED_AT, direction:DESC}) {
      nodes {
        number title url createdAt mergedAt additions deletions
        author { login }
        authorAssociation
        reviewDecision
        isDraft
      }
    }
    releases(first:1, orderBy:{field:CREATED_AT, direction:DESC}) {
      nodes { tagName createdAt }
    }
  }
}
"""


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def _issue_from_node(n: dict) -> GhIssue:
    return GhIssue(
        number=n["number"],
        title=n["title"],
        url=n["url"],
        body="",
        author=(n.get("author") or {}).get("login") if n.get("author") else None,
        author_association=n.get("authorAssociation") or "NONE",
        comments=(n.get("comments") or {}).get("totalCount", 0),
        reactions=(n.get("reactions") or {}).get("totalCount", 0),
        labels=[l["name"] for l in (n.get("labels") or {}).get("nodes", [])],
        created_at=_dt(n.get("createdAt")),
        updated_at=_dt(n.get("updatedAt")),
        assigned=(n.get("assignees") or {}).get("totalCount", 0) > 0,
    )


def _pull_from_node(n: dict) -> GhPull:
    return GhPull(
        number=n["number"],
        title=n["title"],
        url=n["url"],
        author=(n.get("author") or {}).get("login") if n.get("author") else None,
        author_association=n.get("authorAssociation") or "NONE",
        review_decision=n.get("reviewDecision"),
        is_draft=bool(n.get("isDraft")),
        additions=n.get("additions", 0),
        deletions=n.get("deletions", 0),
        created_at=_dt(n.get("createdAt")),
        updated_at=_dt(n.get("updatedAt")),
        merged_at=_dt(n.get("mergedAt")),
    )


def fetch_repo_state(repos: list[str]) -> list[RepoState]:
    """One GraphQL call per repo → a snapshot of its current triage state.
    Best-effort: a failing repo yields a RepoState with .error set, never raises."""
    states: list[RepoState] = []
    if not settings.github_token:
        logger.warning("no GITHUB_TOKEN — repo-state fetch (GraphQL) skipped")
        return states

    with httpx.Client(timeout=40.0) as client:
        for repo in repos:
            try:
                owner, _, name = repo.partition("/")
                data = None
                for attempt in range(3):
                    resp = client.post(
                        GRAPHQL,
                        headers=_headers(),
                        json={"query": _REPO_STATE_QUERY, "variables": {"owner": owner, "name": name}},
                    )
                    # GitHub 502/503s on heavy queries for big repos — retry
                    if resp.status_code in (502, 503) and attempt < 2:
                        logger.warning("graphql %s for %s, retry %d", resp.status_code, repo, attempt + 1)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    break
                if data is None:
                    raise RuntimeError("graphql retries exhausted")
                if data.get("errors"):
                    raise RuntimeError(str(data["errors"])[:300])
                r = (data.get("data") or {}).get("repository")
                if not r:
                    raise RuntimeError("repository not found")

                rel_nodes = (r.get("releases") or {}).get("nodes") or []
                rel_at = _dt(rel_nodes[0]["createdAt"]) if rel_nodes else None
                rel_tag = rel_nodes[0]["tagName"] if rel_nodes else None

                open_issues = [_issue_from_node(n) for n in (r.get("issues") or {}).get("nodes", [])]
                open_prs = [_pull_from_node(n) for n in (r.get("openPRs") or {}).get("nodes", [])]
                merged = [_pull_from_node(n) for n in (r.get("mergedPRs") or {}).get("nodes", [])]
                merged_since = [
                    p for p in merged
                    if p.merged_at and (rel_at is None or p.merged_at > rel_at)
                ]

                states.append(
                    RepoState(
                        repo=r["nameWithOwner"],
                        stars=r.get("stargazerCount", 0),
                        open_issue_count=(r.get("issues") or {}).get("totalCount", 0),
                        open_pr_count=(r.get("openPRs") or {}).get("totalCount", 0),
                        latest_release_tag=rel_tag,
                        latest_release_at=rel_at,
                        open_issues=open_issues,
                        open_prs=open_prs,
                        merged_since_release=merged_since,
                    )
                )
            except Exception as e:
                logger.exception("repo-state fetch failed for %s", repo)
                states.append(RepoState(
                    repo=repo, stars=0, open_issue_count=0, open_pr_count=0,
                    latest_release_tag=None, latest_release_at=None, error=str(e)[:300],
                ))

    logger.info("repo-state: %d repos (%d ok)", len(states), sum(1 for s in states if not s.error))
    return states
