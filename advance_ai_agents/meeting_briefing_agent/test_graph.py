"""Deterministic end-to-end test of the Briefing Room graph — no API calls.

Run:  uv run python test_graph.py
"""

from pathlib import Path

import graph as g


class FakeStructured:
    def __init__(self, payload):
        self.payload = payload

    def invoke(self, messages):
        return self.payload


class FakeLLM:
    """Stands in for ChatOpenAI: canned structured outputs + a canned brief.

    The first coverage check reports a gap (forcing the reflect→research
    loop); the second passes, so the run terminates and writes the brief.
    """

    def __init__(self):
        self.coverage_calls = 0

    def with_structured_output(self, schema):
        if schema is g.ResearchPlan:
            return FakeStructured(
                g.ResearchPlan(sub_questions=["q1", "q2", "q3"], angle="angle")
            )
        if schema is g.CoverageCheck:
            self.coverage_calls += 1
            if self.coverage_calls == 1:
                return FakeStructured(
                    g.CoverageCheck(
                        sufficient=False, gaps=["gap-q"], reasoning="missing news"
                    )
                )
            return FakeStructured(
                g.CoverageCheck(sufficient=True, gaps=[], reasoning="ok")
            )
        raise AssertionError(f"unexpected schema: {schema}")

    def invoke(self, messages):
        class Resp:
            content = "## Acme Corp — Meeting Brief\n**Three things to know** ..."

        return Resp()


class FakeSearch:
    def invoke(self, payload):
        q = payload["query"]
        return {
            "results": [
                {"title": f"T-{q}", "url": f"http://x/{q}", "content": "snippet"}
            ]
        }


def test_env_path_is_project_local():
    assert g.ENV_FILE == Path(g.__file__).resolve().with_name(".env")
    print("environment test OK: .env path is anchored to the project")


def test_graph_end_to_end():
    graph = g.build_graph(FakeLLM(), FakeSearch())
    state = g.initial_state("Acme Corp", attendee="Jane Doe", max_iterations=2)
    final = graph.invoke(state)

    # plan produced the research questions
    assert final["sub_questions"] == ["q1", "q2", "q3"]

    # exactly one reflect→research loop happened
    assert final["iterations"] == 2

    # evidence accumulated across both passes (3 planned + 1 gap query)
    urls = {e["url"] for e in final["evidence"]}
    assert urls == {"http://x/q1", "http://x/q2", "http://x/q3", "http://x/gap-q"}, urls
    assert any(e["question"] == "gap-q" for e in final["evidence"])

    # brief was written
    assert "Meeting Brief" in final["brief"]
    print("end-to-end graph test OK: plan -> research -> reflect(loop) -> write")


def test_stream_updates_preserve_all_evidence():
    """Later research updates must append instead of replacing prior sources."""
    workflow = g.build_graph(FakeLLM(), FakeSearch())
    state = g.initial_state("Acme Corp", max_iterations=2)
    streamed_state = dict(state)

    for chunk in workflow.stream(state, stream_mode="updates"):
        for update in chunk.values():
            streamed_state = g.merge_stream_update(streamed_state, update)

    urls = {e["url"] for e in streamed_state["evidence"]}
    assert urls == {"http://x/q1", "http://x/q2", "http://x/q3", "http://x/gap-q"}
    assert len(streamed_state["evidence"]) == 4

    after_empty_pass = g.merge_stream_update(streamed_state, {"evidence": []})
    assert after_empty_pass["evidence"] == streamed_state["evidence"]
    print("streaming state test OK: evidence accumulates across research passes")


def test_iteration_budget_is_respected():
    """If coverage never passes, the graph still stops at max_iterations."""

    class AlwaysGappy(FakeLLM):
        def with_structured_output(self, schema):
            if schema is g.CoverageCheck:
                return FakeStructured(
                    g.CoverageCheck(
                        sufficient=False, gaps=["more"], reasoning="never happy"
                    )
                )
            return super().with_structured_output(schema)

    graph = g.build_graph(AlwaysGappy(), FakeSearch())
    final = graph.invoke(g.initial_state("Acme Corp", max_iterations=2))
    assert final["iterations"] == 2  # stopped at the budget, still wrote a brief
    assert "Meeting Brief" in final["brief"]
    print("iteration budget test OK: graph terminates and writes anyway")


def test_all_search_failures_are_reported():
    """A bad Tavily credential must not silently produce an empty brief."""

    class FailingSearch:
        def invoke(self, payload):
            raise RuntimeError("401: unable to authenticate")

    graph = g.build_graph(FakeLLM(), FailingSearch())
    try:
        graph.invoke(g.initial_state("Acme Corp"))
    except g.TavilySearchError as exc:
        assert "every search request" in str(exc)
    else:
        raise AssertionError("expected TavilySearchError")
    print("search failure test OK: provider errors are surfaced")


if __name__ == "__main__":
    test_env_path_is_project_local()
    test_graph_end_to_end()
    test_stream_updates_preserve_all_evidence()
    test_iteration_budget_is_respected()
    test_all_search_failures_are_reported()
    print("\nAll graph tests passed.")
