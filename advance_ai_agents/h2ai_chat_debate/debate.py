"""Core logic for a turn-based debate between several different LLMs.

This module deliberately contains no network calls and no console I/O, so the
whole conversation flow can be unit-tested without API keys. ``main.py`` wires
it to an OpenAI-compatible endpoint and to the human moderator.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_AGENTS_FILE = Path(__file__).with_name("agents.json")

# Every past turn is replayed to the next speaker with role="user", never
# role="assistant". Several OpenAI-compatible providers reject or mangle a
# history where "assistant" messages were not produced by that same model, and
# in a cross-vendor debate they never are.
HISTORY_ROLE = "user"


@dataclass(frozen=True)
class Agent:
    """One debater: a persona bound to a model on some provider."""

    name: str
    role: str
    model: str
    base_url: str
    api_key_env: str


@dataclass(frozen=True)
class Turn:
    """One thing said by one participant."""

    speaker: str
    text: str


@dataclass
class Debate:
    """A topic, a roster and everything said so far."""

    topic: str
    agents: list[Agent]
    total_rounds: int
    turns: list[Turn] = field(default_factory=list)

    def add(self, speaker: str, text: str) -> None:
        self.turns.append(Turn(speaker=speaker, text=text))

    def transcript(self) -> str:
        return format_transcript(self.turns)


def load_agents(path: Path | str | None = None) -> list[Agent]:
    """Read the roster from JSON and fail loudly on a malformed entry."""
    path = Path(path) if path is not None else DEFAULT_AGENTS_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path} must hold a non-empty list of agents")

    required = ("name", "role", "model", "base_url", "api_key_env")
    agents: list[Agent] = []
    for index, entry in enumerate(data):
        missing = [key for key in required if not entry.get(key)]
        if missing:
            raise ValueError(f"agent #{index + 1} in {path} is missing: {', '.join(missing)}")
        agents.append(Agent(**{key: entry[key] for key in required}))

    names = [agent.name for agent in agents]
    if len(set(names)) != len(names):
        raise ValueError("two agents share the same name, so the transcript would be ambiguous")
    if len(agents) < 2:
        raise ValueError("a debate needs at least two agents")
    return agents


def format_transcript(turns: list[Turn]) -> str:
    """Render the conversation so far as plain text."""
    if not turns:
        return "(nothing has been said yet: you open the debate)"
    return "\n\n".join(f"{turn.speaker}: {turn.text}" for turn in turns)


def build_system_prompt(agent: Agent, roster: list[Agent], topic: str) -> str:
    """Tell one debater who it is and who else is in the room."""
    others = [other for other in roster if other.name != agent.name]
    introductions = ", ".join(f"{other.name} ({other.role})" for other in others)
    return (
        f"You are {agent.name}, taking part in a debate about: {topic}\n"
        f"Your role is: {agent.role}\n"
        f"The other participants are: {introductions}\n\n"
        "Rules of this debate:\n"
        "- Answer the points others actually made. Quote them by name.\n"
        "- Do not repeat what has already been said; add something.\n"
        "- Change your mind out loud if someone convinces you.\n"
        "- Keep it under 150 words. Plain prose, no headings, no bullet lists."
    )


def build_messages(
    debate: Debate,
    agent: Agent,
    round_number: int,
    moderator_note: str | None = None,
) -> list[dict[str, str]]:
    """Build the exact payload sent to one debater for its turn."""
    context = [
        f"Round {round_number} of {debate.total_rounds}.",
        "",
        "Conversation so far:",
        debate.transcript(),
    ]
    if moderator_note:
        context += ["", f"The human moderator interrupts and says: {moderator_note}"]
    context += ["", f"{agent.name}, it is your turn. Speak now."]

    return [
        {"role": "system", "content": build_system_prompt(agent, debate.agents, debate.topic)},
        {"role": HISTORY_ROLE, "content": "\n".join(context)},
    ]


def speaking_order(agents: list[Agent], round_number: int) -> list[Agent]:
    """Rotate who opens each round, so nobody always speaks last."""
    if not agents:
        return []
    offset = (round_number - 1) % len(agents)
    return agents[offset:] + agents[:offset]
