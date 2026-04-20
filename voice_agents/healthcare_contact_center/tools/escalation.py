"""Human-bridge escalation stub: logs the event instead of bridging a real call."""

from datetime import datetime

from loguru import logger


def escalate_to_human(reason: str, urgency: str = "normal", summary: str = "") -> dict[str, str]:
    ticket = f"ESC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    logger.warning(
        f"[ESCALATION] ticket={ticket} urgency={urgency} reason={reason!r} summary={summary!r}"
    )
    return {
        "ticket": ticket,
        "status": "logged",
        "message": (
            "A supervisor has been paged and will join shortly. "
            "In a real deployment this would bridge the call to a live operator."
        ),
    }
