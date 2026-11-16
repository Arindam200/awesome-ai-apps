"""Two agents that share one memory through ClickHouse Loom.

The planner saves what the user tells it with a `remember` tool. The reviewer, run later
in another process with no chat history, answers with a `recall` tool that searches the
same Loom namespace, and cites the memory keys it used.

    python main.py --agent planner "We deploy on Tuesdays and Thursdays, never on Fridays."
    python main.py --agent reviewer "Can I ship the billing fix on Friday?"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from typing import Any

from dotenv import load_dotenv
from loom import Agent
from loom.errors import BackendUnavailable
from openai import AsyncOpenAI, OpenAIError

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"
MAX_TURNS = 6

INSTRUCTIONS = {
    "planner": (
        "You are the planner on a small software team. The user tells you about the "
        "project. Save every durable fact (a decision, a constraint, an owner, a date) "
        "with the remember tool, one fact per call, under a short snake_case key. Then "
        "say in one sentence what you saved. Do not save greetings or questions."
    ),
    "reviewer": (
        "You are the reviewer on a small software team. Before you answer, search the "
        "team's memory with the recall tool. Answer only from the memories it returns. "
        "End every sentence that uses a memory with that memory's key in the form "
        "(#key), as recall shows it. If no memory is relevant, say that the team has "
        "not recorded it."
    ),
}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save one durable fact to the team's shared memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "A short snake_case name"},
                    "fact": {"type": "string", "description": "The fact as one sentence"},
                },
                "required": ["key", "fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Search the team's shared memory by meaning.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]


async def remember(memory: Any, key: str, fact: str) -> str:
    result = await memory.set(key, fact)
    # Loom merges a fact it already holds into the existing memory instead of copying it.
    merged = result.get("merged_into_key")
    return f"already saved as {merged}" if merged else f"saved {key}"


async def recall(memory: Any, query: str, seen: set[str]) -> str:
    # memory.search reads what every agent in the namespace wrote, not only this agent.
    hits = await memory.search(query, top_k=5)
    seen.update(hit.memory_key for hit in hits)
    lines = [f"[{hit.memory_key}] {hit.content_excerpt}" for hit in hits]
    return "\n".join(lines) or "no memories match"


async def call_tool(memory: Any, name: str, arguments: str, seen: set[str]) -> str:
    try:
        args = json.loads(arguments or "{}")
        if name == "remember":
            return await remember(memory, args["key"], args["fact"])
        if name == "recall":
            return await recall(memory, args["query"], seen)
    except (KeyError, TypeError, ValueError) as exc:
        return f"bad arguments for {name}: {exc!r}"
    return f"unknown tool {name}"


def unknown_citations(answer: str, seen: set[str]) -> list[str]:
    """Keys the answer cites, as [key] or (#key), that no recall returned."""
    cited = re.findall(r"(?:\[|\(#)([A-Za-z0-9_./-]+)[\])]", answer)
    return [key for key in dict.fromkeys(cited) if key not in seen]


async def run_agent(llm: Any, model: str, memory: Any, agent_name: str, prompt: str) -> str:
    """The tool-calling loop: the model calls the tools until it answers in text."""
    seen: set[str] = set()
    messages: list[Any] = [
        {"role": "system", "content": INSTRUCTIONS[agent_name]},
        {"role": "user", "content": prompt},
    ]
    for _ in range(MAX_TURNS):
        response = await llm.chat.completions.create(model=model, messages=messages, tools=TOOLS)
        message = response.choices[0].message
        if not message.tool_calls:
            answer = (message.content or "").strip()
            if not answer:
                raise RuntimeError(f"{model} returned an empty reply")
            unknown = unknown_citations(answer, seen)
            if unknown:
                # A model can invent a key; say so instead of passing it on as a source.
                answer += "\n(Not found in memory: " + ", ".join(unknown) + ")"
            return answer
        messages.append(message)
        for call in message.tool_calls:
            result = await call_tool(memory, call.function.name, call.function.arguments, seen)
            print(f"  {agent_name} -> {call.function.name}: {result.splitlines()[0]}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    return "Stopped after too many tool calls."


async def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Two agents that share one Loom memory.")
    parser.add_argument("--agent", choices=sorted(INSTRUCTIONS), required=True)
    parser.add_argument("prompt")
    args = parser.parse_args()

    api_key = os.environ.get("NEBIUS_API_KEY", "")
    if not api_key:
        print("NEBIUS_API_KEY is not set: copy .env.example to .env and add it.", file=sys.stderr)
        return 2
    base_url = os.environ.get("NEBIUS_BASE_URL") or DEFAULT_BASE_URL
    llm = AsyncOpenAI(api_key=api_key, base_url=base_url)
    model = os.environ.get("NEBIUS_MODEL") or DEFAULT_MODEL

    # Both agents use one org and namespace: that is what makes the memory shared.
    # Loom records each write under the agent that made it.
    try:
        async with Agent(
            org=os.environ.get("LOOM_ORG") or "dev",
            namespace=os.environ.get("LOOM_NAMESPACE") or "local",
            agent=args.agent,
        ) as loom:
            answer = await run_agent(llm, model, loom.memory, args.agent, args.prompt)
    except BackendUnavailable:
        url = os.environ.get("LOOM_BASE_URL") or "http://localhost:7777"
        print(f"Loom is not reachable at {url}: start it with the installer.", file=sys.stderr)
        return 1
    except OpenAIError as exc:
        print(f"The model endpoint refused the request: {exc}", file=sys.stderr)
        return 1
    print(f"{args.agent}: {answer}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
