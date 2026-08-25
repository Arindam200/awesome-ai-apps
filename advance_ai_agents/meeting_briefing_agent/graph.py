"""Briefing Room — a pre-meeting intel agent.

A LangGraph state machine that turns a company name (and optionally an
attendee) into a one-page pre-meeting brief, grounded in live web research
via Tavily and written by an open model served on Nebius Token Factory.

Flow
----
        ┌────────┐     ┌──────────┐     ┌─────────┐
START ─▶│  plan  │ ──▶ │ research │ ──▶ │ reflect │ ──┐ gaps found and
        └────────┘     └──────────┘     └─────────┘   │ iterations left
              ▲                                        │
              └────────────────────────────────────────┘
                                                   │ sufficient
                                                   ▼
                                              ┌────────┐
                                              │  write │ ──▶ END
                                              └────────┘

The reflect → research loop is what makes this a LangGraph demo rather than
a plain chain: the graph keeps researching until coverage is good enough or
the iteration budget runs out.
"""

from __future__ import annotations

import operator
import os
from pathlib import Path
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, SecretStr

ENV_FILE = Path(__file__).resolve().with_name(".env")
load_dotenv(ENV_FILE)

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"
DEFAULT_MAX_ITERATIONS = 2
MAX_TAVILY_RESULTS = 5
SNIPPET_CHARS = 600


# --------------------------------------------------------------------------- #
# State and structured-output schemas
# --------------------------------------------------------------------------- #


class Evidence(TypedDict):
    """One piece of web evidence tied to the question that produced it."""

    question: str
    title: str
    url: str
    snippet: str


class BriefingState(TypedDict):
    company: str
    attendee: str
    user_context: str
    max_iterations: int
    sub_questions: list[str]
    evidence: Annotated[list[Evidence], operator.add]
    gaps: list[str]
    iterations: int
    brief: str


class ResearchPlan(BaseModel):
    """Structured output of the planning step."""

    sub_questions: list[str] = Field(
        description=(
            "4-6 specific, search-engine-friendly research questions that "
            "together cover what someone needs before a meeting with this "
            "company: what they do, recent news/funding, products and tech "
            "stack, priorities and pain points, and the attendee's role."
        )
    )
    angle: str = Field(
        description="One sentence describing the sharpest angle for the brief."
    )


class CoverageCheck(BaseModel):
    """Structured output of the reflection step."""

    sufficient: bool = Field(
        description="True if the evidence is enough to write a solid brief."
    )
    gaps: list[str] = Field(
        default_factory=list,
        description=(
            "If not sufficient: up to 3 new search queries that would close "
            "the biggest gaps. Empty when sufficient is True."
        ),
    )
    reasoning: str = Field(description="One sentence explaining the verdict.")


class TavilySearchError(RuntimeError):
    """Raised when Tavily fails for every query in a research pass."""


def merge_stream_update(state: dict, update: dict) -> dict:
    """Merge a streamed node update using the graph state's reducer semantics."""
    merged = {**state, **{key: value for key, value in update.items() if key != "evidence"}}
    if "evidence" in update:
        merged["evidence"] = [
            *state.get("evidence", []),
            *update.get("evidence", []),
        ]
    return merged


# --------------------------------------------------------------------------- #
# Model / tool builders
# --------------------------------------------------------------------------- #


def build_model(
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.4,
) -> ChatOpenAI:
    """Chat model served by Nebius Token Factory (OpenAI-compatible API)."""
    key = (api_key or os.environ["NEBIUS_API_KEY"]).strip()
    return ChatOpenAI(
        model=model or os.getenv("NEBIUS_MODEL", DEFAULT_MODEL),
        base_url=base_url or os.getenv("NEBIUS_BASE_URL", DEFAULT_BASE_URL),
        api_key=SecretStr(key),
        temperature=temperature,
    )


def build_search(api_key: str | None = None) -> TavilySearch:
    key = (api_key or os.environ["TAVILY_API_KEY"]).strip()
    return TavilySearch(
        max_results=MAX_TAVILY_RESULTS,
        topic="general",
        tavily_api_key=SecretStr(key),
    )


# --------------------------------------------------------------------------- #
# Graph nodes
# --------------------------------------------------------------------------- #

_PLAN_SYSTEM = (
    "You are a chief of staff preparing an executive for an external meeting. "
    "Break the prep work into concrete web research questions. Make every "
    "question self-contained (include the company/person name) and phrased "
    "the way you would type it into a search engine."
)

_REFLECT_SYSTEM = (
    "You are a demanding research editor. Judge whether the collected "
    "evidence is enough to brief someone before a meeting: company basics, "
    "recent developments, and at least one concrete conversation angle. "
    "Only ask for more research if something important is clearly missing "
    "or contradicted."
)

_WRITE_SYSTEM = """You are a chief of staff writing a one-page pre-meeting brief.

Rules:
- Ground every claim in the numbered evidence; cite inline as [1], [2], ...
- Never invent facts, numbers, or dates. If something is unknown, omit it.
- Separate confirmed facts from suggested talking points.

Produce markdown with exactly these sections:
## {company} — Meeting Brief
**Three things to know** — the three most useful facts, each one sentence, each cited.
**Company snapshot** — what they do, size/stage, product & tech signals, recent momentum (bullets, cited).
{attendee_section}**Three questions to ask** — sharp, open questions that show you did your homework.
**One thing to avoid** — a topic, claim, or assumption that could backfire, and why.
**Sources** — numbered list of the cited URLs.
"""


def _format_evidence_for_prompt(evidence: list[Evidence]) -> str:
    lines = []
    for i, ev in enumerate(evidence, start=1):
        lines.append(f"[{i}] {ev['title']}\n{ev['url']}\n{ev['snippet']}\n")
    return "\n".join(lines) if lines else "(no evidence collected)"


def make_plan_node(llm: ChatOpenAI):
    def plan_node(state: BriefingState) -> dict:
        planner = llm.with_structured_output(ResearchPlan)
        attendee_line = (
            f"The person we are meeting: {state['attendee']}."
            if state["attendee"]
            else "The specific attendee is unknown."
        )
        context_line = (
            f"Our context/goal for the meeting: {state['user_context']}"
            if state["user_context"]
            else "No extra context about our goal was provided."
        )
        plan: ResearchPlan = planner.invoke(
            [
                SystemMessage(content=_PLAN_SYSTEM),
                HumanMessage(
                    content=(
                        f"Company: {state['company']}\n"
                        f"{attendee_line}\n{context_line}\n\n"
                        "Produce the research plan."
                    )
                ),
            ]
        )
        return {"sub_questions": plan.sub_questions[:6], "iterations": 0}

    return plan_node


def make_research_node(search: TavilySearch):
    def research_node(state: BriefingState) -> dict:
        # First pass researches the plan; later passes chase the gaps.
        queries = state["gaps"] if state["gaps"] else state["sub_questions"]
        seen_urls = {ev["url"] for ev in state["evidence"]}
        new_evidence: list[Evidence] = []
        failures: list[Exception] = []
        for query in queries:
            try:
                raw = search.invoke({"query": query})
            except Exception as exc:
                failures.append(exc)
                continue
            results = raw.get("results", []) if isinstance(raw, dict) else raw
            for r in results:
                if not isinstance(r, dict):
                    continue
                url = r.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                new_evidence.append(
                    Evidence(
                        question=query,
                        title=r.get("title", "(untitled)"),
                        url=url,
                        snippet=(r.get("content") or "")[:SNIPPET_CHARS],
                    )
                )
        if queries and len(failures) == len(queries):
            first_error = failures[0]
            raise TavilySearchError(
                f"Tavily rejected every search request: {first_error}"
            ) from first_error
        return {"evidence": new_evidence}

    return research_node


def make_reflect_node(llm: ChatOpenAI):
    def reflect_node(state: BriefingState) -> dict:
        checker = llm.with_structured_output(CoverageCheck)
        check: CoverageCheck = checker.invoke(
            [
                SystemMessage(content=_REFLECT_SYSTEM),
                HumanMessage(
                    content=(
                        f"Meeting target: {state['company']}"
                        + (
                            f" (attendee: {state['attendee']})"
                            if state["attendee"]
                            else ""
                        )
                        + "\n\nEvidence so far:\n"
                        + _format_evidence_for_prompt(state["evidence"])
                    )
                ),
            ]
        )
        gaps = [] if check.sufficient else check.gaps[:3]
        return {"gaps": gaps, "iterations": state["iterations"] + 1}

    return reflect_node


def route_after_reflect(state: BriefingState) -> str:
    if state["gaps"] and state["iterations"] < state["max_iterations"]:
        return "research"
    return "write"


def make_write_node(llm: ChatOpenAI):
    def write_node(state: BriefingState) -> dict:
        attendee_section = (
            f"**About {state['attendee']}** — role, background, likely priorities (cited).\n"
            if state["attendee"]
            else ""
        )
        prompt = _WRITE_SYSTEM.replace("{company}", state["company"]).replace(
            "{attendee_section}", attendee_section
        )
        context_line = (
            f"\nTailor talking points to our goal: {state['user_context']}"
            if state["user_context"]
            else ""
        )
        response = llm.invoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=(
                        f"Write the brief for the meeting with {state['company']}."
                        f"{context_line}\n\nEvidence:\n"
                        + _format_evidence_for_prompt(state["evidence"])
                    )
                ),
            ]
        )
        return {"brief": response.content}

    return write_node


# --------------------------------------------------------------------------- #
# Graph assembly
# --------------------------------------------------------------------------- #


def build_graph(llm: ChatOpenAI, search: TavilySearch):
    """Compile the Briefing Room graph."""
    builder = StateGraph(BriefingState)
    builder.add_node("plan", make_plan_node(llm))
    builder.add_node("research", make_research_node(search))
    builder.add_node("reflect", make_reflect_node(llm))
    builder.add_node("write", make_write_node(llm))

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "research")
    builder.add_edge("research", "reflect")
    builder.add_conditional_edges("reflect", route_after_reflect, ["research", "write"])
    builder.add_edge("write", END)
    return builder.compile()


def initial_state(
    company: str,
    attendee: str = "",
    user_context: str = "",
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> BriefingState:
    return BriefingState(
        company=company.strip(),
        attendee=attendee.strip(),
        user_context=user_context.strip(),
        max_iterations=max_iterations,
        sub_questions=[],
        evidence=[],
        gaps=[],
        iterations=0,
        brief="",
    )
