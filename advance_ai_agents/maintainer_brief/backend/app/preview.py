"""No-signin instant repo preview — the conversion moment.

Two phases so the visitor sees value in seconds instead of waiting on the LLM:
  phase 1 (~3-6s): GraphQL repo snapshot -> deterministic candidates -> a
                   placeholder brief with real sections/links but templated copy.
  phase 2 (~30-60s): a background thread runs the LLM synthesis and upgrades the
                   row to `ready`; the frontend polls and the copy fills in.

Abuse control (single backend instance, in-memory is fine; resets on deploy):
per-IP daily cap, global daily cap, and a semaphore bounding concurrent LLM
synthesis. Results cache in Postgres for 24h so popular repos are instant.
"""

import logging
import re
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.github_conn import fetch_repo_state
from app.db import SessionLocal
from app.intelligence.brief_v2 import synthesize_brief_v2
from app.intelligence.insights import build_candidates
from app.models import PreviewBrief

logger = logging.getLogger(__name__)

REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
CACHE_TTL = timedelta(hours=24)
PER_IP_DAILY = 10
GLOBAL_DAILY = 300
_SYNTH_SEMAPHORE = threading.Semaphore(2)

_counters_lock = threading.Lock()
_counters: dict[str, int] = {}  # ip -> count today
_counters_day: str = ""
_global_count = 0


def _check_rate(ip: str) -> bool:
    """True if this request is allowed. Day-scoped in-memory counters."""
    global _counters_day, _global_count
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _counters_lock:
        if _counters_day != today:
            _counters.clear()
            _counters_day = today
            _global_count = 0
        if _global_count >= GLOBAL_DAILY or _counters.get(ip, 0) >= PER_IP_DAILY:
            return False
        _counters[ip] = _counters.get(ip, 0) + 1
        _global_count += 1
        return True


def normalize_repo(repo: str) -> str | None:
    repo = repo.strip().removeprefix("https://github.com/").strip("/").lower()
    return repo if REPO_RE.match(repo) else None


def placeholder_brief(repo: str, candidates: dict) -> dict:
    """Deterministic brief_json — real sections and links, copy pending."""
    stats = candidates["stats"]
    ship = candidates["ship_it"]
    n_triage = len(candidates["triage"])
    n_ready = len(ship["ready_to_merge"])
    bits = []
    if n_triage:
        bits.append(f"{n_triage} issues need a decision")
    if n_ready:
        bits.append(f"{n_ready} PRs are ready to merge")
    if ship["unreleased_count"]:
        bits.append(f"{ship['unreleased_count']} merges are waiting on a release")
    headline = f"{repo}: " + (", ".join(bits) if bits else "a quiet week") + "."

    kind = lambda r: "hot" if r["hot"] else ("unanswered" if r["no_response"] else "stalled")  # noqa: E731
    triage = [
        {
            "title": r["title"][:80],
            "kind": kind(r),
            "action": "",  # phase 2 fills this in
            "issues": [
                {"number": r["number"], "repo": r["repo"], "title": r["title"],
                 "url": r["url"], "reactions": r["reactions"], "comments": r["comments"]}
            ],
        }
        for r in candidates["triage"][:10]
    ]

    def pr_out(p: dict, num_key: str = "number") -> dict:
        return {"number": p[num_key], "repo": p["repo"], "title": p["title"], "url": p["url"],
                "author": p.get("author"), "age_days": p.get("age_days"), "note": ""}

    return {
        "headline": headline,
        "stats": stats,
        "triage": triage,
        "ship_it": {
            "latest_release": ship["latest_release"]["tag"] if ship["latest_release"] else None,
            "unreleased_count": ship["unreleased_count"],
            "release_summary": "",  # phase 2
            "ready_to_merge": [pr_out(p) for p in ship["ready_to_merge"]],
            "needs_review": [pr_out(p) for p in ship["needs_review"]],
            "security": [],
        },
        "people": [pr_out(p, num_key="pr_number") for p in candidates["people"]],
        "worth_replying_to": [],
        "mentions": [],
    }


def _synthesize_in_thread(preview_id: int, repo: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(PreviewBrief, preview_id)
        if not row or not row.candidates_json:
            return
        with _SYNTH_SEMAPHORE:
            try:
                brief_json = synthesize_brief_v2(repo, row.candidates_json)
                row.brief_json = brief_json
                row.status = "ready"
            except Exception as e:
                logger.exception("preview synthesis failed for %s", repo)
                row.status = "failed"
                row.error = str(e)[:300]
        row.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def preview_dict(row: PreviewBrief) -> dict:
    return {
        "preview_id": row.id,
        "repo": row.repo,
        "status": row.status,
        "generated_at": row.created_at.isoformat() if row.created_at else None,
        "brief_json": row.brief_json,
    }


def get_or_create_preview(db: Session, repo_raw: str, ip: str) -> tuple[int, dict]:
    """Returns (http_status, payload). 200 on success paths."""
    repo = normalize_repo(repo_raw or "")
    if not repo:
        return 422, {"detail": "expected 'org/name'"}

    # cache hit — fresh row for this repo (any status but failed)
    cutoff = datetime.now(timezone.utc) - CACHE_TTL
    cached = db.scalar(
        select(PreviewBrief)
        .where(PreviewBrief.repo == repo, PreviewBrief.created_at >= cutoff,
               PreviewBrief.status != "failed")
        .order_by(PreviewBrief.created_at.desc())
        .limit(1)
    )
    if cached:
        return 200, preview_dict(cached)

    if not _check_rate(ip):
        return 429, {"detail": "preview limit reached — sign in for unlimited briefs"}

    states = fetch_repo_state([repo])
    if not states or states[0].error:
        err = states[0].error if states else "fetch failed"
        if "not found" in (err or "").lower() or "NOT_FOUND" in (err or ""):
            return 404, {"detail": "repository not found"}
        return 502, {"detail": f"github error: {err}"}

    candidates = build_candidates(states, [])
    row = PreviewBrief(
        repo=repo,
        status="phase1",
        candidates_json=candidates,
        brief_json=placeholder_brief(repo, candidates),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    threading.Thread(target=_synthesize_in_thread, args=(row.id, repo), daemon=True).start()
    return 200, preview_dict(row)
