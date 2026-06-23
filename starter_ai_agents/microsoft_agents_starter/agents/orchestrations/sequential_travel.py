"""Sequential orchestration — a pipeline of travel agents.

Pattern
-------
In SEQUENTIAL orchestration agents run one after another in a fixed order.
Each agent sees the conversation so far and adds its contribution, then passes
the (now richer) conversation to the next agent. This is ideal when every step
*builds on* the previous one.

Pipeline used here (4 agents):

    DestinationResearcher  ->  FlightPlanner  ->  HotelPlanner  ->  ItineraryWriter

    1. DestinationResearcher : gathers facts about the destination.
    2. FlightPlanner         : picks flights (uses the search_flights tool).
    3. HotelPlanner          : picks lodging (uses the search_hotels tool).
    4. ItineraryWriter       : synthesizes everything into a day-by-day plan.

Docs: https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/sequential

Run:
    python agents/orchestrations/sequential_travel.py
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from agent_framework import Agent, AgentResponse, tool
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework.orchestrations import SequentialBuilder
from monocle_apptrace import setup_monocle_telemetry

# Enable Monocle tracing so every agent/tool call in the pipeline is captured.
setup_monocle_telemetry(
    workflow_name="okahu_demos_ms_openai_sequential_travel",
    monocle_exporters_list="file",
)


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@tool(approval_mode="never_require")
def search_flights(origin: str, destination: str, date: str) -> str:
    """Search for flights between two cities on a given date."""
    return (
        f"Flights {origin}->{destination} on {date}: "
        f"Delta $320 (08:00), United $290 (11:30), JetBlue $275 (17:45)."
    )


@tool(approval_mode="never_require")
def search_hotels(city: str, checkin: str, checkout: str) -> str:
    """Search for hotels in a city for the given date range."""
    return (
        f"Hotels in {city} ({checkin}->{checkout}): "
        f"Marriott $180/night, Hilton $165/night, Airbnb loft $120/night."
    )


# --------------------------------------------------------------------------- #
# Agents (each is a stage in the pipeline)
# --------------------------------------------------------------------------- #
def _client() -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model="Qwen/Qwen3.5-397B-A17B",
        api_key=os.getenv("NEBIUS_API_KEY"),
        base_url="https://api.tokenfactory.nebius.com/v1/",
    )


researcher = Agent(
    client=_client(),
    name="DestinationResearcher",
    description="Gathers concise, factual background about the destination.",
    instructions=(
        "You are a destination researcher. Given a trip request, list the best "
        "season to visit, 3 must-see neighborhoods/areas, and any travel tips. "
        "Be brief and factual. Do not plan flights or hotels."
    ),
)

flight_planner = Agent(
    client=_client(),
    name="FlightPlanner",
    description="Selects the best flights for the trip.",
    instructions=(
        "You are a flight planner. Use the search_flights tool to find options, "
        "then recommend ONE outbound and ONE return flight with a one-line reason. "
        "Build on the researcher's notes but only handle flights."
    ),
    tools=[search_flights],
)

hotel_planner = Agent(
    client=_client(),
    name="HotelPlanner",
    description="Selects lodging that fits the trip and chosen flights.",
    instructions=(
        "You are a hotel planner. Use the search_hotels tool, then recommend ONE "
        "hotel with a one-line reason. Consider the neighborhoods the researcher "
        "highlighted. Only handle lodging."
    ),
    tools=[search_hotels],
)

itinerary_writer = Agent(
    client=_client(),
    name="ItineraryWriter",
    description="Synthesizes research, flights and hotel into a final itinerary.",
    instructions=(
        "You are an itinerary writer. Using everything discussed so far, produce a "
        "clean day-by-day itinerary that includes the chosen flights, hotel, and "
        "activities. End with an estimated total budget."
    ),
)


async def main() -> None:
    # The participants run strictly left-to-right.
    workflow = SequentialBuilder(
        participants=[researcher, flight_planner, hotel_planner, itinerary_writer]
    ).build()

    events = await workflow.run(
        "Plan a 4-day trip from New York to San Francisco, "
        "departing 2026-07-10 and returning 2026-07-14, for two people."
    )

    outputs = events.get_outputs()
    if outputs:
        final: AgentResponse = outputs[0]
        print("===== Final Itinerary (last agent in the pipeline) =====")
        for msg in final.messages:
            print(f"\n[{msg.author_name or 'assistant'}]\n{msg.text}")


if __name__ == "__main__":
    asyncio.run(main())
