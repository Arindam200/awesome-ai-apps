"""Multi-Agent Risk Review.

A LangGraph workflow in which four reviewer agents (security, legal, finance
and operations) read the same proposal, contract or deployment plan in
parallel and return structured findings. A coordinator agent then merges,
deduplicates and settles them into one risk report.

Flow
----
            ┌────────────┐
       ┌──▶ │  security  │ ──┐
       │    └────────────┘   │
       │    ┌────────────┐   │
       ├──▶ │   legal    │ ──┤
START ─┤    └────────────┘   ├──▶ coordinator ──▶ END
       │    ┌────────────┐   │
       ├──▶ │  finance   │ ──┤
       │    └────────────┘   │
       │    ┌────────────┐   │
       └──▶ │ operations │ ──┘
            └────────────┘

Every reviewer and the coordinator run on a model served by Nebius Token
Factory through its OpenAI-compatible API.
"""

from __future__ import annotations

import operator
import os
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, SecretStr

ENV_FILE = Path(__file__).resolve().with_name(".env")
load_dotenv(ENV_FILE)

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"

RiskLevel = Literal["low", "medium", "high", "critical"]
RISK_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


# --------------------------------------------------------------------------- #
# Structured-output schemas
# --------------------------------------------------------------------------- #


class Finding(BaseModel):
    """One risk a reviewer found in the document."""

    title: str = Field(description="Short name of the risk.")
    risk_level: RiskLevel = Field(description="low, medium, high or critical.")
    evidence: str = Field(
        description="A short quote from the document that shows the risk."
    )
    reasoning: str = Field(
        description="Why this is a risk from your perspective, and why this level."
    )
    recommendation: str = Field(description="What should change before approval.")


class ReviewerFindings(BaseModel):
    """Structured output of one reviewer."""

    findings: list[Finding] = Field(
        default_factory=list,
        description="Every distinct risk in your area. Empty if there is none.",
    )


class ReportIssue(BaseModel):
    """One issue in the final report, merged from one or more findings."""

    title: str = Field(description="Short name of the issue.")
    risk_level: RiskLevel = Field(description="low, medium, high or critical.")
    source_ids: list[str] = Field(
        description="IDs of the reviewer findings this issue covers, e.g. ['SEC-1', 'LEG-2']."
    )
    reasoning: str = Field(
        description=(
            "Why the issue has this level. If reviewers rated it differently, "
            "name them and say how you settled it."
        )
    )
    recommendation: str = Field(description="The combined recommendation.")


class RiskReport(BaseModel):
    """Structured output of the coordinator."""

    summary: str = Field(
        description="Two or three sentences on whether the document is ready to approve."
    )
    issues: list[ReportIssue] = Field(default_factory=list)


class ReviewState(TypedDict):
    document: str
    # Reviewers run in parallel; `operator.add` appends each one's findings.
    findings: Annotated[list[dict], operator.add]
    report: RiskReport | None
    warnings: list[str]


# --------------------------------------------------------------------------- #
# Reviewer and coordinator prompts
# --------------------------------------------------------------------------- #

# role -> (finding id prefix, display name, what the reviewer looks for)
REVIEWERS: dict[str, tuple[str, str, str]] = {
    "security": (
        "SEC",
        "Security Reviewer",
        (
            "data exposure, access control, credentials and secrets, encryption, "
            "third-party access to systems or data, and attack surface"
        ),
    ),
    "legal": (
        "LEG",
        "Legal Reviewer",
        (
            "contract terms, liability and indemnity, data protection and privacy "
            "law, consent, licensing, and regulatory obligations"
        ),
    ),
    "finance": (
        "FIN",
        "Finance Reviewer",
        (
            "costs, budget gaps, payment and renewal terms, financial exposure, "
            "and the assumptions behind any savings or returns"
        ),
    ),
    "operations": (
        "OPS",
        "Operations Reviewer",
        (
            "rollout and rollback, monitoring, on-call ownership, capacity, "
            "support coverage, and dependency on the vendor"
        ),
    ),
}

REVIEWER_PROMPT = (
    "You are the {name} on a risk review board.\n"
    "Review the document only for {focus}.\n\n"
    "Rules:\n"
    "- Report each distinct risk once, at the level you would defend: "
    "low, medium, high or critical.\n"
    "- Quote the document's own words as evidence. Never invent facts that "
    "are not in the document.\n"
    "- Leave risks outside your area to the other reviewers.\n"
    "- If you find nothing in your area, return an empty list."
)

COORDINATOR_PROMPT = (
    "You chair a risk review board. A security, a legal, a finance and an "
    "operations reviewer reviewed the same document. Their findings follow, "
    "each with an ID.\n\n"
    "Merge them into one report:\n"
    "- Combine findings that describe the same underlying problem into one "
    "issue, and list the ID of every finding it covers in source_ids.\n"
    "- Keep unrelated problems as separate issues. Every finding ID should "
    "appear in at least one issue.\n"
    "- When reviewers rate the same problem differently, keep the higher "
    "level unless another reviewer's quoted evidence shows the risk is "
    "mitigated. Say in reasoning which reviewers disagreed and why you chose "
    "the level.\n"
    "- Use only the IDs given, and do not add risks no reviewer raised."
)


# --------------------------------------------------------------------------- #
# Model builder
# --------------------------------------------------------------------------- #


class MissingAPIKeyError(RuntimeError):
    """Raised when no Nebius API key is configured."""


def build_model(
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.2,
) -> ChatOpenAI:
    """Chat model served by Nebius Token Factory (OpenAI-compatible API)."""
    key = (api_key or os.getenv("NEBIUS_API_KEY") or "").strip()
    if not key:
        raise MissingAPIKeyError(
            "NEBIUS_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return ChatOpenAI(
        model=model or os.getenv("NEBIUS_MODEL") or DEFAULT_MODEL,
        base_url=base_url or os.getenv("NEBIUS_BASE_URL") or DEFAULT_BASE_URL,
        api_key=SecretStr(key),
        temperature=temperature,
    )


# --------------------------------------------------------------------------- #
# Graph nodes
# --------------------------------------------------------------------------- #


def make_reviewer_node(llm: ChatOpenAI, role: str):
    prefix, name, focus = REVIEWERS[role]
    system = REVIEWER_PROMPT.format(name=name, focus=focus)

    def review_node(state: ReviewState) -> dict:
        result: ReviewerFindings = llm.with_structured_output(ReviewerFindings).invoke(
            [SystemMessage(content=system), HumanMessage(content=state["document"])]
        )
        # IDs come from code, not the model, so the coordinator's citations
        # can be checked against them.
        return {
            "findings": [
                {"id": f"{prefix}-{n}", "role": role, **finding.model_dump()}
                for n, finding in enumerate(result.findings, start=1)
            ]
        }

    return review_node


def _format_findings(findings: list[dict]) -> str:
    return "\n\n".join(
        f"[{f['id']}] ({f['role']}, {f['risk_level']}) {f['title']}\n"
        f"Evidence: {f['evidence']}\n"
        f"Reasoning: {f['reasoning']}\n"
        f"Recommendation: {f['recommendation']}"
        for f in findings
    )


def check_report(report: RiskReport, findings: list[dict]) -> list[str]:
    """List citation and severity problems instead of repairing them.

    This proves reference coverage (every cited ID exists and every finding
    is cited), and flags a finding cited by several issues and an issue rated
    below its most severe finding. It cannot prove the merged wording kept
    each point, which is why the report also prints the original findings.
    """
    by_id = {f["id"]: f for f in findings}
    warnings = []
    for issue in report.issues:
        if not issue.source_ids:
            warnings.append(f"Issue '{issue.title}' cites no reviewer finding.")
        for source_id in issue.source_ids:
            if source_id not in by_id:
                warnings.append(
                    f"Issue '{issue.title}' cites {source_id}, which no reviewer raised."
                )
        levels = [by_id[s]["risk_level"] for s in issue.source_ids if s in by_id]
        highest = min(levels, key=RISK_ORDER.__getitem__, default=None)
        if highest and RISK_ORDER[issue.risk_level] > RISK_ORDER[highest]:
            warnings.append(
                f"Issue '{issue.title}' is rated {issue.risk_level}, below its most "
                f"severe finding ({highest}); check its reasoning."
            )
    uses = Counter(s for issue in report.issues for s in set(issue.source_ids))
    warnings += [
        f"{source_id} is cited by {count} issues; check whether they repeat one risk."
        for source_id, count in uses.items()
        if count > 1 and source_id in by_id
    ]
    cited = set(uses)
    warnings += [
        f"No issue cites {f['id']} ({f['title']}); see the original findings."
        for f in findings
        if f["id"] not in cited
    ]
    return warnings


def make_coordinator_node(llm: ChatOpenAI):
    def coordinator_node(state: ReviewState) -> dict:
        findings = state["findings"]
        if not findings:
            report = RiskReport(summary="No reviewer found a risk in this document.")
            return {"report": report, "warnings": []}
        report: RiskReport = llm.with_structured_output(RiskReport).invoke(
            [
                SystemMessage(content=COORDINATOR_PROMPT),
                HumanMessage(content=_format_findings(findings)),
            ]
        )
        return {"report": report, "warnings": check_report(report, findings)}

    return coordinator_node


# --------------------------------------------------------------------------- #
# Graph assembly and rendering
# --------------------------------------------------------------------------- #


def build_graph(llm: ChatOpenAI):
    """Compile the review graph: four parallel reviewers, then the coordinator."""
    builder = StateGraph(ReviewState)
    for role in REVIEWERS:
        builder.add_node(role, make_reviewer_node(llm, role))
        builder.add_edge(START, role)
    builder.add_node("coordinator", make_coordinator_node(llm))
    # A list of sources makes the coordinator wait for all four reviewers.
    builder.add_edge(list(REVIEWERS), "coordinator")
    builder.add_edge("coordinator", END)
    return builder.compile()


def initial_state(document: str) -> ReviewState:
    return ReviewState(document=document, findings=[], report=None, warnings=[])


def render_markdown(state: ReviewState) -> str:
    """Render the final state as a Markdown report."""
    report = state["report"]
    lines = ["# Risk Review Report", "", report.summary, "", "## Issues", ""]
    if not report.issues and state["findings"]:
        lines += [
            "The coordinator returned no issues; see the validation warnings.",
            "",
        ]
    elif not report.issues:
        lines += ["No issues.", ""]
    issues = sorted(report.issues, key=lambda issue: RISK_ORDER[issue.risk_level])
    for n, issue in enumerate(issues, start=1):
        lines += [
            f"### {n}. {issue.title} ({issue.risk_level.upper()})",
            "",
            f"- **Sources:** {', '.join(issue.source_ids) or 'none'}",
            f"- **Reasoning:** {issue.reasoning}",
            f"- **Recommendation:** {issue.recommendation}",
            "",
        ]
    lines += ["## Validation warnings", ""]
    lines += [f"- {warning}" for warning in state["warnings"]] or ["None."]
    lines += ["", "## Original findings", ""]
    for role, (_, name, _) in REVIEWERS.items():
        own = [f for f in state["findings"] if f["role"] == role]
        lines += [f"### {name}", ""]
        if not own:
            lines += ["No findings.", ""]
            continue
        for f in own:
            lines += [
                f"- **{f['id']}** {f['title']} ({f['risk_level']})",
                f'  - Evidence: "{f["evidence"]}"',
                f"  - Reasoning: {f['reasoning']}",
                f"  - Recommendation: {f['recommendation']}",
            ]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
