"""Run a turn-based debate between several LLMs, with a human moderating.

    python main.py --topic "Should AI systems have the right to refuse a task?"
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel

from debate import Agent, Debate, build_messages, load_agents, speaking_order

console = Console()

COLOURS = ("cyan", "magenta", "green", "yellow", "blue", "red")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True, help="what the models should argue about")
    parser.add_argument("--rounds", type=int, default=3, help="how many turns each model takes")
    parser.add_argument("--agents", default=None, help="path to a roster file (default: agents.json)")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="do not stop for the moderator between rounds",
    )
    return parser.parse_args()


def client_for(agent: Agent) -> OpenAI:
    """One client per agent, so each can live on a different provider."""
    api_key = os.getenv(agent.api_key_env)
    if not api_key:
        raise SystemExit(
            f"{agent.name} needs {agent.api_key_env} to be set. "
            "Copy .env.example to .env and fill it in. "
            "For a local model (Ollama, LM Studio) any non-empty value will do."
        )
    return OpenAI(base_url=agent.base_url, api_key=api_key)


def ask(agent: Agent, messages: list[dict[str, str]]) -> str:
    """Ask one model for its turn. A failure ends that turn, not the debate."""
    try:
        response = client_for(agent).chat.completions.create(
            model=agent.model,
            messages=messages,
            temperature=0.8,
            timeout=90,
        )
    except Exception as error:  # noqa: BLE001 - any provider error is just a lost turn
        return f"(no answer: {type(error).__name__}: {error})"
    return (response.choices[0].message.content or "").strip()


def moderator_note() -> str | None:
    """Let the human steer, or walk away. Empty input just moves on."""
    console.print("[dim]Moderator — say something to steer the next round, "
                  "Enter to let them carry on, or 'q' to stop.[/dim]")
    try:
        note = input("> ").strip()
    except EOFError:
        return None
    if note.lower() in {"q", "quit", "exit"}:
        raise SystemExit(0)
    return note or None


def main() -> int:
    load_dotenv()
    args = parse_args()

    agents = load_agents(args.agents)
    debate = Debate(topic=args.topic, agents=agents, total_rounds=args.rounds)

    roster = ", ".join(f"{agent.name} ({agent.model})" for agent in agents)
    console.print(Panel(f"[bold]{args.topic}[/bold]\n\n{roster}", title="H2AI Chat — debate"))

    note: str | None = None
    for round_number in range(1, args.rounds + 1):
        console.rule(f"Round {round_number} of {args.rounds}")
        for agent in speaking_order(agents, round_number):
            colour = COLOURS[agents.index(agent) % len(COLOURS)]
            with console.status(f"{agent.name} is thinking..."):
                messages = build_messages(debate, agent, round_number, note)
                answer = ask(agent, messages)
            debate.add(agent.name, answer)
            console.print(Panel(answer, title=f"[{colour}]{agent.name} — {agent.role}[/{colour}]"))
            note = None

        if not args.auto and round_number < args.rounds:
            note = moderator_note()

    console.rule("End of debate")
    console.print(f"[dim]{len(debate.turns)} turns. "
                  f"The full thing, with the web version: https://h2aichat.com[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
