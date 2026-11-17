"""Generate sample agent traces and analyze them locally or with Nebius."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from agent_observability import JsonlTraceRecorder, SupportAgentWorkflow, TraceAnalysisAgent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-file", type=Path, default=Path("traces/agent_runs.jsonl"))
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing trace file instead of preserving it",
    )
    parser.add_argument("--llm-analysis", action="store_true")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    if args.trace_file.exists():
        if not args.overwrite:
            raise SystemExit(
                f"Trace file already exists: {args.trace_file}. Pass --overwrite to replace it."
            )
        args.trace_file.unlink()

    workflow = SupportAgentWorkflow(JsonlTraceRecorder(args.trace_file))
    prompts = [
        ("Where can I find my invoice?", False),
        ("How do I reset my password?", False),
        ("Check my support ticket", True),
    ]
    for prompt, fail_tool in prompts:
        try:
            print(workflow.run(prompt, fail_tool=fail_tool))
        except RuntimeError as error:
            print(f"Run failed: {error}")

    analyzer = TraceAnalysisAgent()
    summary = analyzer.summarize(args.trace_file)
    print("\nLocal analysis:\n" + json.dumps(summary, indent=2))
    if args.llm_analysis:
        print("\nNebius analysis:\n" + analyzer.analyze_with_nebius(summary))


if __name__ == "__main__":
    main()
