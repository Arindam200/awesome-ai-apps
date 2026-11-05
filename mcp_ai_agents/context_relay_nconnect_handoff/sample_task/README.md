# A small task to hand off

This **exercise fixture** is deliberately incomplete. Copy this directory to a fresh scratch folder, then register that folder with Context Relay. Do not solve the task in this collection's checkout.

```sh
cp -R sample_task /tmp/relay-webhook-lab
cd /tmp/relay-webhook-lab
python3 verify.py  # fails until the idempotency rule is implemented
```

The starter `WebhookLedger.apply(event_id, amount_cents, now)` adds a charge every time it sees a webhook. Implement these rules:

1. The first event adds its amount to `total_cents` and returns the new total.
2. A repeat of the same event ID **before seven days** passes does not charge again and returns the original result.
3. A repeat with a different amount inside that window raises `ValueError`.
4. At exactly seven days after the first event, the ID can be charged again.

`now` is supplied by the caller so the exercise is deterministic. Keep the state in memory; this is a focused handoff exercise, not a payment system.

Suggested Claude Code starting prompt:

> Read `README.md`, `webhook_ledger.py` and `verify.py`. Do not edit files. Design the seven-day idempotency fix, state the currently failing assertion and leave the implementation steps for another coding agent.

Capture the Claude session in Relay, review and offer its checkpoint to Codex, then ask Codex through NConnect to finish the remaining rules and run `python3 verify.py`. The handoff should carry the seven-day rule and the still-failing checks, rather than a pasted transcript.
