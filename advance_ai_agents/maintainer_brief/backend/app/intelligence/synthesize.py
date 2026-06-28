"""Brief synthesis: signals + trends -> structured brief JSON via Claude.

Uses structured outputs (messages.parse with Pydantic) so the brief is always
valid JSON. Every claim must carry signal_ids; hallucinated ids are dropped
and the call retried once with the validation errors appended.
"""

import json
import logging
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.llm import parse_structured
from app.models import Project, Signal, TrendMetric

logger = logging.getLogger(__name__)

MAX_SIGNALS = 300


class FeatureCluster(BaseModel):
    cluster_name: str
    summary: str
    urgency: str = Field(description="low, medium, high, or critical")
    signal_ids: list[int]
    recommendation_hint: str = ""


class CommunityHealth(BaseModel):
    summary: str
    metrics_callouts: list[str]
    signal_ids: list[int] = []


class EcosystemMention(BaseModel):
    context: str
    prominence: str = ""
    signal_ids: list[int]


class CompetitorItem(BaseModel):
    competitor: str
    development: str
    why_it_matters: str
    signal_ids: list[int]


class SecurityAlert(BaseModel):
    identifier: str = Field(description="CVE/advisory id, or short label")
    severity: str
    action: str
    signal_ids: list[int]


class Recommendation(BaseModel):
    recommendation: str
    rationale: str
    effort: str = Field(description="small, medium, or large")
    supporting_signal_ids: list[int]


class BriefOutput(BaseModel):
    headline: str
    top_requested_features: list[FeatureCluster]
    community_health: CommunityHealth
    ecosystem_mentions: list[EcosystemMention]
    competitor_watch: list[CompetitorItem]
    security_alerts: list[SecurityAlert]
    maintainer_recommendations: list[Recommendation]


SYSTEM_PROMPT = """You are an expert open source ecosystem analyst writing a weekly intelligence \
brief for the maintainers of {project_name}. You receive a normalized stream of signals \
(GitHub issues/releases, Hacker News and Reddit posts, security advisories, and structured \
extractions from conference decks, reports, and PDFs) plus trend metrics.

Project keywords: {keywords}
Known competitors: {competitors}

Rules:
- Every item you write MUST cite signal_ids drawn ONLY from the ids in the provided signals. Never invent ids.
- Cluster semantically similar feature requests across sources into one cluster; cross-source convergence is the strongest signal.
- Prefer document-sourced signals (conference decks, reports) for ecosystem and competitor sections — they carry citations.
- Be specific and quantitative where the trends table allows ("mentions up 3x week-over-week").
- Use the per-signal "engagement" number (reactions + comments + points) to identify trending issues — \
high-engagement signals deserve priority in clustering, community health, and recommendations.
- Recommendations must be concrete actions a maintainer could start this week.
- If a section has no supporting signals, return an empty list for it (or a brief honest summary for community_health)."""


def _engagement(s: Signal) -> int:
    p = s.payload or {}
    return int(p.get("reactions") or 0) + int(p.get("comments") or 0) + int(p.get("points") or 0)


def _signal_line(s: Signal) -> dict:
    return {
        "id": s.id,
        "type": s.signal_type,
        "source": s.source_kind,
        "title": s.title,
        "summary": (s.summary or "")[:300],
        "urgency": s.urgency,
        "sentiment": s.sentiment,
        "keywords": s.keywords,
        "confidence": s.confidence,
        "engagement": _engagement(s),
    }


def _trends_table(trends: list[TrendMetric]) -> str:
    lines = ["| metric | current | prior |", "|---|---|---|"]
    for t in trends:
        prior = f"{t.prior_value:g}" if t.prior_value is not None else "-"
        lines.append(f"| {t.metric_key} | {t.value:g} | {prior} |")
    return "\n".join(lines)


def synthesize_brief(
    db: Session, project: Project, period_start: date, period_end: date
) -> dict:
    candidates = list(
        db.scalars(
            select(Signal)
            .where(
                Signal.project_id == project.id,
                Signal.observed_at >= period_start,
                Signal.observed_at < period_end,
            )
            .order_by(Signal.observed_at.desc())
            .limit(MAX_SIGNALS * 2)
        )
    )
    # Prioritize document signals, urgency, and engagement when truncating
    urgency_rank = {"critical": 3, "high": 2, "medium": 1}
    candidates.sort(
        key=lambda s: (
            s.source_kind == "document",
            urgency_rank.get((s.urgency or "").lower(), 0),
            _engagement(s),
        ),
        reverse=True,
    )
    signals = candidates[:MAX_SIGNALS]
    trends = list(
        db.scalars(
            select(TrendMetric).where(
                TrendMetric.project_id == project.id,
                TrendMetric.period_start == period_start,
            )
        )
    )
    valid_ids = {s.id for s in signals}

    competitors = ", ".join(c["name"] for c in project.config.get("competitors") or []) or "none listed"
    system = SYSTEM_PROMPT.format(
        project_name=project.name,
        keywords=", ".join(project.config.get("keywords") or []),
        competitors=competitors,
    )
    user_content = (
        f"Period: {period_start} to {period_end}\n\n"
        "## Signals (JSONL)\n"
        + "\n".join(json.dumps(_signal_line(s)) for s in signals)
        + "\n\n## Trend metrics (current period vs prior period)\n"
        + _trends_table(trends)
    )

    content = user_content
    for attempt in range(2):
        brief = parse_structured(
            tier="synthesis",
            system=system,
            user_content=content,
            output_model=BriefOutput,
        )
        if brief is None:
            raise RuntimeError("brief synthesis returned no parseable output")

        bad_ids = _validate_ids(brief, valid_ids)
        if not bad_ids:
            return brief.model_dump()
        if attempt == 0:
            logger.warning("brief cited %d unknown signal ids, retrying", len(bad_ids))
            content = (
                user_content
                + f"\n\nIMPORTANT: a previous attempt cited signal ids that do not exist: "
                f"{sorted(bad_ids)}. Use ONLY ids from the signals above."
            )

    # Last resort: strip the invalid ids rather than failing the run
    _strip_bad_ids(brief, valid_ids)
    return brief.model_dump()


def _iter_id_lists(brief: BriefOutput):
    for item in brief.top_requested_features:
        yield item.signal_ids
    yield brief.community_health.signal_ids
    for item in brief.ecosystem_mentions:
        yield item.signal_ids
    for item in brief.competitor_watch:
        yield item.signal_ids
    for item in brief.security_alerts:
        yield item.signal_ids
    for item in brief.maintainer_recommendations:
        yield item.supporting_signal_ids


def _validate_ids(brief: BriefOutput, valid_ids: set[int]) -> set[int]:
    bad = set()
    for ids in _iter_id_lists(brief):
        bad.update(i for i in ids if i not in valid_ids)
    return bad


def _strip_bad_ids(brief: BriefOutput, valid_ids: set[int]) -> None:
    for ids in _iter_id_lists(brief):
        ids[:] = [i for i in ids if i in valid_ids]
