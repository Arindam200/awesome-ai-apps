"""Deterministic end-to-end tests of the risk review graph - no API calls.

Run:  uv run python tests/test_graph.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import graph as g


def finding(title, risk_level):
    return g.Finding(
        title=title,
        risk_level=risk_level,
        evidence=f"quote about {title}",
        reasoning=f"why {title} matters",
        recommendation=f"fix {title}",
    )


# Findings each reviewer returns, keyed by the reviewer's display name.
CANNED = {
    "Security Reviewer": [
        finding("Customer data sent to vendor", "high"),
        finding("Shared admin key", "critical"),
    ],
    "Legal Reviewer": [finding("No data processing agreement", "critical")],
    "Finance Reviewer": [finding("Egress cost not budgeted", "medium")],
    "Operations Reviewer": [finding("No rollback plan", "high")],
}

# The coordinator merges SEC-1 with LEG-1, rates the critical SEC-2 as only
# high, cites an ID nobody raised, and never cites OPS-1, so all three
# problems must surface as warnings.
MERGED = g.RiskReport(
    summary="Not ready to approve.",
    issues=[
        g.ReportIssue(
            title="Customer data shared without an agreement",
            risk_level="critical",
            source_ids=["SEC-1", "LEG-1"],
            reasoning="Security rated it high, Legal critical; kept critical.",
            recommendation="Sign a DPA and minimise the export.",
        ),
        g.ReportIssue(
            title="Shared admin key",
            risk_level="high",
            source_ids=["SEC-2"],
            reasoning="One key with billing rights in a wiki.",
            recommendation="Issue scoped keys and rotate them.",
        ),
        g.ReportIssue(
            title="Egress cost",
            risk_level="medium",
            source_ids=["FIN-1", "FIN-9"],
            reasoning="400 GB a night is not in the budget.",
            recommendation="Price the egress before signing.",
        ),
    ],
)


class FakeStructured:
    def __init__(self, llm, schema):
        self.llm, self.schema = llm, schema

    def invoke(self, messages):
        if self.schema is g.ReviewerFindings:
            for name, findings in self.llm.reviewer_findings.items():
                if name in messages[0].content:
                    return g.ReviewerFindings(findings=findings)
            raise AssertionError("unknown reviewer prompt")
        if self.schema is g.RiskReport:
            self.llm.coordinator_inputs.append(messages[1].content)
            return MERGED
        raise AssertionError(f"unexpected schema: {self.schema}")


class FakeLLM:
    """Stands in for ChatOpenAI and returns canned structured outputs."""

    def __init__(self, reviewer_findings=CANNED):
        self.reviewer_findings = reviewer_findings
        self.coordinator_inputs = []

    def with_structured_output(self, schema):
        return FakeStructured(self, schema)


def test_reviewers_run_and_coordinator_sees_every_finding():
    llm = FakeLLM()
    final = g.build_graph(llm).invoke(g.initial_state("a deployment plan"))

    ids = sorted(f["id"] for f in final["findings"])
    assert ids == ["FIN-1", "LEG-1", "OPS-1", "SEC-1", "SEC-2"], ids
    assert {f["role"] for f in final["findings"]} == set(g.REVIEWERS)

    # The coordinator ran once, after all four reviewers, with every ID.
    assert len(llm.coordinator_inputs) == 1
    for finding_id in ids:
        assert f"[{finding_id}]" in llm.coordinator_inputs[0]
    print("graph test OK: four reviewers fan in to one coordinator call")


def test_report_problems_are_warnings_not_repairs():
    final = g.build_graph(FakeLLM()).invoke(g.initial_state("a deployment plan"))

    warnings = final["warnings"]
    assert any("FIN-9" in w and "no reviewer raised" in w for w in warnings), warnings
    assert any("No issue cites OPS-1" in w for w in warnings), warnings
    assert any(
        "rated high, below its most severe finding (critical)" in w for w in warnings
    ), warnings
    assert len(warnings) == 3, warnings
    # The report is kept as the coordinator wrote it.
    assert final["report"] == MERGED

    markdown = g.render_markdown(final)
    for finding_id in ("SEC-1", "SEC-2", "LEG-1", "FIN-1", "OPS-1"):
        assert f"**{finding_id}**" in markdown, finding_id
    assert "No issue cites OPS-1" in markdown
    # Issues are listed critical first.
    assert markdown.index("(CRITICAL)") < markdown.index("(MEDIUM)")
    print("report test OK: bad citations and downgrades are reported, originals kept")


def test_no_findings_skips_the_coordinator():
    empty = {name: [] for name in CANNED}
    llm = FakeLLM(reviewer_findings=empty)
    final = g.build_graph(llm).invoke(g.initial_state("a harmless memo"))

    assert llm.coordinator_inputs == []
    assert final["report"].issues == []
    assert final["warnings"] == []
    assert "No issues." in g.render_markdown(final)
    print("empty test OK: no findings means no coordinator call")


def test_missing_api_key_is_reported():
    saved = os.environ.get("NEBIUS_API_KEY")
    os.environ["NEBIUS_API_KEY"] = "  "
    try:
        g.build_model()
    except g.MissingAPIKeyError as exc:
        assert "NEBIUS_API_KEY" in str(exc)
    else:
        raise AssertionError("expected MissingAPIKeyError")
    finally:
        if saved is None:
            os.environ.pop("NEBIUS_API_KEY")
        else:
            os.environ["NEBIUS_API_KEY"] = saved
    print("api key test OK: a blank key fails before any request")


if __name__ == "__main__":
    test_reviewers_run_and_coordinator_sees_every_finding()
    test_report_problems_are_warnings_not_repairs()
    test_no_findings_skips_the_coordinator()
    test_missing_api_key_is_reported()
