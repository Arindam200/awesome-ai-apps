"""End-of-shift handoff and memory consolidation.

The demo shift runs 09:00-09:47 on a simulated clock. For a real rotation use
something like cron="0 17 * * 1-5".
"""

from cron import define_schedule

schedule = define_schedule(
    cron="47 9 * * *",
    prompt=(
        "Your shift is ending. Send the handoff for the next on-call human as one "
        "notify(level='fyi', title='Shift handoff', ...): incidents opened and "
        "resolved, anything still being watched, and recommended next steps. "
        "Then save up to three durable lessons from this shift with remember, "
        "skipping anything already in long-term memory."
    ),
)
