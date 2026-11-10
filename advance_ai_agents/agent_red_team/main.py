"""CLI for the prompt-injection red-team agent — defensive use only.

Run only against agents you own.

Usage:
    python main.py [--attacks attacks.json] [--report reports/report.md]
                   [--json reports/report.json] [--target demo|hardened]
                   [--variants 3]

By default the demo target is a deliberately vulnerable agent, so the
report shows what successful attacks look like. Use ``--target hardened``
to check that a hardened agent blocks every attack. No API key is
required: the default judge is rule-based and fully offline.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from red_team import (
    DemoTarget,
    HardenedTarget,
    Runner,
    load_attacks,
    report_json,
    report_markdown,
    summarize,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Prompt-injection red-team agent (defensive use only, "
            "only against agents you own)."
        )
    )
    here = Path(__file__).resolve().parent
    parser.add_argument(
        "--attacks",
        default=str(here / "attacks.json"),
        help="Path to the attacks JSON file.",
    )
    parser.add_argument(
        "--report",
        default=str(here / "reports" / "report.md"),
        help="Path to write the Markdown report to.",
    )
    parser.add_argument(
        "--json",
        default=str(here / "reports" / "report.json"),
        help="Path to write the JSON report to.",
    )
    parser.add_argument(
        "--target",
        choices=("demo", "hardened"),
        default="demo",
        help="Target agent: demo (vulnerable) or hardened (refuses).",
    )
    parser.add_argument(
        "--variants",
        type=int,
        default=3,
        help="Number of prompt variants to run per attack case.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the red-team suite and write the reports."""
    args = parse_args(argv)
    if args.variants <= 0:
        print("Error: --variants must be a positive integer.", file=sys.stderr)
        return 2
    provider = os.environ.get("LLM_PROVIDER", "offline")
    if provider != "offline":
        print(
            "Note: LLM_PROVIDER is set to "
            f"{provider!r}, but this offline build still uses the "
            "rule-based judge only. An LLM judge is a future option, "
            "not a requirement.",
        )
    cases = load_attacks(args.attacks)
    if not cases:
        print("No attacks found — nothing to run.")
        return 0
    target = DemoTarget() if args.target == "demo" else HardenedTarget()
    results = Runner(target, variants_per_case=args.variants).run(cases)
    summary = summarize(results)

    print("Prompt-injection red-team report")
    print("Defensive use only — only against agents you own.")
    print(
        f"Target: {args.target} ({len(cases)} cases, {len(results)} attempts)"
    )
    print()
    print(f"{'Category':<14}{'Attempts':>9}{'Succeeded':>11}{'Rate':>9}")
    for category in (
        "direct",
        "indirect",
        "exfiltration",
        "benign",
        "overall",
    ):
        row = summary[category]
        print(
            f"{category:<14}{row['total']:>9}{row['succeeded']:>11}"
            f"{float(row['rate']) * 100:>8.1f}%"
        )

    for path, content in (
        (args.report, report_markdown(results, summary)),
        (args.json, json.dumps(report_json(results, summary), indent=2)),
    ):
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content + "\n", encoding="utf-8")
        print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
