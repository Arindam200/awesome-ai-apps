"""CLI: python app.py "How many sick days do I get?" (or run without args for a REPL)."""
import sys

from dotenv import load_dotenv

load_dotenv()

from triage import build_agent  # noqa: E402


def show(a):
    tag = "FALLBACK" if a.fallback else "ANSWER"
    print(f"\n[{tag}] intent={a.intent} confidence={a.confidence:.2f}\n{a.answer}")
    for i, c in enumerate(a.citations, 1):
        print(f"  [{i}] {c}")


def main():
    agent = build_agent()
    if len(sys.argv) > 1:
        show(agent.ask(" ".join(sys.argv[1:])))
        return
    while True:
        try:
            q = input("\nQuestion (empty to quit): ").strip()
        except EOFError:
            break
        if not q:
            break
        show(agent.ask(q))


if __name__ == "__main__":
    main()
