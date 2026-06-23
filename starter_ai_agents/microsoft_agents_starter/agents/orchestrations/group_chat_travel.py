"""Group chat orchestration — travel agents collaborating in one room.

Pattern
-------
In GROUP CHAT orchestration a central orchestrator coordinates a shared
conversation, deciding who speaks next (round-robin, a selector function, or an
agent-based orchestrator). All agents see the full history and iteratively
refine each other's work until a termination condition is met.

Agents used here (3 agents in a shared chat):

    Planner   : proposes / revises the itinerary
    BudgetHawk: pushes back on cost, demands cheaper alternatives
    Reviewer  : final quality gate; says "APPROVED" when the plan is solid

Speaker selection: a custom round-robin selector cycles
    Planner -> BudgetHawk -> Reviewer -> Planner -> ...
Termination: stop once the Reviewer says "APPROVED" (or after a max of rounds).

Docs: https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/group-chat

Run:
    python agents/orchestrations/group_chat_travel.py
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from agent_framework import Agent, AgentResponse, AgentResponseUpdate
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework.orchestrations import GroupChatBuilder, GroupChatState
from monocle_apptrace import setup_monocle_telemetry

setup_monocle_telemetry(
    workflow_name="okahu_demos_ms_openai_groupchat_travel",
    monocle_exporters_list="file",
)


def _client() -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model="Qwen/Qwen3.5-397B-A17B",
        api_key=os.getenv("NEBIUS_API_KEY"),
        base_url="https://api.tokenfactory.nebius.com/v1/",
    )


# --------------------------------------------------------------------------- #
# Three collaborators
# --------------------------------------------------------------------------- #
planner = Agent(
    client=_client(),
    name="Planner",
    description="Proposes and revises the travel itinerary.",
    instructions=(
        "You are the trip planner. Propose a concrete itinerary. When the budget "
        "hawk or reviewer gives feedback, revise the plan accordingly. Keep it tight."
    ),
)

budget_hawk = Agent(
    client=_client(),
    name="BudgetHawk",
    description="Challenges the plan on cost.",
    instructions=(
        "You are a cost-conscious critic. Scrutinize the planner's itinerary for "
        "overspending and demand specific cheaper alternatives. Be direct and brief."
    ),
)

reviewer = Agent(
    client=_client(),
    name="Reviewer",
    description="Final quality gate for the itinerary.",
    instructions=(
        "You are the senior reviewer. If the itinerary is realistic, well-priced "
        "and complete, reply starting with the single word 'APPROVED' followed by a "
        "one-line summary. Otherwise, give one round of specific fixes."
    ),
)


def round_robin_selector(state: GroupChatState) -> str:
    """Cycle Planner -> BudgetHawk -> Reviewer based on the round index."""
    names = list(state.participants.keys())
    return names[state.current_round % len(names)]


def approved(conversation) -> bool:
    """Terminate once the Reviewer approves, or after 6 messages as a safety cap."""
    if conversation:
        last = conversation[-1]
        if last.author_name == "Reviewer" and "approved" in last.text.lower():
            return True
    return len(conversation) >= 6


async def main() -> None:
    workflow = GroupChatBuilder(
        participants=[planner, budget_hawk, reviewer],
        termination_condition=approved,
        selection_func=round_robin_selector,
    ).build()

    task = (
        "Plan a 3-day budget weekend in Barcelona for two friends, total budget "
        "under $1,200 including flights from London."
    )

    print(f"Task: {task}\n" + "=" * 80)
    result = await workflow.run(task)

    for output in result.get_outputs():
        msgs = getattr(output, "messages", None)
        if msgs is not None:
            for msg in msgs:
                print(f"\n[{getattr(msg, 'author_name', None) or 'assistant'}]\n{msg.text}")
        else:
            author = getattr(output, "author_name", None) or "assistant"
            text = getattr(output, "text", None)
            print(f"\n[{author}]\n{text if text is not None else output}")


if __name__ == "__main__":
    asyncio.run(main())
