"""Deterministic insight candidates for the v2 signal engine.

This is the part that makes the brief *actionable* instead of commentary. It
takes a live repo-state snapshot (from github_conn.fetch_repo_state) plus the
normalized external signals (HN/Reddit/OSV) and computes, in plain Python (no
LLM), the candidate items for each maintainer-facing section:

  - Triage:            open issues that need a decision this week
  - Ship It:           unreleased merges, ready-to-merge PRs, aging reviews, CVEs
  - People:            newcomers' PRs going stale (contributor-churn risk)
  - Worth Replying To: fresh HN/Reddit threads

The LLM downstream only *labels and writes copy* for these candidates — it never
invents an issue or PR number. Every candidate carries its real URL and number.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.connectors.github_conn import GhIssue, GhPull, RepoState

# Tunables (revisit during dogfood; see design doc §1 precision bars)
HOT_REACTIONS = 5
HOT_COMMENTS = 8
STALE_PR_DAYS = 7
TRIAGE_MAX = 40
NEEDS_REVIEW_MAX = 8
NEWCOMER_ASSOCIATIONS = {"FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _issue_score(i: GhIssue) -> float:
    """Higher = more likely to need a maintainer decision this week."""
    score = i.reactions * 2 + i.comments
    if not i.assigned:
        score += 4
    if i.comments == 0:
        score += 3  # nobody has answered a fresh issue
    if i.updated_at and (_now() - i.updated_at).days <= 7:
        score += 3  # active this week
    return score


def _triage_candidates(states: list[RepoState]) -> list[dict]:
    rows: list[dict] = []
    for s in states:
        for i in s.open_issues:
            rows.append(
                {
                    "repo": s.repo,
                    "number": i.number,
                    "title": i.title,
                    "url": i.url,
                    "reactions": i.reactions,
                    "comments": i.comments,
                    "age_days": i.age_days,
                    "assigned": i.assigned,
                    "no_response": i.comments == 0,
                    "hot": i.reactions >= HOT_REACTIONS or i.comments >= HOT_COMMENTS,
                    "labels": i.labels,
                    "_score": _issue_score(i),
                }
            )
    rows.sort(key=lambda r: r["_score"], reverse=True)
    top = rows[:TRIAGE_MAX]
    for r in top:
        r.pop("_score", None)
    return top


def _pr_ref(s: RepoState, p: GhPull, **extra) -> dict:
    return {
        "repo": s.repo,
        "number": p.number,
        "title": p.title,
        "url": p.url,
        "author": p.author,
        "age_days": p.age_days,
        "association": p.author_association,
        **extra,
    }


def _ship_it(states: list[RepoState]) -> dict:
    unreleased: list[dict] = []
    ready: list[dict] = []
    needs_review: list[dict] = []
    latest_release = None

    for s in states:
        if s.latest_release_tag and latest_release is None:
            latest_release = {"tag": s.latest_release_tag, "repo": s.repo}
        for p in s.merged_since_release:
            unreleased.append(
                {"repo": s.repo, "number": p.number, "title": p.title, "url": p.url, "author": p.author}
            )
        for p in s.open_prs:
            if p.is_draft:
                continue
            if p.review_decision == "APPROVED":
                ready.append(_pr_ref(s, p))
            elif (
                p.review_decision == "REVIEW_REQUIRED"
                and p.age_days >= STALE_PR_DAYS
                and p.author_association not in NEWCOMER_ASSOCIATIONS  # newcomers → People
            ):
                needs_review.append(_pr_ref(s, p))

    needs_review.sort(key=lambda r: r["age_days"], reverse=True)
    return {
        "latest_release": latest_release,
        "unreleased": unreleased[:30],
        "unreleased_count": len(unreleased),
        "ready_to_merge": ready,
        "needs_review": needs_review[:NEEDS_REVIEW_MAX],
    }


def _people(states: list[RepoState]) -> list[dict]:
    """Newcomers whose PR is going unreviewed — the churn risk the docs flag."""
    out: list[dict] = []
    for s in states:
        for p in s.open_prs:
            if p.is_draft:
                continue
            if (
                p.author_association in NEWCOMER_ASSOCIATIONS
                and p.review_decision == "REVIEW_REQUIRED"
                and p.age_days >= STALE_PR_DAYS
            ):
                out.append(
                    _pr_ref(s, p, kind="first_pr_stale", pr_number=p.number)
                )
    out.sort(key=lambda r: r["age_days"], reverse=True)
    return out[:8]


def _worth_replying_to(signals: list) -> list[dict]:
    out: list[dict] = []
    for sig in signals:
        if sig.source_kind not in ("hackernews", "reddit"):
            continue
        payload = sig.payload or {}
        engagement = int(payload.get("points") or 0) + int(payload.get("comments") or 0)
        age_days = (_now() - sig.observed_at).days if sig.observed_at else None
        out.append(
            {
                "source": sig.source_kind,
                "title": sig.title,
                "url": sig.source_url,
                "summary": (sig.summary or "")[:240],
                "age_days": age_days,
                "engagement": engagement,
            }
        )
    out.sort(key=lambda r: (r["engagement"], -(r["age_days"] or 999)), reverse=True)
    return out[:8]


def _normalize_url(url: str) -> str:
    """Strip tracking params + trailing slash so near-identical links dedupe."""
    base = url.split("?")[0].split("#")[0].rstrip("/")
    return base.lower()


def _mentions(signals: list) -> list[dict]:
    """Exa web mentions — blogs/newsletters/recaps. Commentary, not action."""
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for sig in signals:
        if sig.source_kind != "web":
            continue
        payload = sig.payload or {}
        url = sig.source_url or ""
        domain = payload.get("domain") or ""
        key = (domain, _normalize_url(url))
        if not url or key in seen:
            continue
        seen.add(key)
        age_days = (_now() - sig.observed_at).days if sig.observed_at else None
        out.append(
            {
                "source": "web",
                "domain": domain,
                "title": sig.title,
                "url": url,
                "summary": (sig.summary or "")[:240],
                "age_days": age_days,
            }
        )
    out.sort(key=lambda r: r["age_days"] if r["age_days"] is not None else 999)
    return out[:8]


def _security(signals: list) -> list[dict]:
    out: list[dict] = []
    for sig in signals:
        if sig.source_kind != "osv":
            continue
        payload = sig.payload or {}
        out.append(
            {
                "id": payload.get("vuln_id") or sig.title.split(":")[0],
                "title": sig.title,
                "url": sig.source_url,
                "severity": payload.get("severity", "unknown"),
                "package": payload.get("package"),
            }
        )
    return out[:8]


def build_candidates(repo_states: list[RepoState], external_signals: list) -> dict:
    """Assemble the full candidate set the synthesis LLM will label.

    external_signals: normalized Signal rows for the period (HN/Reddit/OSV).
    """
    ok_states = [s for s in repo_states if not s.error]
    ship = _ship_it(ok_states)
    ship["security"] = _security(external_signals)

    return {
        "repos": [s.repo for s in ok_states],
        "stats": {
            "open_issues": sum(s.open_issue_count for s in ok_states),
            "open_prs": sum(s.open_pr_count for s in ok_states),
            "stars": sum(s.stars for s in ok_states),
            "latest_release": ship["latest_release"]["tag"] if ship["latest_release"] else None,
            "unreleased_prs": ship["unreleased_count"],
        },
        "triage": _triage_candidates(ok_states),
        "ship_it": ship,
        "people": _people(ok_states),
        "worth_replying_to": _worth_replying_to(external_signals),
        # NOTE: mentions deliberately do NOT count toward brief_signal_count —
        # they're commentary; a mentions-only week stays a quiet week.
        "mentions": _mentions(external_signals),
        "errors": [{"repo": s.repo, "error": s.error} for s in repo_states if s.error],
    }
