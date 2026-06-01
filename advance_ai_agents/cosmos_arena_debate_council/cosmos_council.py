"""Cosmos Arena - Multi-Agent Debate Council.

A LangGraph state machine that orchestrates a structured, multi-round debate
between specialized council member agents, then a Judge renders a verdict.

The graph drives the debate explicitly instead of relying on a single model to
delegate to itself: each council member is its own node and its own model call,
and the Moderator (the graph) threads the prior round's arguments into the next
member's prompt so rebuttals genuinely respond to what was just said.

Every council member runs on `nvidia/Cosmos3-Super-Reasoner` served by
Nebius Token Factory.

Flow
----
        ┌──────────────┐      ┌─────────────┐
START ─▶│  proponent   │ ───▶ │  opponent   │ ──▶ (more rounds?)
        └──────────────┘      └─────────────┘         │
              ▲  more rounds: next_round              │ no
              └───────────────────────────────────────┤
                                                       ▼
                                   (pragmatist?) ─▶ judge ─▶ END
"""

from __future__ import annotations

import operator
import os
import re
from typing import Annotated, TypedDict

from langchain_core.outputs import ChatResult
from langchain_nebius import ChatNebius
from langgraph.graph import END, START, StateGraph

# Token Factory is the relevant endpoint for NVIDIA-hosted models (same as the
# Nemotron examples in this repo). Override with NEBIUS_BASE_URL if needed.
DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "nvidia/Cosmos3-Super-Reasoner"

# Reasoning models (Cosmos) can wrap chain-of-thought in <think> tags. We keep
# the reasoning so the UI can show it, but never mix it into the argument text.
_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)


def split_reasoning(text: str) -> tuple[str, str]:
    """Separate the visible answer from the model's <think> reasoning."""
    text = text or ""
    reasoning_parts = [m.strip() for m in _THINK_RE.findall(text)]
    clean = _THINK_RE.sub("", text).strip()
    if "<think>" in clean.lower():  # unclosed reasoning block
        idx = clean.lower().index("<think>")
        reasoning_parts.append(clean[idx + len("<think>"):].strip())
        clean = clean[:idx].strip()
    return clean.strip(), "\n\n".join(p for p in reasoning_parts if p).strip()


class CosmosChatNebius(ChatNebius):
    """ChatNebius that surfaces the non-standard ``reasoning`` field.

    The Cosmos reasoner served by Token Factory frequently returns its answer in
    the ``reasoning`` field of the response and leaves ``content`` empty. The
    stock integration drops ``reasoning``, so every council member would come
    back blank. We fold it back in: if ``content`` is empty the reasoning *is*
    the answer; otherwise we keep it as separate chain-of-thought for the UI.
    """

    def _create_chat_result(self, response, generation_info=None) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)
        response_dict = response if isinstance(response, dict) else response.model_dump()
        for gen, choice in zip(result.generations, response_dict.get("choices") or []):
            reasoning = (choice.get("message") or {}).get("reasoning")
            if not reasoning:
                continue
            message = gen.message
            if (message.content or "").strip():
                message.additional_kwargs.setdefault("reasoning_content", reasoning)
            else:
                message.content = reasoning
        return result


def build_model(
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.6,
) -> ChatNebius:
    """Create the shared Cosmos reasoner backed by Nebius Token Factory."""
    return CosmosChatNebius(
        model=model or os.getenv("COSMOS_MODEL", DEFAULT_MODEL),
        api_key=api_key or os.getenv("NEBIUS_API_KEY"),
        base_url=base_url or os.getenv("NEBIUS_BASE_URL") or DEFAULT_BASE_URL,
        temperature=temperature,
    )


# --------------------------------------------------------------------------- #
# Council member personas
# --------------------------------------------------------------------------- #

PROPONENT_PROMPT = (
    "You are The Advocate, a council member in the Cosmos Arena debate.\n"
    "Your role: argue persuasively and rigorously IN FAVOR of the motion.\n\n"
    "Guidelines:\n"
    "- Make the strongest honest case for the motion.\n"
    "- Ground claims in reasoning, evidence, and concrete examples.\n"
    "- If you are given the opposition's prior argument, directly REBUT it "
    "point by point before adding new arguments.\n"
    "- Be sharp and confident, but never fabricate facts.\n"
    "- Keep it focused: 3-5 tight paragraphs or bullet clusters in markdown. "
    "End with your single strongest line.\n"
    "- Output ONLY your argument. Do not narrate your process or add headings "
    "naming yourself."
)

OPPONENT_PROMPT = (
    "You are The Skeptic, a council member in the Cosmos Arena debate.\n"
    "Your role: argue persuasively and rigorously AGAINST the motion.\n\n"
    "Guidelines:\n"
    "- Make the strongest honest case opposing the motion.\n"
    "- Expose weak assumptions, costs, risks, and counterexamples.\n"
    "- If you are given the proponent's prior argument, directly REBUT it "
    "point by point before adding new arguments.\n"
    "- Be incisive, but never fabricate facts.\n"
    "- Keep it focused: 3-5 tight paragraphs or bullet clusters in markdown. "
    "End with your single strongest line.\n"
    "- Output ONLY your argument. Do not narrate your process or add headings "
    "naming yourself."
)

PRAGMATIST_PROMPT = (
    "You are The Pragmatist, an independent council member in the Cosmos Arena "
    "debate. You favor neither side.\n\n"
    "Your role:\n"
    "- Pressure-test BOTH the proponent's and opponent's arguments.\n"
    "- Surface hidden assumptions, practical constraints, and second-order "
    "effects each side ignored.\n"
    "- Identify what evidence or conditions would actually decide the question "
    "in the real world.\n"
    "- Be even-handed and concrete. 3-4 paragraphs maximum, in markdown.\n"
    "- Output ONLY your analysis. Do not narrate your process."
)

JUDGE_PROMPT = (
    "You are The Arbiter, the impartial judge of the Cosmos Arena debate.\n"
    "You will be given the full debate transcript.\n\n"
    "Deliver your verdict as markdown with EXACTLY these sections:\n\n"
    "### Scorecard\n"
    "A markdown table scoring each side (Proponent, Opponent) from 0-10 on "
    "**Logic**, **Evidence**, and **Rebuttal**, with a **Total** column.\n\n"
    "### Verdict\n"
    "State the winner (or an honest draw) in one bold sentence, then 2-3 "
    "sentences justifying it based strictly on the arguments made.\n\n"
    "### Strongest Argument\n"
    "Quote or paraphrase the single most decisive point from the debate.\n\n"
    "### What Would Change the Outcome\n"
    "One short paragraph on the evidence or reasoning that would flip the "
    "result. Be rigorous and unbiased.\n\n"
    "Output ONLY the verdict sections. Do not narrate your process."
)

# Stable metadata used by both the engine and the UI.
MEMBERS: dict[str, dict] = {
    "proponent": {"name": "The Advocate", "side": "FOR the motion"},
    "opponent": {"name": "The Skeptic", "side": "AGAINST the motion"},
    "pragmatist": {"name": "The Pragmatist", "side": "Reality check"},
    "judge": {"name": "The Arbiter", "side": "Verdict"},
}


# --------------------------------------------------------------------------- #
# Graph state
# --------------------------------------------------------------------------- #

class Turn(TypedDict):
    speaker: str          # proponent | opponent | pragmatist | judge
    round: int            # debate round this turn belongs to (0 for judge)
    text: str             # the visible argument
    reasoning: str        # the model's <think> reasoning, if any


class DebateState(TypedDict):
    motion: str
    current_round: int
    # `operator.add` makes each node append its single turn to the running
    # transcript, so streaming `updates` yields exactly one new turn per step.
    transcript: Annotated[list[Turn], operator.add]


# --------------------------------------------------------------------------- #
# Transcript helpers
# --------------------------------------------------------------------------- #

def _latest(transcript: list[Turn], speaker: str) -> str:
    for turn in reversed(transcript):
        if turn["speaker"] == speaker:
            return turn["text"]
    return ""


def _full_transcript(transcript: list[Turn]) -> str:
    lines = []
    for turn in transcript:
        name = MEMBERS[turn["speaker"]]["name"]
        tag = f" (Round {turn['round']})" if turn["round"] else ""
        lines.append(f"## {name}{tag}\n\n{turn['text']}")
    return "\n\n".join(lines)


# --------------------------------------------------------------------------- #
# Graph construction
# --------------------------------------------------------------------------- #

def build_debate_graph(
    model: ChatNebius,
    rounds: int = 2,
    use_pragmatist: bool = True,
):
    """Compile the Cosmos Arena debate as an explicit LangGraph state machine.

    Each council member is a node and a single model call. The graph loops the
    proponent/opponent pair for `rounds` rounds, optionally runs the pragmatist,
    then renders the judge's verdict.
    """

    def _say(system_prompt: str, user_prompt: str) -> tuple[str, str]:
        response = model.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        content = response.content
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict)
            )
        answer, inline_reasoning = split_reasoning(content or "")
        # `reasoning_content` holds chain-of-thought the model returned alongside
        # a real answer (see CosmosChatNebius); prefer it over any inline <think>.
        reasoning = response.additional_kwargs.get("reasoning_content") or inline_reasoning
        return answer, reasoning

    def proponent_node(state: DebateState) -> dict:
        rnd = state["current_round"]
        if rnd == 1:
            user = (
                f"The motion before the council:\n\n> {state['motion']}\n\n"
                "Deliver your OPENING case in favor of the motion."
            )
        else:
            user = (
                f"The motion before the council:\n\n> {state['motion']}\n\n"
                "The Skeptic's most recent argument was:\n\n"
                f"{_latest(state['transcript'], 'opponent')}\n\n"
                f"This is round {rnd}. Rebut the Skeptic point by point, then "
                "press your strongest new arguments for the motion."
            )
        text, reasoning = _say(PROPONENT_PROMPT, user)
        return {"transcript": [Turn(speaker="proponent", round=rnd, text=text, reasoning=reasoning)]}

    def opponent_node(state: DebateState) -> dict:
        rnd = state["current_round"]
        if rnd == 1:
            user = (
                f"The motion before the council:\n\n> {state['motion']}\n\n"
                "The Advocate has just opened in favor:\n\n"
                f"{_latest(state['transcript'], 'proponent')}\n\n"
                "Deliver your OPENING case against the motion. You may engage "
                "the Advocate's points, but make your own strongest case."
            )
        else:
            user = (
                f"The motion before the council:\n\n> {state['motion']}\n\n"
                "The Advocate's most recent argument was:\n\n"
                f"{_latest(state['transcript'], 'proponent')}\n\n"
                f"This is round {rnd}. Rebut the Advocate point by point, then "
                "press your strongest new arguments against the motion."
            )
        text, reasoning = _say(OPPONENT_PROMPT, user)
        return {"transcript": [Turn(speaker="opponent", round=rnd, text=text, reasoning=reasoning)]}

    def increment_round_node(state: DebateState) -> dict:
        return {"current_round": state["current_round"] + 1}

    def pragmatist_node(state: DebateState) -> dict:
        user = (
            f"The motion before the council:\n\n> {state['motion']}\n\n"
            "Here is the full debate so far:\n\n"
            f"{_full_transcript(state['transcript'])}\n\n"
            "Stress-test both sides."
        )
        text, reasoning = _say(PRAGMATIST_PROMPT, user)
        return {"transcript": [Turn(speaker="pragmatist", round=0, text=text, reasoning=reasoning)]}

    def judge_node(state: DebateState) -> dict:
        user = (
            f"The motion debated:\n\n> {state['motion']}\n\n"
            "Full transcript of the debate:\n\n"
            f"{_full_transcript(state['transcript'])}\n\n"
            "Deliver your verdict."
        )
        text, reasoning = _say(JUDGE_PROMPT, user)
        return {"transcript": [Turn(speaker="judge", round=0, text=text, reasoning=reasoning)]}

    def route_after_opponent(state: DebateState) -> str:
        if state["current_round"] < rounds:
            return "increment_round"
        return "pragmatist" if use_pragmatist else "judge"

    builder = StateGraph(DebateState)
    builder.add_node("proponent", proponent_node)
    builder.add_node("opponent", opponent_node)
    builder.add_node("increment_round", increment_round_node)
    builder.add_node("judge", judge_node)
    if use_pragmatist:
        builder.add_node("pragmatist", pragmatist_node)

    builder.add_edge(START, "proponent")
    builder.add_edge("proponent", "opponent")
    builder.add_conditional_edges(
        "opponent",
        route_after_opponent,
        ["increment_round", "pragmatist", "judge"]
        if use_pragmatist
        else ["increment_round", "judge"],
    )
    builder.add_edge("increment_round", "proponent")
    if use_pragmatist:
        builder.add_edge("pragmatist", "judge")
    builder.add_edge("judge", END)

    return builder.compile()


def initial_state(motion: str) -> DebateState:
    """Build the starting state for a debate run."""
    return DebateState(motion=motion, current_round=1, transcript=[])


def create_debate_council(
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    rounds: int = 2,
    use_pragmatist: bool = True,
    temperature: float = 0.6,
):
    """Build the Cosmos Arena debate council as a compiled LangGraph graph."""
    cosmos = build_model(
        api_key=api_key, model=model, base_url=base_url, temperature=temperature
    )
    return build_debate_graph(cosmos, rounds=rounds, use_pragmatist=use_pragmatist)
