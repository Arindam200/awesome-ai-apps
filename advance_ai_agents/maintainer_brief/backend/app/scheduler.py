"""In-process APScheduler: per-project newsletter cron.

Lives in its own module so both main.py (startup) and api/routes.py (on
project create/update) can register jobs without a circular import.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db import SessionLocal
from app.models import PipelineRun, Project
from app.pipeline.orchestrator import run_pipeline

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _scheduled_run(project_id: int):
    db = SessionLocal()
    try:
        active = db.scalar(
            select(PipelineRun.id).where(
                PipelineRun.project_id == project_id, PipelineRun.status == "running"
            )
        )
        if active:
            logger.warning("scheduled run skipped: run %s already in progress", active)
            return
        run = PipelineRun(project_id=project_id, dry_run=False, stats={})
        db.add(run)
        db.commit()
        run_pipeline(db, run)
    finally:
        db.close()


def _trigger_for(project: Project) -> CronTrigger:
    cadence = (project.config.get("newsletter") or {}).get("cadence", "weekly")
    if cadence == "daily":
        return CronTrigger(hour=8, minute=0, timezone="UTC")
    return CronTrigger(day_of_week="mon", hour=8, minute=0, timezone="UTC")


def schedule_project(project: Project):
    """(Re)register one project's cron. No-op until the scheduler has started."""
    if not scheduler.running:
        return
    scheduler.add_job(
        _scheduled_run, _trigger_for(project), args=[project.id],
        id=f"brief-{project.slug}", replace_existing=True,
    )
    cadence = (project.config.get("newsletter") or {}).get("cadence", "weekly")
    logger.info("scheduled %s brief for %s", cadence, project.slug)


def unschedule_project(slug: str):
    job_id = f"brief-{slug}"
    if scheduler.running and scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def schedule_all():
    """Register every project at startup."""
    db = SessionLocal()
    try:
        for project in db.scalars(select(Project)):
            scheduler.add_job(
                _scheduled_run, _trigger_for(project), args=[project.id],
                id=f"brief-{project.slug}", replace_existing=True,
            )
            cadence = (project.config.get("newsletter") or {}).get("cadence", "weekly")
            logger.info("scheduled %s brief for %s", cadence, project.slug)
    finally:
        db.close()
