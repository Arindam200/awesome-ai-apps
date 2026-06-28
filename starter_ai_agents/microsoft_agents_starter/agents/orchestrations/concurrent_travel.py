"""Concurrent orchestration — travel specialists working in parallel.

Pattern
-------
In CONCURRENT orchestration every agent receives the SAME task and works on it
*simultaneously and independently*. Their answers are then aggregated. This is
ideal for gathering diverse perspectives on one question (ensemble reasoning).

Specialists used here (4 agents, all run at once):

    FlightExpert   : flight strategy / routing advice
    HotelExpert    : lodging recommendations
    ActivitiesExpert : things to do / experiences
    BudgetExpert   : cost-control and money-saving advice

A custom aggregator then asks a SummarizerAgent to fuse the four expert
opinions into one cohesive travel brief.

Docs: https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/concurrent

Run:
    python agents/orchestrations/concurrent_travel.py
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from agent_framework import Agent, AgentExecutorResponse
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework.orchestrations import ConcurrentBuilder
from monocle_apptrace import setup_monocle_telemetry

setup_monocle_telemetry(
    workflow_name="okahu_demos_ms_openai_concurrent_travel",
    monocle_exporters_list="file",
)


def _client() -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model="Qwen/Qwen3.5-397B-A17B",
        api_key=os.getenv("NEBIUS_API_KEY"),
        base_url="https://api.tokenfactory.nebius.com/v1/",
    )


# --------------------------------------------------------------------------- #
# Four independent specialists (each gets the full task at the same time)
# --------------------------------------------------------------------------- #
flight_expert = Agent(
    client=_client(),
    name="FlightExpert",
    description="Aviation and routing specialist.",
    instructions=(
        "You are a flight expert. For the given trip, recommend the smartest "
        "routing, ideal booking window, and cabin/airline tips. Be concise."
    ),
)

hotel_expert = Agent(
    client=_client(),
    name="HotelExpert",
    description="Lodging specialist.",
    instructions=(
        "You are a hotel expert. For the given trip, recommend the best "
        "neighborhoods to stay in and the type of lodging that fits. Be concise."
    ),
)

activities_expert = Agent(
    client=_client(),
    name="ActivitiesExpert",
    description="Local experiences specialist.",
    instructions=(
        "You are an activities expert. For the given trip, suggest the top 5 "
        "experiences and any seasonal events worth catching. Be concise."
    ),
)

budget_expert = Agent(
    client=_client(),
    name="BudgetExpert",
    description="Cost-control specialist.",
    instructions=(
        "You are a budget expert. For the given trip, list realistic cost ranges "
        "and 3 concrete money-saving tactics. Be concise."
    ),
)

# Aggregator agent: fuses the four parallel outputs into one brief.
summarizer = Agent(
    client=_client(),
    name="Summarizer",
    description="Consolidates expert outputs into one cohesive brief.",
    instructions=(
        "You consolidate multiple travel experts' notes into one cohesive, "
        "well-structured travel brief with clear sections. Keep it under 250 words."
    ),
)


async def summarize_results(results: list[AgentExecutorResponse]) -> str:
    """Custom aggregator: collect each expert's final message, then summarize."""
    sections: list[str] = []
    for r in results:
        messages = getattr(r.agent_response, "messages", [])
        text = messages[-1].text if messages else "(no content)"
        sections.append(f"## {r.executor_id}\n{text}")
    fused = await summarizer.run("\n\n".join(sections))
    return fused.messages[-1].text if fused.messages else ""


async def main() -> None:
    workflow = (
        ConcurrentBuilder(
            participants=[flight_expert, hotel_expert, activities_expert, budget_expert]
        )
        .with_aggregator(summarize_results)
        .build()
    )

    task = (
        "We are planning a 5-day trip from Chicago to Tokyo in October 2026 "
        "for two people with a mid-range budget."
    )

    result = await workflow.run(task)

    print("===== Consolidated Travel Brief (4 experts, run in parallel) =====")
    for output in result.get_outputs():
        print(output)


if __name__ == "__main__":
    asyncio.run(main())
