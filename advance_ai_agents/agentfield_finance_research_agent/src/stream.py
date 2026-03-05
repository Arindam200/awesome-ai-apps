"""
stream.py — Server-Sent Events (SSE) streaming for the Argus UI.

Adds raw FastAPI routes to the AgentField app:
  GET  /          → serves the single-page frontend
  POST /research/stream/start       → starts a session, returns session_id
  GET  /research/stream/events/{id} → streams SSE events

Event types:
  agent_start    — an agent has started working
  agent_note     — a progress log from inside an agent
  agent_complete — an agent has finished, with its structured output
  error          — something went wrong
  complete       — both ResearchReports (short + long term) are ready

Agent identifiers used in events:
  manager, analyst, contrarian, editor_short, editor_long

All LLM calls are routed through @app.reasoner() decorated functions from
reasoners.py, giving the AgentField control plane automatic execution tracking.
"""
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from src import app
from src.reasoners import (
    create_plan,
    conduct_research,
    assess_risks,
    editor_short_term,
    editor_long_term,
)
from src.skills import validate_ticker

# ---------------------------------------------------------------------------
# Event bus: one asyncio.Queue per active request, keyed by session_id
# ---------------------------------------------------------------------------

_sessions: dict[str, asyncio.Queue] = {}
_current_queue: ContextVar[asyncio.Queue | None] = ContextVar("_current_queue", default=None)


def _get_queue() -> asyncio.Queue | None:
    return _current_queue.get()


async def emit(event_type: str, agent: str, data: dict | str | None = None):
    """Push an SSE event onto the current request's queue."""
    q = _get_queue()
    if q:
        payload = {"type": event_type, "agent": agent, "data": data or {}}
        await q.put(payload)


def _sse_format(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


async def _event_generator(session_id: str) -> AsyncGenerator[str, None]:
    q = _sessions.get(session_id)
    if not q:
        yield _sse_format({"type": "error", "agent": "system", "data": {"message": "Session not found"}})
        return

    while True:
        try:
            event = await asyncio.wait_for(q.get(), timeout=300)
            yield _sse_format(event)
            if event.get("type") in ("complete", "error"):
                break
        except asyncio.TimeoutError:
            yield _sse_format({"type": "error", "agent": "system", "data": {"message": "Request timed out"}})
            break

    _sessions.pop(session_id, None)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _json(obj) -> str:
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump(), default=str, indent=2)
    return json.dumps(obj, default=str, indent=2)


# ---------------------------------------------------------------------------
# Streaming research pipeline — calls @app.reasoner() functions for tracking
# ---------------------------------------------------------------------------

async def _run_pipeline(query: str):
    """Full 5-agent pipeline that emits SSE events as it runs.

    Each LLM step calls a @app.reasoner() decorated function from reasoners.py,
    so the AgentField control plane automatically tracks all executions.
    """

    # ── Manager: create research plan (tracked via @app.reasoner) ──────────
    await emit("agent_start", "manager", {"message": f'Decomposing query: "{query}"'})

    plan = await create_plan(query)

    await emit("agent_note", "manager", {
        "message": f"Plan created for {plan.ticker} ({plan.company_name})",
        "detail": f"Hypotheses: {len(plan.hypotheses)} | Focus: {', '.join(plan.focus_areas[:3])}"
    })
    await emit("agent_complete", "manager", {
        "ticker": plan.ticker,
        "company_name": plan.company_name,
        "hypotheses": plan.hypotheses,
        "focus_areas": plan.focus_areas,
        "reasoning_steps": plan.reasoning_steps,
    })

    # ── Ticker validation: early exit if not actively tradable ────────────
    await emit("agent_note", "manager", {"message": f"Validating {plan.ticker} on yfinance..."})
    ticker_check = await validate_ticker(plan.ticker)
    if not ticker_check.get("valid"):
        reason = ticker_check.get("reason", "Ticker not found.")
        await emit("error", "system", {
            "message": (
                f"Cannot analyse {plan.ticker}: {reason} "
                "Please use a real, actively traded stock ticker (e.g. AAPL, NVDA, MSFT)."
            )
        })
        return

    await emit("agent_note", "manager", {
        "message": f"{plan.ticker} validated — {ticker_check.get('quote_type', 'EQUITY')} "
                   f"trading at ${ticker_check.get('current_price')} on {ticker_check.get('exchange', 'unknown exchange')}"
    })

    # ── Analyst + Contrarian: PARALLEL (both tracked via @app.reasoner) ──
    await emit("agent_start", "analyst", {"message": f"Pulling financials for {plan.ticker}..."})
    await emit("agent_start", "contrarian", {"message": f"Scanning risks for {plan.ticker}..."})

    analyst_finding, risk_assessment = await asyncio.gather(
        conduct_research(plan),
        assess_risks(plan),
    )

    await emit("agent_complete", "analyst", {
        "bull_case": analyst_finding.bull_case,
        "key_metrics": analyst_finding.key_metrics,
        "data_quality": analyst_finding.data_quality,
        "reasoning_steps": analyst_finding.reasoning_steps,
    })

    await emit("agent_complete", "contrarian", {
        "bear_case": risk_assessment.bear_case,
        "risks": risk_assessment.risks,
        "severity": risk_assessment.severity,
        "reasoning_steps": risk_assessment.reasoning_steps,
    })

    # ── Editors (Short Term + Long Term): PARALLEL (both tracked) ─────────
    await emit("agent_start", "editor_short", {"message": "Synthesising short-term (1–6 month) case..."})
    await emit("agent_start", "editor_long",  {"message": "Synthesising long-term (1–5 year) case..."})

    short_report, long_report = await asyncio.gather(
        editor_short_term(plan, analyst_finding, risk_assessment),
        editor_long_term(plan, analyst_finding, risk_assessment),
    )

    await emit("agent_complete", "editor_short", {
        "summary": short_report.summary,
        "verdict": short_report.verdict,
        "confidence": short_report.confidence,
        "reasoning_steps": short_report.reasoning_steps,
    })
    await emit("agent_complete", "editor_long", {
        "summary": long_report.summary,
        "verdict": long_report.verdict,
        "confidence": long_report.confidence,
        "reasoning_steps": long_report.reasoning_steps,
    })

    await emit("complete", "system", {
        "short_term": short_report.model_dump(),
        "long_term":  long_report.model_dump(),
    })


# ---------------------------------------------------------------------------
# Raw FastAPI routes added directly to the Agent (which is a FastAPI subclass)
# ---------------------------------------------------------------------------

class StreamQuery(BaseModel):
    query: str


@app.post("/research/stream/start")
async def start_stream(body: StreamQuery):
    """Start a streaming research session. Returns a session_id."""
    session_id = str(uuid.uuid4())
    _sessions[session_id] = asyncio.Queue()
    # Run pipeline in background, bound to this session's queue
    token = _current_queue.set(_sessions[session_id])

    async def run():
        try:
            _current_queue.set(_sessions.get(session_id))
            await _run_pipeline(body.query)
        except Exception as e:
            q = _sessions.get(session_id)
            if q:
                await q.put({"type": "error", "agent": "system", "data": {"message": str(e)}})

    asyncio.create_task(run())
    _current_queue.reset(token)
    return {"session_id": session_id}


@app.get("/research/stream/events/{session_id}")
async def stream_events(session_id: str):
    """SSE endpoint — streams events for a given session."""
    return StreamingResponse(
        _event_generator(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the Argus UI."""
    ui_path = Path(__file__).parent.parent / "ui" / "index.html"
    return HTMLResponse(content=ui_path.read_text())
