from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Brief, Project, Signal

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)


ALL_SECTIONS = ["triage", "ship_it", "people", "worth_replying_to"]


def section_flags(project: Project) -> dict:
    """Which brief sections to include — defaults to all on."""
    configured = ((project.config.get("newsletter") or {}).get("sections")) or {}
    return {s: configured.get(s, True) for s in ALL_SECTIONS}


def render_brief_html(db: Session, project: Project, brief: Brief, subject: str | None = None) -> str:
    signal_count = db.scalar(
        select(func.count(Signal.id)).where(
            Signal.project_id == project.id,
            Signal.observed_at >= brief.period_start,
            Signal.observed_at < brief.period_end,
        )
    )
    template = _env.get_template("brief.html.j2")
    return template.render(
        project_name=project.name,
        brief=brief.brief_json,
        sections=section_flags(project),
        period_start=brief.period_start.strftime("%b %d, %Y"),
        period_end=brief.period_end.strftime("%b %d, %Y"),
        signal_count=signal_count or 0,
        app_url=settings.app_url.rstrip("/"),
    )
