"""Trend metrics: current period vs prior period, plain SQL over signals."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Project, Signal, TrendMetric


def _count_by(db: Session, project_id: int, start: date, end: date, column, prefix: str) -> dict[str, float]:
    rows = db.execute(
        select(column, func.count(Signal.id))
        .where(
            Signal.project_id == project_id,
            Signal.observed_at >= start,
            Signal.observed_at < end,
            column.isnot(None),
        )
        .group_by(column)
    ).all()
    return {f"{prefix}:{key}": float(count) for key, count in rows}


def _keyword_counts(db: Session, project_id: int, start: date, end: date) -> dict[str, float]:
    kw = func.unnest(Signal.keywords).label("kw")
    sub = (
        select(kw)
        .where(
            Signal.project_id == project_id,
            Signal.observed_at >= start,
            Signal.observed_at < end,
            Signal.keywords.isnot(None),
        )
        .subquery()
    )
    rows = db.execute(select(sub.c.kw, func.count()).group_by(sub.c.kw)).all()
    return {f"mentions:{key}": float(count) for key, count in rows}


def _sentiment(db: Session, project_id: int, start: date, end: date) -> dict[str, float]:
    avg = db.scalar(
        select(func.avg(Signal.sentiment)).where(
            Signal.project_id == project_id,
            Signal.observed_at >= start,
            Signal.observed_at < end,
            Signal.sentiment.isnot(None),
        )
    )
    return {"sentiment:overall": float(avg)} if avg is not None else {}


def compute_trends(db: Session, project: Project, period_start: date, period_end: date) -> list[TrendMetric]:
    period_len = period_end - period_start
    prior_start, prior_end = period_start - period_len, period_start

    def all_metrics(start: date, end: date) -> dict[str, float]:
        metrics = {}
        metrics.update(_count_by(db, project.id, start, end, Signal.signal_type, "type"))
        metrics.update(_keyword_counts(db, project.id, start, end))
        metrics.update(_sentiment(db, project.id, start, end))
        return metrics

    current = all_metrics(period_start, period_end)
    prior = all_metrics(prior_start, prior_end)

    # Upsert: delete this period's rows, re-insert
    db.query(TrendMetric).filter(
        TrendMetric.project_id == project.id, TrendMetric.period_start == period_start
    ).delete()

    rows = []
    for key, value in current.items():
        rows.append(
            TrendMetric(
                project_id=project.id,
                metric_key=key,
                period_start=period_start,
                period_end=period_end,
                value=value,
                prior_value=prior.get(key),
            )
        )
    db.add_all(rows)
    db.commit()
    return rows
