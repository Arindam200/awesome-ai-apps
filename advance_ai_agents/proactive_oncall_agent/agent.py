"""The on-call agent: Kimi K3.1 Pro on Nebius Token Factory, built with LangChain `create_agent`.

Nobody chats with this agent. Every run starts from a schedule firing, and the
user message only says which schedule fired and why. The agent then decides
for itself what to look at, whether anyone needs to hear about it, and when it
should wake up again.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Literal

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from cron import CronServer
from desk import Desk, Memory
from world import SERVICES, World

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "moonshotai/Kimi-K3.1-Pro"


# ---- run bookkeeping ---------------------------------------------------------
@dataclass
class Step:
    tool: str
    args: dict
    call_id: str = ""
    result: str = ""


@dataclass
class RunRecord:
    id: str
    at: datetime
    schedule_id: str
    kind: str  # static | follow-up | recurring
    prompt: str
    thread_id: str = ""
    status: str = "running"  # running | done | skipped | error
    steps: list[Step] = field(default_factory=list)
    summary: str = ""
    tokens: int = 0
    seconds: float = 0.0


@dataclass
class OnCallContext:
    """What the tools reach through `runtime.context` (like `runtime.schedules` in Managed Deep Agents)."""

    world: World
    cron: CronServer
    desk: Desk
    memory: Memory
    run: RunRecord


Runtime = ToolRuntime[OnCallContext]


def _err(e: Exception) -> str:
    return f"Error: {e}"


# ---- observe -------------------------------------------------------------------
@tool
def get_new_events(runtime: Runtime) -> str:
    """Events since the last triage run: deploys, rollbacks, monitoring alerts, team chat, support tickets,
    payments-provider status posts and rollback approval decisions. Oldest first."""
    events = runtime.context.world.unread()
    if not events:
        return "No new events since the last triage."
    return "\n".join(e.line() for e in events)


@tool
def get_metrics(service: str, runtime: Runtime, minutes: int = 15) -> str:
    """Per-minute metrics for a service over the last `minutes` (max 60).
    checkout-api: requests/s, 5xx %, p95 latency. orders-db: disk usage and trend."""
    return runtime.context.world.metrics_report(service, minutes)


@tool
def get_deploy_history(service: str, runtime: Runtime) -> str:
    """Recent deploys and rollbacks for a service, newest first, with author and change description."""
    return runtime.context.world.deploy_history(service)


# ---- act -------------------------------------------------------------------------
@tool
def notify(level: Literal["page", "warn", "fyi"], title: str, message: str, runtime: Runtime) -> str:
    """Send a message to the human on call. `page` wakes them up now: customers are affected or about to be.
    `warn` needs attention today. `fyi` needs no action. Keep it short and specific: what, impact, evidence,
    what you did, what you need from them. Plain text, no markdown. Don't notify about noise, and don't repeat
    what you already told them (see "Messages you sent" in your situation) unless something changed."""
    ctx = runtime.context
    ctx.desk.notify(ctx.world.now, level, title, message, ctx.run.id)
    return f"Sent ({level})."


@tool
def request_rollback(service: str, to_version: str, reason: str, runtime: Runtime) -> str:
    """Ask the human on call to approve rolling `service` back to `to_version`. You can't deploy or roll back
    yourself: this puts an Approve/Deny request on their phone. Their decision shows up as an `approval`
    event, and an approved rollback runs a minute later. Only use it when a recent deploy of that service
    is the likely cause, not for problems outside the service."""
    ctx = runtime.context
    try:
        a = ctx.world.request_rollback(service, to_version, reason, ctx.run.id)
    except ValueError as e:
        return _err(e)
    return f"{a.id} created: waiting for the human to approve rolling back {service} {a.from_version} -> {to_version}."


# ---- incidents (working memory shared by all runs) ----------------------------------
@tool
def open_incident(
    service: Literal["checkout-api", "orders-db", "search-api", "payments-provider"],
    title: str,
    severity: Literal["sev1", "sev2", "sev3"],
    summary: str,
    runtime: Runtime,
) -> str:
    """Open an incident for customer-facing or about-to-be customer-facing trouble on one service. sev1: checkout
    down or payments failing broadly. sev2: degraded for many customers. sev3: contained or at risk. A service has
    at most one open incident: if one is open, update it instead."""
    ctx = runtime.context
    try:
        inc = ctx.desk.open_incident(ctx.world.now, service, title, severity, summary, ctx.run.id)
    except ValueError as e:
        return _err(e)
    return f"Opened {inc.id}."


@tool
def update_incident(incident_id: str, note: str, runtime: Runtime) -> str:
    """Add a timestamped note to an open incident: new evidence, actions taken, current status."""
    ctx = runtime.context
    try:
        inc = ctx.desk.update_incident(ctx.world.now, incident_id, note)
    except ValueError as e:
        return _err(e)
    return f"Updated {inc.id}."


@tool
def resolve_incident(incident_id: str, summary: str, runtime: Runtime) -> str:
    """Resolve an incident once metrics have been back at baseline for a few minutes. `summary`: cause,
    customer impact window, fix, follow-ups for the humans."""
    ctx = runtime.context
    try:
        inc = ctx.desk.resolve_incident(ctx.world.now, incident_id, summary)
    except ValueError as e:
        return _err(e)
    return f"Resolved {inc.id}."


# ---- schedule yourself ------------------------------------------------------------
@tool
def follow_up_in(minutes: int, prompt: str, runtime: Runtime) -> str:
    """Wake yourself up once, `minutes` from now (1-240), continuing this same conversation. Write `prompt`
    as instructions to your future self: what to check, and what to do for each outcome."""
    ctx = runtime.context
    if not 1 <= minutes <= 240:
        return "Error: minutes must be between 1 and 240."
    try:
        sch = ctx.cron.create(
            now=ctx.world.now,
            at=ctx.world.now + timedelta(minutes=minutes),
            prompt=prompt,
            thread_id=ctx.run.thread_id,
            created_by=ctx.run.id,
        )
    except ValueError as e:
        return _err(e)
    return f"Scheduled {sch.id} for {sch.next_run:%H:%M}."


@tool
def schedule_recurring(cron: str, prompt: str, runtime: Runtime) -> str:
    """Wake yourself up on a recurring 5-field cron schedule (for example '*/10 * * * *'), each run in a
    fresh conversation. Use it for a watch that outlives this incident, like a slowly filling disk, and cancel
    it once it's no longer needed. `prompt` must say what to check and when to cancel."""
    ctx = runtime.context
    try:
        sch = ctx.cron.create(now=ctx.world.now, cron=cron, prompt=prompt, created_by=ctx.run.id)
    except ValueError as e:
        return _err(e)
    return f"Scheduled {sch.id} ({cron}), first run {sch.next_run:%H:%M}."


@tool
def list_schedules(runtime: Runtime) -> str:
    """All active schedules: the static ones from schedules/ and the ones you created."""
    return "\n".join(s.describe() for s in runtime.context.cron.active()) or "No active schedules."


@tool
def cancel_schedule(schedule_id: str, runtime: Runtime) -> str:
    """Cancel a follow-up or recurring schedule you created, once it's no longer needed."""
    ctx = runtime.context
    try:
        sch = ctx.cron.cancel(schedule_id.strip(), by=ctx.run.id)
    except ValueError as e:
        return _err(e)
    return f"Cancelled {sch.id}."


# ---- long-term memory ----------------------------------------------------------------
@tool
def remember(note: str, runtime: Runtime) -> str:
    """Save one durable lesson to long-term memory, loaded into every future run, for example
    'checkout-api v2.14.0 (payment retry policy) caused payment timeouts; rollback to v2.13.2 fixed it'.
    Not for status updates."""
    ctx = runtime.context
    return "Saved." if ctx.memory.add(ctx.world.now, note) else "Already in memory."


TOOLS = [
    get_new_events,
    get_metrics,
    get_deploy_history,
    notify,
    request_rollback,
    open_incident,
    update_incident,
    resolve_incident,
    follow_up_in,
    schedule_recurring,
    list_schedules,
    cancel_schedule,
    remember,
]


# ---- prompt ------------------------------------------------------------------------
SYSTEM_PROMPT = """You are the on-call agent for the checkout team of a small online store. Nobody chats with you. \
A cron server wakes you up: on a fixed schedule to triage the event stream, or at times you chose yourself with \
follow_up_in or schedule_recurring. The first message of each run says why you're awake.

How to work:
1. Look before you act. Fetch fresh data with tools in every run. Anything from earlier messages is stale. Never \
state a number you didn't fetch in this run.
2. Most events are noise: chatter, healthy deploys, one-off blips that already recovered. Do nothing about them. \
A quiet run that ends in "nothing needs attention" is a good run.
3. Act in proportion:
   - Customers affected now (checkout 5xx or latency well above baseline): open an incident, page the human with \
the evidence, and find the likely cause.
   - If a recent deploy of that service is the likely cause, request_rollback to the last good version. A human \
approves it; you can't roll back yourself.
   - If the cause is outside our control (the payments provider status page reports trouble), don't roll back. \
Page, explain, and keep watching.
   - Slow-burning risks (a disk filling up): warn, and set a recurring watch that you cancel once it's stable.
4. Close your loops. Whenever you leave something unresolved, schedule a follow-up for when it's worth checking \
again (2-5 minutes during an active incident). On a follow-up, re-check, then update or resolve the incident, \
tell the human what changed if it matters to them, and schedule another follow-up only if still needed.
5. Don't repeat yourself. Before opening, paging or requesting anything, check the situation below for open \
incidents, pending approvals and your schedules. Update the existing incident instead. Cancel schedules you no \
longer need.
6. Save durable lessons with remember: which change broke what, and what fixed it.
7. End every run with one or two plain sentences saying what you saw and what you did. No heading, no markdown.

Times are shown as HH:MM on today's date."""


def render_situation(ctx: OnCallContext) -> str:
    w, now = ctx.world, ctx.world.now
    incidents = [i.describe() for i in ctx.desk.incidents if i.status == "open"]
    resolved = [i.describe() for i in ctx.desk.incidents if i.status == "resolved"][-3:]
    approvals = [a.describe() for a in w.approvals][-4:]
    sent = [f"{n.at:%H:%M} {n.level}: {n.title}" for n in ctx.desk.notifications][-6:]
    schedules = [s.describe() for s in ctx.cron.active()]
    services = [
        f"- {name}: {desc}. " + (f"Running {w.current(name).version}." if name in w.deploys else "")
        for name, desc in SERVICES.items()
    ]

    def block(items: list[str], empty: str) -> str:
        return "\n".join(f"- {x}" for x in items) if items else empty

    return f"""## Situation at {now:%H:%M} ({now:%A})
You are in {ctx.run.id}, woken by schedule `{ctx.run.schedule_id}`.

### Services
{chr(10).join(services)}

### Open incidents
{block(incidents, "None.")}

### Recently resolved incidents
{block(resolved, "None.")}

### Rollback approvals
{block(approvals, "None.")}

### Messages you sent the human (latest first)
{block(sent[::-1], "None yet.")}

### Active schedules
{block(schedules, "None.")}

### Long-term memory
{block(ctx.memory.notes, "Empty.")}"""


@dynamic_prompt
def situation_prompt(request: ModelRequest) -> str:
    """Rebuilt before every model call, so the agent always sees the current state of the desk."""
    return SYSTEM_PROMPT + "\n\n" + render_situation(request.runtime.context)


def build_agent(model: str | None = None):
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        raise RuntimeError("NEBIUS_API_KEY is not set. Copy .env.example to .env and add your key.")
    llm = ChatOpenAI(
        model=model or os.getenv("NEBIUS_MODEL", DEFAULT_MODEL),
        base_url=NEBIUS_BASE_URL,
        api_key=api_key,
        reasoning_effort=os.getenv("REASONING_EFFORT", "medium"),
        timeout=120,
        max_retries=2,
    )
    return create_agent(
        llm,
        tools=TOOLS,
        middleware=[situation_prompt],
        context_schema=OnCallContext,
        checkpointer=InMemorySaver(),  # follow-ups continue the thread that set them
    )


def _text(msg: AIMessage) -> str:
    if isinstance(msg.content, str):
        return msg.content.strip()
    return "".join(p.get("text", "") for p in msg.content if isinstance(p, dict)).strip()


def run_agent(agent, ctx: OnCallContext, message: str, on_step: Callable[[str, Step], None] | None = None) -> None:
    """Run one wake-up to completion, recording every tool call on `ctx.run`."""
    rec = ctx.run
    pending: dict[str, Step] = {}
    t0 = time.time()
    try:
        stream = agent.stream(
            {"messages": [HumanMessage(message)]},
            config={"configurable": {"thread_id": rec.thread_id}, "recursion_limit": 40},
            context=ctx,
            stream_mode="updates",
        )
        for chunk in stream:
            for update in chunk.values():
                if not isinstance(update, dict):
                    continue
                for msg in update.get("messages", []):
                    if isinstance(msg, AIMessage):
                        rec.tokens += (msg.usage_metadata or {}).get("total_tokens", 0)
                        for tc in msg.tool_calls:
                            step = Step(tc["name"], tc["args"], tc.get("id") or "")
                            rec.steps.append(step)
                            pending[step.call_id] = step
                            if on_step:
                                on_step("tool", step)
                        if not msg.tool_calls and _text(msg):
                            rec.summary = _text(msg)
                    elif isinstance(msg, ToolMessage):
                        step = pending.pop(msg.tool_call_id, None)
                        if step:
                            step.result = str(msg.content)
                            if on_step:
                                on_step("result", step)
        rec.status = "done"
        rec.summary = rec.summary or "(no log line)"
    except Exception as e:  # keep the cron server alive; the run shows as failed
        rec.status = "error"
        rec.summary = f"{type(e).__name__}: {e}"
    finally:
        rec.seconds = time.time() - t0
