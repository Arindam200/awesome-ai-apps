"""Run after completing the exercise; these checks fail for the starter code."""

from datetime import datetime, timedelta, timezone

from webhook_ledger import WebhookLedger


def main() -> None:
    ledger = WebhookLedger()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert ledger.apply("evt-1", 500, start) == 500
    assert ledger.apply("evt-1", 500, start + timedelta(hours=1)) == 500
    assert ledger.total_cents == 500

    try:
        ledger.apply("evt-1", 900, start + timedelta(days=1))
    except ValueError:
        pass
    else:
        raise AssertionError("Changing the amount inside seven days must fail")

    assert ledger.apply("evt-2", 200, start + timedelta(days=2)) == 700
    assert ledger.apply("evt-1", 500, start + timedelta(days=7)) == 1200
    assert ledger.total_cents == 1200
    print("Webhook ledger contract passed")


if __name__ == "__main__":
    main()
