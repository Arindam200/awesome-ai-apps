"""Batched sentiment scoring for HN/Reddit signals via one Haiku call.
Fail-soft: any error leaves sentiment as None — never blocks the pipeline."""

import logging

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.llm import parse_structured
from app.models import Project, Signal

logger = logging.getLogger(__name__)


class SentimentScore(BaseModel):
    id: int
    score: float  # -1..1


class SentimentBatch(BaseModel):
    scores: list[SentimentScore]


def score_sentiment(db: Session, project: Project, limit: int = 60) -> int:
    signals = list(
        db.scalars(
            select(Signal)
            .where(
                Signal.project_id == project.id,
                Signal.source_kind.in_(["hackernews", "reddit"]),
                Signal.sentiment.is_(None),
            )
            .order_by(Signal.created_at.desc())
            .limit(limit)
        )
    )
    if not signals:
        return 0

    lines = "\n".join(
        f"[{s.id}] {s.title} :: {(s.summary or '')[:200]}" for s in signals
    )
    try:
        batch = parse_structured(
            tier="sentiment",
            system="You score community-post sentiment. Respond only via the structured output.",
            user_content=(
                f"Score the sentiment of each post toward {project.name} / its ecosystem "
                "on a -1.0 (very negative) to 1.0 (very positive) scale, 0 for neutral or "
                "unrelated. One score per [id] line:\n\n" + lines
            ),
            output_model=SentimentBatch,
            max_tokens=4096,
        )
    except Exception:
        logger.exception("sentiment batch failed (non-critical)")
        return 0

    if batch is None:
        return 0
    by_id = {s.id: s for s in signals}
    updated = 0
    for item in batch.scores:
        signal = by_id.get(item.id)
        if signal is not None:
            signal.sentiment = max(-1.0, min(1.0, item.score))
            updated += 1
    db.commit()
    return updated
