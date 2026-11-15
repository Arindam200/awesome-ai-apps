from __future__ import annotations

import json

import pytest

from agent_observability import JsonlTraceRecorder, SupportAgentWorkflow, TraceAnalysisAgent
from agent_observability.tracing import load_spans


def test_workflow_records_agent_tool_retrieval_and_model_spans(tmp_path):
    trace_file = tmp_path / "traces.jsonl"
    workflow = SupportAgentWorkflow(JsonlTraceRecorder(trace_file))

    answer = workflow.run("Where can I find my invoice?")
    spans = load_spans(trace_file)

    assert "Invoice" in answer
    assert {span["kind"] for span in spans} == {"agent", "retrieval", "tool", "model"}
    assert len({span["trace_id"] for span in spans}) == 1
    assert all(span["status"] == "ok" for span in spans)


def test_recorder_captures_errors_and_analysis_finds_patterns(tmp_path):
    trace_file = tmp_path / "traces.jsonl"
    workflow = SupportAgentWorkflow(JsonlTraceRecorder(trace_file))

    with pytest.raises(RuntimeError, match="ticket service unavailable"):
        workflow.run("Check my support ticket", fail_tool=True)

    summary = TraceAnalysisAgent().summarize(trace_file)

    assert summary["trace_count"] == 1
    assert summary["failure_count"] == 2
    assert summary["failure_patterns"] == {"RuntimeError": 2}
    assert summary["tool_calls"] == {"ticket.lookup": 1}


def test_sample_trace_schema_is_json_serializable(tmp_path):
    trace_file = tmp_path / "traces.jsonl"
    recorder = JsonlTraceRecorder(trace_file)

    with recorder.span("demo", kind="agent", attributes={"prompt": "hello"}) as span:
        span.set(output="world")

    record = json.loads(trace_file.read_text())
    assert record["name"] == "demo"
    assert record["attributes"] == {"prompt": "hello", "output": "world"}
    assert record["parent_span_id"] is None
