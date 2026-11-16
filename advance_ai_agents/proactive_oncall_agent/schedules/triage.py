"""Smart triage: every 5 minutes, scan the event stream and act only on what matters.

Port to Managed Deep Agents by swapping the import for
`from managed_deepagents import define_schedule` (drop `metadata`, which is a
local extra).
"""

from cron import define_schedule

schedule = define_schedule(
    cron="*/5 * * * *",
    prompt=(
        "Triage the event stream. Call get_new_events, look into whatever might "
        "affect customers, and act only on what needs it. If nothing needs "
        "attention, say so and do nothing else."
    ),
    # Local extra: marks this as the triage schedule. The runtime skips the run
    # without calling the model when no new events arrived since the last
    # triage, and marks events as read once a triage run finishes.
    metadata={"triage": True},
)
