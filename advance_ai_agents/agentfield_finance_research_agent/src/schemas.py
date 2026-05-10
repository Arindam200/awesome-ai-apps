"""
schemas.py — Pydantic models for the Argus Investment Committee pipeline.

Data flow (streaming — SSE pipeline in stream.py):
  User Query
    → ResearchPlan         (Manager)
    → AnalystFinding       (Analyst) ─┬─ parallel
    → RiskAssessment       (Contrarian)─┘
    → ResearchReport × 2  (EditorShort ‖ EditorLong, parallel) → DualResearchReport

Data flow (direct API — reasoners.py POST /research):
  Same agents, returns DualResearchReport directly.
"""
from pydantic import BaseModel, Field
from typing import Literal


class ResearchPlan(BaseModel):
    """The Manager's decomposition of a user query into a research plan."""

    reasoning_steps: list[str] = Field(
        description="Step-by-step reasoning: how you interpreted the query, why you chose this ticker, key assumptions"
    )
    ticker: str = Field(description="Stock ticker symbol, e.g. AAPL")
    company_name: str = Field(description="Full company name")
    hypotheses: list[str] = Field(
        description="2-4 key hypotheses to investigate (bull and bear)"
    )
    data_needs: list[str] = Field(
        description="List of data points needed to validate the hypotheses"
    )
    focus_areas: list[str] = Field(
        description="Specific areas for deep-dive: e.g. revenue growth, debt levels, competitive moat"
    )


class AnalystFinding(BaseModel):
    """The Analyst's bull-case research output."""

    reasoning_steps: list[str] = Field(
        description="Step-by-step reasoning: what the data shows, how you formed the bull case, key evidence weighed"
    )
    ticker: str
    bull_case: str = Field(
        description="Detailed bull-case thesis (200-400 words) with specific numbers and metrics"
    )
    key_metrics: list[str] = Field(
        description="Key financial metrics as 'Metric: Value' strings, e.g. ['Revenue Growth: 15% YoY', 'P/E: 28x']"
    )
    supporting_data: list[str] = Field(
        description="Key data points and quotes supporting the bull case"
    )
    data_quality: Literal["high", "medium", "low"] = Field(
        description="Assessment of data completeness and reliability"
    )


class RiskAssessment(BaseModel):
    """The Contrarian's bear-case risk analysis."""

    reasoning_steps: list[str] = Field(
        description="Step-by-step reasoning: what you challenged in the bull case, how each risk was identified"
    )
    ticker: str
    bear_case: str = Field(
        description="Detailed bear-case thesis (200-400 words) challenging the bull case"
    )
    risks: list[str] = Field(
        description="Specific, quantified risks: e.g. 'Antitrust fine exposure: up to $30B'"
    )
    counter_points: list[str] = Field(
        description="Direct counter-arguments to the Analyst's bull case"
    )
    severity: Literal["high", "medium", "low"] = Field(
        description="Overall severity of identified risks"
    )


class ResearchReport(BaseModel):
    """The Editor's final synthesized research report."""

    reasoning_steps: list[str] = Field(
        description="Step-by-step reasoning: how you weighed bull vs bear, why you chose this verdict and confidence score"
    )
    time_horizon: Literal["short_term", "long_term"] = Field(
        description="Investment horizon this report covers: short_term (1-6 months) or long_term (1-5 years)"
    )
    ticker: str
    company_name: str
    summary: str = Field(
        description="Executive summary (100 words): balanced overview of the investment case for this time horizon"
    )
    bull_case: str = Field(description="Condensed bull case from the Analyst, filtered for this time horizon")
    bear_case: str = Field(description="Condensed bear case from the Contrarian, filtered for this time horizon")
    key_metrics: list[str] = Field(
        description="Most important financial metrics as 'Metric: Value' strings, e.g. ['Revenue: $94B', 'P/E: 28x']"
    )
    risks: list[str] = Field(description="Top 3-5 risks to the investment thesis for this time horizon")
    verdict: Literal["BUY", "HOLD", "SELL"] = Field(
        description="Final investment recommendation for this time horizon"
    )
    confidence: int = Field(
        ge=0,
        le=100,
        description=(
            "Confidence score 0-100 in the verdict. Use this scale strictly: "
            "85-100 = overwhelming evidence, minimal counter-case; "
            "65-80 = clear lean, but meaningful uncertainty exists; "
            "50-65 = genuinely balanced, could go either way; "
            "<50 = too uncertain to have strong conviction."
        ),
    )
    reasoning: str = Field(
        description="Explanation for the verdict and confidence score"
    )


class DualResearchReport(BaseModel):
    """Combined output of the two parallel editors (short-term + long-term)."""

    short_term: ResearchReport = Field(
        description="Investment outlook for the next 1–6 months"
    )
    long_term: ResearchReport = Field(
        description="Investment outlook for the next 1–5 years"
    )
