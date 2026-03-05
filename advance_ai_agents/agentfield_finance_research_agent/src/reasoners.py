"""
reasoners.py — The five-agent Investment Committee for Argus.

Agent roles:
  1. plan_research      → The Manager      (Adaptive Supervisor)
  2. conduct_research   → The Analyst      (Bull Case)
  3. assess_risks       → The Contrarian   (Bear Case)
  4. editor_short       → Short-Term View  (1–6 month horizon) ─┬─ parallel
  5. editor_long        → Long-Term View   (1–5 year horizon)  ─┘

NOTE: editors 4 & 5 live in stream.py and run only through the SSE pipeline
      (POST /research/stream/start → GET /research/stream/events/{id}).
      The reasoners in this file (analyst, contrarian, manager) are also
      exposed as standalone AgentField endpoints for direct API access.

Flow (streaming pipeline in stream.py):
  User Query
    ↓
  Manager ─ creates ResearchPlan
    ↓
  [asyncio.gather] yfinance data fetches (5 endpoints in parallel)
    ↓
  Analyst ─┬─ LLM calls dispatched concurrently via asyncio.gather
  Contrarian─┘
    ↓
  EditorShort ─┬─ also parallel via asyncio.gather
  EditorLong  ─┘
    ↓
  {short_term: ResearchReport, long_term: ResearchReport} → UI (tabbed)
"""
import asyncio
import json

from src import app
from src.schemas import (
    AnalystFinding,
    DualResearchReport,
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
# Helper
# ---------------------------------------------------------------------------

def _json(obj) -> str:
    """Compact JSON serialisation for passing data into app.ai() prompts."""
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump(), default=str, indent=2)
    return json.dumps(obj, default=str, indent=2)


CONFIDENCE_GUIDE = (
    "Confidence scoring — use this scale strictly: "
    "85-100 = overwhelming evidence, minimal counter-case; "
    "65-80 = clear lean, meaningful uncertainty exists; "
    "50-65 = genuinely balanced, could go either way; "
    "<50 = too uncertain to have strong conviction."
)


# ---------------------------------------------------------------------------
# Reasoner 0: The Manager's plan creation step (standalone)
# ---------------------------------------------------------------------------

@app.reasoner(path="/research/plan", tags=["committee"])
async def create_plan(query: str) -> ResearchPlan:
    """
    The Manager's first step: decompose a user query into a structured
    ResearchPlan. Extracted so stream.py can call it with workflow tracking.
    """
    app.note(f"[manager] Received research query: {query!r}", tags=["manager"])

    plan: ResearchPlan = await app.ai(
        system=(
            "You are the head of research at an investment committee. "
            "Your job is to decompose a user's investment question into a structured "
            "research plan. Extract the ticker symbol and company name from the query, "
            "generate 3-4 key hypotheses to investigate (mix of bull and bear), "
            "list the specific data points needed, and identify 3-5 focus areas for deep-dive. "
            "If no ticker is mentioned, infer the most likely one from context."
        ),
        user=f"User query: {query}\n\nCreate a ResearchPlan to investigate this question.",
        schema=ResearchPlan,
    )

    app.note(
        f"[manager] Research plan created for {plan.ticker} ({plan.company_name}). "
        f"Hypotheses: {len(plan.hypotheses)}, Focus areas: {plan.focus_areas}",
        tags=["manager", plan.ticker],
    )
    return plan


# ---------------------------------------------------------------------------
# Reasoner 4: The Editor — synthesizes final report (generic, single-report)
# ---------------------------------------------------------------------------

@app.reasoner(path="/research/editor", tags=["committee"])
async def synthesize_report(
    analyst_finding: AnalystFinding,
    risk_assessment: RiskAssessment,
) -> ResearchReport:
    """
    The Editor: synthesizes the Analyst's bull case and the Contrarian's bear
    case into a final, balanced investment research report with a clear verdict.
    Used for direct API access; the streaming pipeline uses the horizon-specific
    editors (editor_short_term / editor_long_term) instead.
    """
    app.note(
        f"[editor] Synthesizing report for {analyst_finding.ticker}",
        tags=["editor", analyst_finding.ticker],
    )

    report: ResearchReport = await app.ai(
        system=(
            "You are a senior investment analyst and editor at a top-tier research firm. "
            "Your job is to synthesize conflicting viewpoints from a Bull-case Analyst and a "
            "Bear-case Contrarian into a balanced, rigorous, and actionable research report. "
            "You must weigh both sides fairly, cite specific numbers, and arrive at a clear "
            "BUY / HOLD / SELL recommendation with a confidence score (0-100). "
            "Be intellectually honest — if evidence is mixed, say so."
        ),
        user=(
            f"Ticker: {analyst_finding.ticker}\n\n"
            f"=== ANALYST (BULL CASE) ===\n{_json(analyst_finding)}\n\n"
            f"=== CONTRARIAN (BEAR CASE) ===\n{_json(risk_assessment)}\n\n"
            "Synthesize these viewpoints into a final ResearchReport. "
            "The summary should be balanced; the verdict should reflect the weight of evidence."
        ),
        schema=ResearchReport,
    )

    app.note(
        f"[editor] Verdict for {analyst_finding.ticker}: {report.verdict} "
        f"(confidence={report.confidence})",
        tags=["editor", "verdict", analyst_finding.ticker],
    )
    return report


# ---------------------------------------------------------------------------
# Reasoner 4a: Short-Term Editor (1–6 month horizon)
# ---------------------------------------------------------------------------

@app.reasoner(path="/research/editor/short", tags=["committee"])
async def editor_short_term(
    plan: ResearchPlan,
    analyst_finding: AnalystFinding,
    risk_assessment: RiskAssessment,
) -> ResearchReport:
    """
    Short-Term Editor: synthesizes a 1–6 month investment recommendation
    focusing on near-term catalysts, earnings, momentum, and sentiment.
    """
    app.note(
        f"[editor_short] Starting short-term synthesis for {plan.ticker}",
        tags=["editor_short", plan.ticker],
    )

    # Fetch short-term-specific data
    analyst_targets, insiders, income_q, cashflow_q = await asyncio.gather(
        get_analyst_targets(plan.ticker),
        get_insider_transactions(plan.ticker, limit=10),
        get_income_statement(plan.ticker, "quarterly"),
        get_cash_flow_statement(plan.ticker, "quarterly"),
    )

    report: ResearchReport = await app.ai(
        system=(
            "You are a short-term investment analyst (1–6 month horizon). "
            "First, populate reasoning_steps with your deliberation: which near-term "
            "catalysts or risks dominated your thinking, and why you chose this verdict. "
            "Focus ONLY on near-term factors: upcoming earnings, analyst price targets, "
            "news sentiment, technical momentum, insider activity, macro events. "
            "Ignore long-term structural factors — they are irrelevant here. "
            f"{CONFIDENCE_GUIDE} Set time_horizon='short_term'. "
            "Arrive at a BUY/HOLD/SELL for the NEXT 1–6 MONTHS."
        ),
        user=(
            f"Ticker: {plan.ticker} ({plan.company_name})\n\n"
            f"=== ANALYST PRICE TARGETS & CONSENSUS ===\n{_json(analyst_targets)}\n\n"
            f"=== INSIDER TRANSACTIONS ===\n{_json(insiders)}\n\n"
            f"=== QUARTERLY INCOME (last 4 quarters) ===\n{_json(income_q)}\n\n"
            f"=== QUARTERLY CASH FLOW ===\n{_json(cashflow_q)}\n\n"
            f"=== ANALYST FINDING (BULL) ===\n{_json(analyst_finding)}\n\n"
            f"=== RISK ASSESSMENT (BEAR) ===\n{_json(risk_assessment)}\n\n"
            "Synthesise a SHORT-TERM ResearchReport (time_horizon='short_term')."
        ),
        schema=ResearchReport,
        model="nebius/openai/gpt-oss-20b",
    )

    app.note(
        f"[editor_short] Short-term verdict: {report.verdict} ({report.confidence}%)",
        tags=["editor_short", plan.ticker],
    )
    return report


# ---------------------------------------------------------------------------
# Reasoner 4b: Long-Term Editor (1–5 year horizon)
# ---------------------------------------------------------------------------

@app.reasoner(path="/research/editor/long", tags=["committee"])
async def editor_long_term(
    plan: ResearchPlan,
    analyst_finding: AnalystFinding,
    risk_assessment: RiskAssessment,
) -> ResearchReport:
    """
    Long-Term Editor: synthesizes a 1–5 year investment recommendation
    focusing on competitive moat, growth trajectory, and structural factors.
    """
    app.note(
        f"[editor_long] Starting long-term synthesis for {plan.ticker}",
        tags=["editor_long", plan.ticker],
    )

    # Fetch long-term-relevant data
    analyst_targets, insiders, facts = await asyncio.gather(
        get_analyst_targets(plan.ticker),
        get_insider_transactions(plan.ticker, limit=10),
        get_company_facts(plan.ticker),
    )

    report: ResearchReport = await app.ai(
        system=(
            "You are a long-term investment analyst (1–5 year horizon). "
            "First, populate reasoning_steps with your deliberation: which structural "
            "advantages or risks dominated your thinking, and why you chose this verdict. "
            "Focus ONLY on long-term factors: competitive moat, revenue growth trajectory, "
            "balance sheet strength, management quality, industry tailwinds/headwinds, "
            "valuation vs intrinsic value over 5 years. "
            "Ignore short-term noise — it is irrelevant here. "
            f"{CONFIDENCE_GUIDE} Set time_horizon='long_term'. "
            "Arrive at a BUY/HOLD/SELL for the NEXT 1–5 YEARS."
        ),
        user=(
            f"Ticker: {plan.ticker} ({plan.company_name})\n\n"
            f"=== ANALYST PRICE TARGETS & CONSENSUS ===\n{_json(analyst_targets)}\n\n"
            f"=== INSIDER TRANSACTIONS ===\n{_json(insiders)}\n\n"
            f"=== COMPANY FACTS ===\n{_json(facts)}\n\n"
            f"=== ANALYST FINDING (BULL) ===\n{_json(analyst_finding)}\n\n"
            f"=== RISK ASSESSMENT (BEAR) ===\n{_json(risk_assessment)}\n\n"
            "Synthesise a LONG-TERM ResearchReport (time_horizon='long_term')."
        ),
        schema=ResearchReport,
        model="nebius/openai/gpt-oss-20b",
    )

    app.note(
        f"[editor_long] Long-term verdict: {report.verdict} ({report.confidence}%)",
        tags=["editor_long", plan.ticker],
    )
    return report


# ---------------------------------------------------------------------------
# Reasoner 3: The Contrarian — bear case / risk assessment
# ---------------------------------------------------------------------------

@app.reasoner(path="/research/contrarian", tags=["committee"])
async def assess_risks(
    plan: ResearchPlan,
) -> RiskAssessment:
    """
    it searches specifically for risks, counter-arguments, regulatory threats,
    competitive pressures, and anything that could invalidate the thesis.
    """
    app.note(
        f"[contrarian] Starting bear-case analysis for {plan.ticker}",
        tags=["contrarian", plan.ticker],
    )

    # Fetch risk-oriented news: focus on negative sentiment, lawsuits, competition
    risk_query = f"{plan.ticker} lawsuit antitrust competition earnings miss risk"
    news = await search_market_news(plan.ticker, limit=20)

    # Filter news for risk-relevant articles; fallback to first 8 if none match
    risk_keywords = [
        "risk", "lawsuit", "antitrust", "fine", "fail", "miss", "decline",
        "competition", "threat", "concern", "warn", "short", "bear", "sell",
        "downgrade", "probe", "investigation", "recall", "loss"
    ]
    risk_news = [
        n for n in news
        if any(kw in (n.get("title", "") + n.get("summary", "")).lower() for kw in risk_keywords)
    ] or news[:8]

    app.note(
        f"[contrarian] Found {len(risk_news)} risk-relevant news articles",
        tags=["contrarian", plan.ticker],
    )

    assessment: RiskAssessment = await app.ai(
        system=(
            "You are a short-seller and risk manager at a hedge fund. Your role is to "
            "act as the Devil's Advocate — find every flaw, risk, and counter-argument "
            "in the bull thesis. Be specific with numbers. Identify regulatory risks, "
            "competitive threats, valuation concerns, and macro headwinds. "
            "Do NOT be dismissive — provide substantive, evidence-based counter-points. "
            "Your goal is rigorous risk identification, not pessimism for its own sake."
        ),
        user=(
            f"Ticker: {plan.ticker} ({plan.company_name})\n\n"
            f"=== RESEARCH PLAN (for context) ===\n{_json(plan)}\n\n"
            f"=== RECENT NEWS (risk-focused, {len(risk_news)} articles) ===\n{_json(risk_news)}\n\n"
            "Provide a thorough RiskAssessment. Quantify risks where possible. "
            f"Focus areas: {', '.join(plan.focus_areas)}"
        ),
        schema=RiskAssessment,
    )

    app.note(
        f"[contrarian] Risk severity for {plan.ticker}: {assessment.severity} "
        f"({len(assessment.risks)} risks identified)",
        tags=["contrarian", plan.ticker],
    )
    return assessment


# ---------------------------------------------------------------------------
# Reasoner 2: The Analyst — bull case research
# ---------------------------------------------------------------------------

@app.reasoner(path="/research/analyst", tags=["committee"])
async def conduct_research(plan: ResearchPlan) -> AnalystFinding:
    """
    The Analyst: executes the research plan by pulling financial statements,
    company facts, and news via yfinance Skills, then drafts a bull-case thesis.
    """
    app.note(
        f"[analyst] Starting bull-case research for {plan.ticker}",
        tags=["analyst", plan.ticker],
    )

    # Fetch all financial data in parallel (annual + quarterly + new signals)
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

    app.note(
        f"[analyst] Data gathered for {plan.ticker}. "
        f"Annual periods: {len(income)}, Quarterly: {len(income_q)}, News: {len(news)}",
        tags=["analyst", plan.ticker],
    )

    finding: AnalystFinding = await app.ai(
        system=(
            "You are a senior equity research analyst at a bulge-bracket investment bank. "
            "You are building the BULL CASE for a stock. Your job is to identify the strongest "
            "supporting evidence from the financial data — revenue growth, margin expansion, "
            "free cash flow quality, competitive advantages, and positive catalysts. "
            "Be specific: cite actual numbers (e.g., 'Revenue grew 15% YoY to $94B'). "
            "Focus areas from the research plan should guide your analysis."
        ),
        user=(
            f"Ticker: {plan.ticker} ({plan.company_name})\n\n"
            f"=== RESEARCH PLAN ===\n{_json(plan)}\n\n"
            f"=== ANALYST PRICE TARGETS & CONSENSUS ===\n{_json(analyst_targets)}\n\n"
            f"=== INSIDER TRANSACTIONS ===\n{_json(insiders)}\n\n"
            f"=== COMPANY FACTS ===\n{_json(facts)}\n\n"
            f"=== INCOME STATEMENT (ANNUAL) ===\n{_json(income)}\n\n"
            f"=== INCOME STATEMENT (QUARTERLY) ===\n{_json(income_q)}\n\n"
            f"=== BALANCE SHEET ===\n{_json(balance)}\n\n"
            f"=== CASH FLOW ===\n{_json(cashflow)}\n\n"
            f"=== NEWS (20 articles) ===\n{_json(news)}\n\n"
            f"Build a rigorous AnalystFinding with a detailed bull case. "
            f"Focus on: {', '.join(plan.focus_areas)}"
        ),
        schema=AnalystFinding,
    )

    app.note(
        f"[analyst] Bull case drafted for {plan.ticker} "
        f"(data quality: {finding.data_quality})",
        tags=["analyst", plan.ticker],
    )
    return finding


# ---------------------------------------------------------------------------
# Reasoner 1: The Manager — entry point and orchestrator
# ---------------------------------------------------------------------------

@app.reasoner(path="/research", tags=["committee"])
async def plan_research(query: str) -> DualResearchReport:
    """
    The Manager: entry point for direct API queries (POST /research).
    Decomposes the query into a ResearchPlan, dispatches Analyst and Contrarian
    in parallel, then runs EditorShort and EditorLong in parallel to produce
    a DualResearchReport.

    NOTE: The streaming UI uses POST /research/stream/start instead, which
    runs the same 5-agent pipeline via SSE events, calling the same reasoner
    functions below for automatic workflow tracking.

    Args:
        query: Free-form user query, e.g. "Should I invest in AAPL?"

    Returns:
        DualResearchReport with short_term and long_term ResearchReports.
    """
    # Step 1: Create the research plan using the standalone reasoner
    plan = await create_plan(query)

    # Validate ticker before running the full committee
    app.note(f"[manager] Validating {plan.ticker} on yfinance...", tags=["manager", plan.ticker])
    ticker_check = await validate_ticker(plan.ticker)
    if not ticker_check.get("valid"):
        reason = ticker_check.get("reason", "Ticker not found.")
        raise ValueError(
            f"Cannot analyse {plan.ticker}: {reason} "
            "Please use a real, actively traded stock ticker (e.g. AAPL, NVDA, MSFT)."
        )
    app.note(
        f"[manager] {plan.ticker} validated — {ticker_check.get('quote_type', 'EQUITY')} "
        f"at ${ticker_check.get('current_price')} on {ticker_check.get('exchange', 'unknown exchange')}",
        tags=["manager", plan.ticker],
    )

    # Step 2: Analyst (bull) + Contrarian (bear) in parallel
    analyst_finding, risk_assessment = await asyncio.gather(
        conduct_research(plan),
        assess_risks(plan)
    )

    app.note(
        f"[manager] Committee opinions gathered for {plan.ticker}. "
        f"Running EditorShort and EditorLong in parallel...",
        tags=["manager", plan.ticker],
    )

    # Step 3: Dual editors in parallel — using the standalone reasoner functions
    short_report, long_report = await asyncio.gather(
        editor_short_term(plan, analyst_finding, risk_assessment),
        editor_long_term(plan, analyst_finding, risk_assessment),
    )

    app.note(
        f"[manager] Research complete for {plan.ticker}. "
        f"Short: {short_report.verdict} ({short_report.confidence}%) | "
        f"Long: {long_report.verdict} ({long_report.confidence}%)",
        tags=["manager", "complete", plan.ticker],
    )

    return DualResearchReport(short_term=short_report, long_term=long_report)
