"""CLI entrypoint for the Briefing Room pre-meeting intel agent.

Usage:
    python main.py "Acme Corp" --attendee "Jane Doe, CTO" --context "pitching a partnership"
"""

import argparse
from pathlib import Path

from dotenv import load_dotenv

from graph import (
    build_graph,
    build_model,
    build_search,
    initial_state,
    merge_stream_update,
)

ENV_FILE = Path(__file__).resolve().with_name(".env")
load_dotenv(ENV_FILE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a pre-meeting brief.")
    parser.add_argument("company", help="Company you are meeting with")
    parser.add_argument("--attendee", default="", help="Person you are meeting (optional)")
    parser.add_argument("--context", default="", help="Your context/goal (optional)")
    parser.add_argument("--model", default=None, help="Nebius Token Factory model id")
    parser.add_argument("--max-iterations", type=int, default=2, help="Max research passes")
    args = parser.parse_args()

    graph = build_graph(build_model(model=args.model), build_search())
    state = initial_state(
        company=args.company,
        attendee=args.attendee,
        user_context=args.context,
        max_iterations=args.max_iterations,
    )

    final = dict(state)
    for chunk in graph.stream(state, stream_mode="updates"):
        for node, update in chunk.items():
            if node == "plan":
                print(f"🧭 Plan: {len(update.get('sub_questions', []))} research questions")
                for q in update.get("sub_questions", []):
                    print(f"   - {q}")
            elif node == "research":
                print(f"🔎 Research: +{len(update.get('evidence', []))} sources")
            elif node == "reflect":
                gaps = update.get("gaps", [])
                print("🧐 Reflect: " + (f"gaps -> {gaps}" if gaps else "coverage sufficient"))
            elif node == "write":
                print("✍️  Writing brief…\n")
            final = merge_stream_update(final, update)

    print(final.get("brief", "(no brief produced)"))


if __name__ == "__main__":
    main()
