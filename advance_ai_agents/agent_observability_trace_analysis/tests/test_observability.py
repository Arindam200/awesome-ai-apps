from __future__ import annotations

import json
import sys

import pytest

from agent_observability import JsonlTraceRecorder, SupportAgentWorkflow, TraceAnalysisAgent
from agent_observability.tracing import load_spans
from main import main


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


def test_explicit_trace_id_does_not_inherit_a_parent_from_another_trace(tmp_path):
    trace_file = tmp_path / "traces.jsonl"
    recorder = JsonlTraceRecorder(trace_file)

    with recorder.span("outer", kind="agent", trace_id="outer-trace"):
        with recorder.span("inner", kind="tool", trace_id="inner-trace"):
            pass

    inner = next(span for span in load_spans(trace_file) if span["name"] == "inner")
    assert inner["trace_id"] == "inner-trace"
    assert inner["parent_span_id"] is None


def test_recorder_captures_base_exceptions(tmp_path):
    trace_file = tmp_path / "traces.jsonl"
    recorder = JsonlTraceRecorder(trace_file)

    with pytest.raises(KeyboardInterrupt):
        with recorder.span("interrupted", kind="agent"):
            raise KeyboardInterrupt

    record = load_spans(trace_file)[0]
    assert record["status"] == "error"
    assert record["error"] == {"type": "KeyboardInterrupt", "message": ""}


def test_main_preserves_an_existing_trace_without_overwrite(tmp_path, monkeypatch):
    trace_file = tmp_path / "traces.jsonl"
    trace_file.write_text("existing\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["main.py", "--trace-file", str(trace_file)])

    with pytest.raises(SystemExit, match="Pass --overwrite"):
        main()

    assert trace_file.read_text(encoding="utf-8") == "existing\n"
