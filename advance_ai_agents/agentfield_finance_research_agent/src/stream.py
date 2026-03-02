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
from src.schemas import (
    AnalystFinding,
    ResearchPlan,
    ResearchReport,
    RiskAssessment,
)
from src.skills import (
    get_analyst_targets,
    get_balance_sheet,
    get_cash_flow_statement,
    get_company_facts,
    get_income_statement,
    get_insider_transactions,
    search_market_news,
    validate_ticker,
)

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
# Streaming research pipeline (mirrors reasoners.py but emits SSE events)
# ---------------------------------------------------------------------------

def _json(obj) -> str:
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump(), default=str, indent=2)
    return json.dumps(obj, default=str, indent=2)


async def _run_pipeline(query: str):
    """Full 4-agent pipeline that emits SSE events as it runs."""

    # ── Manager: create research plan ──────────────────────────────────────
    await emit("agent_start", "manager", {"message": f'Decomposing query: "{query}"'})

    plan: ResearchPlan = await app.ai(
        system=(
            "You are the head of research at an investment committee. "
            "Decompose the user's question into a structured research plan. "
            "Extract the ticker symbol and company name, generate 3-4 hypotheses, "
            "list specific data needs, and identify 3-5 focus areas."
        ),
        user=f"User query: {query}\n\nCreate a ResearchPlan.",
        schema=ResearchPlan,
    )

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

    # ── Analyst + Contrarian: PARALLEL execution (asyncio.gather) ─────────
    # Both LLM calls are dispatched concurrently — they do NOT wait for each other.
    # Timeline:
    #   1. Both agent_start events fire (cards glow simultaneously)
    #   2. yfinance data fetch runs (shared, parallel across 5 endpoints)
    #   3. run_analyst() and run_contrarian() sent to asyncio.gather → true concurrency
    #   4. Whichever finishes first emits agent_complete; the other follows shortly after
    await emit("agent_start", "analyst", {"message": f"Pulling financials for {plan.ticker}..."})
    await emit("agent_start", "contrarian", {"message": f"Scanning risks for {plan.ticker}..."})

    # Fetch all data in parallel: annual + quarterly financials, targets, insider activity
    income, income_q, balance, cashflow, cashflow_q, facts, news, analyst_targets, insiders = await asyncio.gather(
        get_income_statement(plan.ticker, "annual"),
        get_income_statement(plan.ticker, "quarterly"),
        get_balance_sheet(plan.ticker, "annual"),
        get_cash_flow_statement(plan.ticker, "annual"),
        get_cash_flow_statement(plan.ticker, "quarterly"),
        get_company_facts(plan.ticker),
        search_market_news(plan.ticker, limit=20),
        get_analyst_targets(plan.ticker),
        get_insider_transactions(plan.ticker, limit=10),
    )

    await emit("agent_note", "analyst", {
        "message": "Financial data loaded",
        "detail": f"Annual periods: {len(income)} | Quarterly: {len(income_q)} | News: {len(news)} | Analyst targets: {'yes' if analyst_targets else 'no'}"
    })

    # Run analyst and contrarian in parallel (contrarian gets plan + will critique analyst)
    async def run_analyst():
        finding: AnalystFinding = await app.ai(
            system=(
                "You are a senior equity research analyst building the BULL CASE. "
                "First, populate reasoning_steps with your step-by-step analysis: what the data shows, "
                "which metrics are most compelling, what narrative you are building and why. "
                "Then write the full bull_case thesis using those insights. "
                "Be specific: cite actual numbers."
            ),
            user=(
                f"Ticker: {plan.ticker} ({plan.company_name})\n\n"
                f"=== RESEARCH PLAN ===\n{_json(plan)}\n\n"
                f"=== ANALYST PRICE TARGETS & CONSENSUS ===\n{_json(analyst_targets)}\n\n"
                f"=== INSIDER TRANSACTIONS ===\n{_json(insiders)}\n\n"
                f"=== COMPANY FACTS ===\n{_json(facts)}\n\n"
                f"=== INCOME STATEMENT (ANNUAL) ===\n{_json(income)}\n\n"
                f"=== INCOME STATEMENT (QUARTERLY, last 4 quarters) ===\n{_json(income_q)}\n\n"
                f"=== BALANCE SHEET ===\n{_json(balance)}\n\n"
                f"=== CASH FLOW ===\n{_json(cashflow)}\n\n"
                f"=== NEWS (20 articles) ===\n{_json(news)}\n\n"
                f"Build a rigorous AnalystFinding. Focus on: {', '.join(plan.focus_areas)}"
            ),
            schema=AnalystFinding,
        )
        await emit("agent_complete", "analyst", {
            "bull_case": finding.bull_case,
            "key_metrics": finding.key_metrics,
            "data_quality": finding.data_quality,
            "reasoning_steps": finding.reasoning_steps,
        })
        return finding

    async def run_contrarian():
        risk_keywords = [
            "risk", "lawsuit", "antitrust", "fine", "fail", "miss", "decline",
            "competition", "warn", "short", "bear", "downgrade", "probe", "loss"
        ]
        # Filter from 20 articles; fallback to first 8 if no matches
        risk_news = [
            n for n in news
            if any(kw in (n.get("title", "") + n.get("summary", "")).lower() for kw in risk_keywords)
        ] or news[:8]

        await emit("agent_note", "contrarian", {
            "message": f"Found {len(risk_news)} risk-relevant news articles"
        })

        assessment: RiskAssessment = await app.ai(
            system=(
                "You are a short-seller and risk manager. "
                "First, populate reasoning_steps with your thinking: which parts of the bull case "
                "look overstated, what risks you identified and why they matter, how you weighed severity. "
                "Then write the bear_case using those conclusions. "
                "Be specific with numbers. Identify regulatory, competitive, valuation, and macro risks."
            ),
            user=(
                f"Ticker: {plan.ticker} ({plan.company_name})\n\n"
                f"=== RESEARCH PLAN ===\n{_json(plan)}\n\n"
                f"=== ANALYST PRICE TARGETS (wall street consensus) ===\n{_json(analyst_targets)}\n\n"
                f"=== INSIDER TRANSACTIONS ===\n{_json(insiders)}\n\n"
                f"=== RISK-FOCUSED NEWS ({len(risk_news)} articles) ===\n{_json(risk_news)}\n\n"
                f"=== COMPANY FACTS ===\n{_json(facts)}\n\n"
                f"Provide a thorough RiskAssessment. Focus on: {', '.join(plan.focus_areas)}"
            ),
            schema=RiskAssessment,
        )
        await emit("agent_complete", "contrarian", {
            "bear_case": assessment.bear_case,
            "risks": assessment.risks,
            "severity": assessment.severity,
            "reasoning_steps": assessment.reasoning_steps,
        })
        return assessment

    analyst_finding, risk_assessment = await asyncio.gather(run_analyst(), run_contrarian())

    # ── Editors (Short Term + Long Term): PARALLEL ───────────────────────────
    # Both editors fire concurrently after Analyst + Contrarian complete.
    # Short-term focuses on catalysts / momentum / near-term factors;
    # Long-term focuses on moat / balance sheet / secular trends.
    CONFIDENCE_GUIDE = (
        "Confidence scoring — use this scale strictly: "
        "85-100 = overwhelming evidence, minimal counter-case; "
        "65-80 = clear lean, meaningful uncertainty exists; "
        "50-65 = genuinely balanced, could go either way; "
        "<50 = too uncertain to have strong conviction."
    )

    await emit("agent_start", "editor_short", {"message": "Synthesising short-term (1–6 month) case..."})
    await emit("agent_start", "editor_long",  {"message": "Synthesising long-term (1–5 year) case..."})

    async def run_editor_short():
        report: ResearchReport = await app.ai(
            system=(
                "You are a short-term investment analyst (1–6 month horizon). "
                "First, populate reasoning_steps with your deliberation: which near-term catalysts "
                "or risks dominated your thinking, and why you chose this verdict. "
                "Focus ONLY on near-term factors: upcoming earnings, analyst price targets, "
                "news sentiment, technical momentum, insider activity, macro events in the next 6 months. "
                "Ignore long-term structural factors — they are irrelevant here. "
                f"{CONFIDENCE_GUIDE} "
                "Set time_horizon='short_term'. "
                "Arrive at a BUY/HOLD/SELL for the NEXT 1–6 MONTHS."
            ),
            user=(
                f"Ticker: {plan.ticker} ({plan.company_name})\n\n"
                f"=== ANALYST PRICE TARGETS & CONSENSUS ===\n{_json(analyst_targets)}\n\n"
                f"=== INSIDER TRANSACTIONS ===\n{_json(insiders)}\n\n"
                f"=== QUARTERLY INCOME (last 4 quarters — short-term trend) ===\n{_json(income_q)}\n\n"
                f"=== QUARTERLY CASH FLOW ===\n{_json(cashflow_q)}\n\n"
                f"=== ANALYST FINDING (BULL) ===\n{_json(analyst_finding)}\n\n"
                f"=== RISK ASSESSMENT (BEAR) ===\n{_json(risk_assessment)}\n\n"
                "Synthesise a SHORT-TERM ResearchReport (time_horizon='short_term')."
            ),
            schema=ResearchReport,
            model="nebius/openai/gpt-oss-20b",
        )
        await emit("agent_complete", "editor_short", {
            "summary": report.summary,
            "verdict": report.verdict,
            "confidence": report.confidence,
            "reasoning_steps": report.reasoning_steps,
        })
        return report

    async def run_editor_long():
        report: ResearchReport = await app.ai(
            system=(
                "You are a long-term investment analyst (1–5 year horizon). "
                "First, populate reasoning_steps with your deliberation: which structural "
                "advantages or risks dominated your thinking, and why you chose this verdict. "
                "Focus ONLY on long-term factors: competitive moat, revenue growth trajectory, "
                "balance sheet strength, management quality, industry tailwinds/headwinds, "
                "valuation vs intrinsic value over 5 years. "
                "Ignore short-term noise — it is irrelevant here. "
                f"{CONFIDENCE_GUIDE} "
                "Set time_horizon='long_term'. "
                "Arrive at a BUY/HOLD/SELL for the NEXT 1–5 YEARS."
            ),
            user=(
                f"Ticker: {plan.ticker} ({plan.company_name})\n\n"
                f"=== ANALYST PRICE TARGETS & CONSENSUS ===\n{_json(analyst_targets)}\n\n"
                f"=== INSIDER TRANSACTIONS ===\n{_json(insiders)}\n\n"
                f"=== ANALYST FINDING (BULL) ===\n{_json(analyst_finding)}\n\n"
                f"=== RISK ASSESSMENT (BEAR) ===\n{_json(risk_assessment)}\n\n"
                f"=== COMPANY FACTS ===\n{_json(facts)}\n\n"
                "Synthesise a LONG-TERM ResearchReport (time_horizon='long_term')."
            ),
            schema=ResearchReport,
            model="nebius/openai/gpt-oss-20b",
        )
        await emit("agent_complete", "editor_long", {
            "summary": report.summary,
            "verdict": report.verdict,
            "confidence": report.confidence,
            "reasoning_steps": report.reasoning_steps,
        })
        return report

    short_report, long_report = await asyncio.gather(run_editor_short(), run_editor_long())

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
