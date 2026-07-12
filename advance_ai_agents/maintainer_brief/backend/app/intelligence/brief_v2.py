"""v2 brief synthesis: deterministic candidates -> maintainer-facing brief.

The LLM's job is narrow and safe: cluster/label the *provided* triage issues,
write a changelog blurb, and add one-line copy per item. It never invents an
issue or PR — the final brief_json rebuilds every ref (number/url/title) from the
deterministic candidates and only grafts in the LLM's text, matched by number.
So a hallucinated number is dropped and a corrupted URL is impossible.

Sections: headline · triage · ship_it (release/ready/review/security) · people ·
worth_replying_to.
"""

import json
import logging

from pydantic import BaseModel, Field

from app.intelligence.llm import parse_structured

logger = logging.getLogger(__name__)


# ── What the LLM returns (copy only; refs are rebuilt in Python) ────────────


class TriageCluster(BaseModel):
    title: str = Field(description="short label a maintainer reads, e.g. 'Duplicate: dark-mode flicker'")
    kind: str = Field(description="one of: duplicates, hot, unanswered, stalled")
    action: str = Field(description="the concrete recommended action, one sentence")
    issue_numbers: list[int] = Field(description="issue numbers from the provided candidates ONLY")


class NumberNote(BaseModel):
    number: int
    note: str = Field(description="one short clause of context, no more than ~12 words")


class ThreadWhy(BaseModel):
    url: str
    why: str = Field(description="why the maintainer should reply, one sentence")


class BriefWriteup(BaseModel):
    headline: str = Field(description="one sentence summarizing the maintainer's week")
    triage: list[TriageCluster]
    release_summary: str = Field(description="a short changelog-style blurb of what's merged but unreleased; '' if none")
    ready_to_merge_notes: list[NumberNote] = []
    needs_review_notes: list[NumberNote] = []
    people_notes: list[NumberNote] = []
    worth_replying_to: list[ThreadWhy] = []
    mentions: list[ThreadWhy] = []


SYSTEM_PROMPT = """You are the chief of staff for the maintainers of {project_name}. \
You write a weekly brief that tells them exactly what to DO — not commentary, not \
news. You are given the repo's live state as candidate lists (open issues, PRs, \
merges, threads). Your job is to label and prioritize them.

Hard rules:
- Use ONLY the issue/PR numbers present in the candidates. Never invent a number.
- Every triage cluster's action must be something a maintainer can do this week \
(close as duplicate of #N, add a `needs-repro` label, ship a fix, reply, etc.).
- For triage: group true duplicates or same-root-cause issues into ONE cluster \
with kind "duplicates". Surface high-engagement issues as "hot", brand-new issues \
with no reply as "unanswered", and long-open-but-recently-active ones as "stalled". \
Only recommend "close as duplicate" when you are confident they're the same thing.
- release_summary: 2-4 sentences a maintainer could paste as release notes, \
grouping the unreleased merges by theme (features / fixes / docs). If there are no \
unreleased merges, return "".
- Notes are optional and terse. Skip a note rather than pad it.
- For web_mentions: one line on why the mention matters (reach, sentiment, what \
it gets right/wrong). Use ONLY the provided URLs. Skip low-value SEO spam.
- Prefer fewer, higher-signal items. A short brief a maintainer trusts beats a \
long one they skim."""


def _candidate_digest(candidates: dict) -> str:
    """Compact JSON the model reads. Drops internal fields, keeps numbers+text."""
    triage = [
        {
            "number": r["number"], "repo": r["repo"], "title": r["title"],
            "reactions": r["reactions"], "comments": r["comments"],
            "age_days": r["age_days"], "no_response": r["no_response"],
            "hot": r["hot"], "labels": r["labels"][:5],
        }
        for r in candidates["triage"]
    ]
    ship = candidates["ship_it"]
    unreleased = [{"number": p["number"], "title": p["title"]} for p in ship["unreleased"]]
    ready = [{"number": p["number"], "title": p["title"], "author": p["author"]} for p in ship["ready_to_merge"]]
    review = [
        {"number": p["number"], "title": p["title"], "age_days": p["age_days"]}
        for p in ship["needs_review"]
    ]
    people = [
        {"number": p["pr_number"], "title": p["title"], "author": p["author"], "age_days": p["age_days"]}
        for p in candidates["people"]
    ]
    threads = [
        {"url": t["url"], "source": t["source"], "title": t["title"], "engagement": t["engagement"]}
        for t in candidates["worth_replying_to"]
    ]
    mentions = [
        {"url": m["url"], "domain": m["domain"], "title": m["title"], "age_days": m["age_days"]}
        for m in candidates.get("mentions", [])
    ]
    return json.dumps(
        {
            "triage_issues": triage,
            "unreleased_merges": unreleased,
            "ready_to_merge_prs": ready,
            "aging_prs_needing_review": review,
            "newcomer_stale_prs": people,
            "threads": threads,
            "web_mentions": mentions,
        },
        indent=1,
    )


def _index_notes(notes: list[NumberNote]) -> dict[int, str]:
    return {n.number: n.note for n in notes}


def synthesize_brief_v2(project_name: str, candidates: dict) -> dict:
    """Return the render-ready brief_json. Rebuilds all refs from candidates.

    Takes a plain name (not a Project) so the no-signin preview can synthesize
    for repos that have no Project row.
    """
    system = SYSTEM_PROMPT.format(project_name=project_name)
    user_content = (
        "Here is the repo's live state. Write the weekly brief.\n\n" + _candidate_digest(candidates)
    )

    writeup: BriefWriteup | None = parse_structured(
        tier="synthesis", system=system, user_content=user_content, output_model=BriefWriteup,
        max_tokens=4000,  # output is ~1-2k tokens; capping cuts LLM latency substantially
    )
    if writeup is None:
        raise RuntimeError("v2 brief synthesis returned no parseable output")

    # ── rebuild refs deterministically; graft in the LLM's copy ─────────────
    triage_by_num = {r["number"]: r for r in candidates["triage"]}
    valid_triage_nums = set(triage_by_num)

    triage_out = []
    for cluster in writeup.triage:
        issues = [triage_by_num[n] for n in cluster.issue_numbers if n in valid_triage_nums]
        if not issues:
            continue  # cluster referenced only invalid numbers → drop
        triage_out.append(
            {
                "title": cluster.title,
                "kind": cluster.kind,
                "action": cluster.action,
                "issues": [
                    {"number": i["number"], "repo": i["repo"], "title": i["title"],
                     "url": i["url"], "reactions": i["reactions"], "comments": i["comments"]}
                    for i in issues
                ],
            }
        )

    ship = candidates["ship_it"]
    ready_notes = _index_notes(writeup.ready_to_merge_notes)
    review_notes = _index_notes(writeup.needs_review_notes)
    people_notes = _index_notes(writeup.people_notes)

    def _pr_out(p: dict, notes: dict[int, str], num_key: str = "number") -> dict:
        return {
            "number": p[num_key], "repo": p["repo"], "title": p["title"], "url": p["url"],
            "author": p.get("author"), "age_days": p.get("age_days"),
            "note": notes.get(p[num_key], ""),
        }

    ship_out = {
        "latest_release": ship["latest_release"]["tag"] if ship["latest_release"] else None,
        "unreleased_count": ship["unreleased_count"],
        "release_summary": writeup.release_summary,
        "ready_to_merge": [_pr_out(p, ready_notes) for p in ship["ready_to_merge"]],
        "needs_review": [_pr_out(p, review_notes) for p in ship["needs_review"]],
        "security": ship.get("security", []),
    }

    people_out = [_pr_out(p, people_notes, num_key="pr_number") for p in candidates["people"]]

    why_by_url = {t.url: t.why for t in writeup.worth_replying_to}
    threads_out = [
        {"source": t["source"], "title": t["title"], "url": t["url"],
         "why": why_by_url.get(t["url"], ""), "age_days": t["age_days"]}
        for t in candidates["worth_replying_to"]
    ]

    # Mentions rebuilt from candidates too — a hallucinated URL simply never matches.
    mention_why = {m.url: m.why for m in writeup.mentions}
    mentions_out = [
        {"source": "web", "domain": m["domain"], "title": m["title"], "url": m["url"],
         "why": mention_why.get(m["url"], ""), "age_days": m["age_days"]}
        for m in candidates.get("mentions", [])
    ]

    return {
        "headline": writeup.headline,
        "stats": candidates["stats"],
        "triage": triage_out,
        "ship_it": ship_out,
        "people": people_out,
        "worth_replying_to": threads_out,
        "mentions": mentions_out,
    }


def brief_signal_count(candidates: dict) -> int:
    """How many real actionable items the candidates hold (for the empty-week skip rule)."""
    ship = candidates["ship_it"]
    return (
        len(candidates["triage"])
        + len(ship["ready_to_merge"])
        + len(ship["needs_review"])
        + ship["unreleased_count"]
        + len(candidates["people"])
        + len(candidates["worth_replying_to"])
        + len(ship.get("security", []))
    )
