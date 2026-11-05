"""Deliberately incomplete starter for the cross-harness handoff exercise."""

from datetime import datetime


class WebhookLedger:
    def __init__(self) -> None:
        self.total_cents = 0

    def apply(self, event_id: str, amount_cents: int, now: datetime) -> int:
        """Apply a webhook charge; the seven-day idempotency rule is still open work."""
        self.total_cents += amount_cents
        return self.total_cents
