import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Brief, Project

logger = logging.getLogger(__name__)

RESEND_API = "https://api.resend.com/emails"


def build_subject(project: Project, brief: Brief, override: str | None = None) -> str:
    if override:
        return override[:200]
    newsletter = project.config.get("newsletter") or {}
    prefix = newsletter.get("subject_prefix", "Maintainer Brief")
    headline = (brief.brief_json or {}).get("headline", project.name)
    return f"{prefix}: {headline}"[:200]


def send_brief(
    db: Session,
    project: Project,
    brief: Brief,
    *,
    recipients: list[str] | None = None,
    subject: str | None = None,
    from_name: str | None = None,
    html: str | None = None,
    test: bool = False,
    record: bool = True,
) -> dict:
    """Send a brief via Resend.

    Overrides default to the project's newsletter config. `test=True` sends only
    to the first recipient. `record=False` skips writing sent_at/resend_id (used
    for test sends). Returns {sent_to, resend_id}.
    """
    newsletter = project.config.get("newsletter") or {}
    to = recipients if recipients is not None else (newsletter.get("recipients") or [])
    if test and to:
        to = to[:1]
    if not to:
        raise ValueError("no recipients")
    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY not configured")

    sender = settings.newsletter_from
    if from_name:
        # newsletter_from looks like "Name <addr>"; swap the display name, keep the address
        addr = sender.split("<")[-1].rstrip(">") if "<" in sender else sender
        sender = f"{from_name} <{addr}>"

    resp = httpx.post(
        RESEND_API,
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": sender,
            "to": to,
            "subject": build_subject(project, brief, subject),
            "html": html if html is not None else brief.html,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    resend_id = resp.json().get("id")
    if record and not test:
        brief.resend_id = resend_id
        brief.sent_at = datetime.now(timezone.utc)
        db.commit()
    logger.info("brief %s sent to %s (test=%s, resend id %s)", brief.id, to, test, resend_id)
    return {"sent_to": to, "resend_id": resend_id, "test": test}
