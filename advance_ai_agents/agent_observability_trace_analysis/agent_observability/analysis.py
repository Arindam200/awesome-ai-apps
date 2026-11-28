"""Deterministic and optional LLM-powered analysis of agent trace files."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from .tracing import load_spans


class TraceAnalysisAgent:
    """Summarize failures, slow spans, tool use, and retrieval quality across runs."""

    def summarize(self, trace_path: str | Path) -> dict[str, Any]:
        spans = load_spans(trace_path)
        traces = {span["trace_id"] for span in spans}
        failures = [span for span in spans if span["status"] == "error"]
        durations: dict[str, list[float]] = defaultdict(list)
        tools = Counter()
        retrieval_misses = 0

        for span in spans:
            durations[span["name"]].append(float(span["duration_ms"]))
            if span["kind"] == "tool":
                tools[span["name"]] += 1
            if span["kind"] == "retrieval" and span["attributes"].get("result_count") == 0:
                retrieval_misses += 1

        average_latency = {
            name: round(mean(values), 3) for name, values in sorted(durations.items())
        }
        slowest = sorted(average_latency.items(), key=lambda item: item[1], reverse=True)[:3]
        failure_patterns = Counter(
            (span.get("error") or {}).get("type", "UnknownError") for span in failures
        )
        return {
            "trace_count": len(traces),
            "span_count": len(spans),
            "failure_count": len(failures),
            "failure_patterns": dict(failure_patterns),
            "tool_calls": dict(tools),
            "retrieval_misses": retrieval_misses,
            "average_latency_ms": average_latency,
            "slowest_steps": [{"name": name, "average_ms": duration} for name, duration in slowest],
        }

    def analyze_with_nebius(self, summary: dict[str, Any]) -> str:
        """Ask a Nebius-hosted model for prioritized remediation advice."""

        api_key = os.getenv("NEBIUS_API_KEY")
        if not api_key:
            raise RuntimeError("Set NEBIUS_API_KEY to enable LLM-powered trace analysis")

        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("NEBIUS_BASE_URL", "https://api.studio.nebius.ai/v1"),
        )
        response = client.chat.completions.create(
            model=os.getenv("NEBIUS_MODEL", "meta-llama/Llama-3.3-70B-Instruct"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an agent reliability analyst. Identify recurring failures, "
                        "slow steps, and retrieval/tool problems. Return three prioritized, "
                        "actionable recommendations grounded only in the supplied summary."
                    ),
                },
                {"role": "user", "content": json.dumps(summary, indent=2)},
            ],
            temperature=0,
        )
        return response.choices[0].message.content or ""
