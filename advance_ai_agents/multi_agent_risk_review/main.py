"""CLI entrypoint for the Multi-Agent Risk Review.

Usage:
    python main.py samples/vendor_rollout_plan.md
"""

import argparse
import sys
from pathlib import Path

from graph import (
    MissingAPIKeyError,
    build_graph,
    build_model,
    initial_state,
    render_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review a proposal, contract or deployment plan for risk."
    )
    parser.add_argument("document", type=Path, help="Text or Markdown file to review")
    parser.add_argument("--model", default=None, help="Nebius Token Factory model id")
    args = parser.parse_args()

    try:
        document = args.document.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        sys.exit(f"error: cannot read {args.document}: {exc}")
    if not document.strip():
        sys.exit(f"error: {args.document} is empty")

    try:
        llm = build_model(model=args.model)
    except MissingAPIKeyError as exc:
        sys.exit(f"error: {exc}")

    print(
        "Reviewing with the security, legal, finance and operations reviewers...",
        file=sys.stderr,
    )
    final = build_graph(llm).invoke(initial_state(document))
    print(render_markdown(final))


if __name__ == "__main__":
    main()
