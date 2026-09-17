"""Command-line entry points for offline and live evaluation runs."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from guardrail_eval_harness import reporting
from guardrail_eval_harness.evaluation import evaluate_scenarios
from guardrail_eval_harness.scenarios import load_scenarios

EXIT_PASS = 0
EXIT_FAILURES = 1
EXIT_CONFIG_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guardrail_eval_harness",
        description="Evaluate guardrail behavior of a scripted or live support agent.",
    )
    parser.add_argument(
        "--suite", choices=("default", "negative-controls"), default="default"
    )
    parser.add_argument(
        "--case", action="append", default=[], help="Scenario id; repeatable"
    )
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument(
        "--report", type=Path, default=None, help="Optional JSON report path"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace an existing report"
    )
    parser.add_argument(
        "--live-model",
        default=None,
        help="Explicit model name required for --mode live",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        scenarios = load_scenarios(args.suite, args.case or None)
    except (ValueError, FileNotFoundError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    if args.mode == "live":
        from guardrail_eval_harness.live import LiveBackend, live_report

        try:
            backend = LiveBackend(model_name=args.live_model)
        except ValueError as exc:
            print(f"configuration error: {exc}", file=sys.stderr)
            return EXIT_CONFIG_ERROR
        try:
            cases, totals, aggregate = live_report(backend, scenarios)
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"runner error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return EXIT_CONFIG_ERROR
    else:
        if args.live_model:
            print(
                "configuration error: --live-model requires --mode live",
                file=sys.stderr,
            )
            return EXIT_CONFIG_ERROR
        cases, totals, aggregate = evaluate_scenarios(scenarios, mode=args.mode)

    report = reporting.build_report(
        cases, totals, aggregate, mode=args.mode, suite=args.suite
    )
    print(reporting.render_console(cases, totals, aggregate, mode=args.mode))
    if args.report is not None:
        try:
            reporting.write_report(report, args.report, overwrite=args.overwrite)
        except (OSError, FileExistsError) as exc:
            print(f"report write failed: {exc}", file=sys.stderr)
            return EXIT_CONFIG_ERROR
    if aggregate == "error":
        return EXIT_CONFIG_ERROR
    if aggregate == "fail":
        return EXIT_FAILURES
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
