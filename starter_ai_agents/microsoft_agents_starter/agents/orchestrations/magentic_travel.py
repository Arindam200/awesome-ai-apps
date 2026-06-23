"""Magentic orchestration — a manager dynamically directs a travel team.

Pattern
-------
MAGENTIC orchestration (based on AutoGen's Magentic-One) uses a powerful
*manager* agent that plans the task, then dynamically decides which specialist
should act next, tracks progress on a "ledger", detects stalls, replans when
needed, and finally synthesizes one answer. Use it for complex, open-ended
tasks where the solution path is not known up front.

Team used here (1 manager + 4 specialists):

    MagenticManager      : plans, routes, tracks progress, synthesizes the answer
    DestinationResearcher: facts, seasonality, safety, local context
    FlightSpecialist     : routing & flight options (tool: search_flights)
    HotelSpecialist      : lodging options          (tool: search_hotels)
    BudgetAnalyst        : cost breakdown & savings  (tool: estimate_costs)

The manager calls specialists in whatever order/repetition the task requires —
unlike the fixed pipeline of Sequential or the fixed cycle of round-robin Group
Chat.

Docs: https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/magentic

Run:
    python agents/orchestrations/magentic_travel.py
"""

import asyncio
import os
from typing import Annotated

from dotenv import load_dotenv

load_dotenv()

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework.orchestrations import MagenticBuilder
from monocle_apptrace import setup_monocle_telemetry

setup_monocle_telemetry(
    workflow_name="okahu_demos_ms_openai_magentic_travel",
    monocle_exporters_list="file",
)


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@tool(approval_mode="never_require")
def search_flights(origin: str, destination: str, date: str) -> str:
    """Search for flights between two cities on a given date."""
    return f"Flights {origin}->{destination} on {date}: ANA $980, United $1,040 (round trip)."


@tool(approval_mode="never_require")
def search_hotels(city: str, nights: int) -> str:
    """Search for hotels in a city for a number of nights."""
    return f"Hotels in {city} for {nights} nights: Ryokan $210/night, Hotel $150/night."


@tool(approval_mode="never_require")
def estimate_costs(
    flights: Annotated[float, "Total flight cost in USD"],
    nightly_hotel: Annotated[float, "Hotel cost per night in USD"],
    nights: Annotated[int, "Number of nights"],
    daily_spend: Annotated[float, "Estimated daily spend per person in USD"],
    travelers: Annotated[int, "Number of travelers"],
) -> str:
    """Estimate a total trip cost from the component costs."""
    total = flights + (nightly_hotel * nights) + (daily_spend * nights * travelers)
    return f"Estimated total trip cost: ${total:,.0f} for {travelers} traveler(s)."


def _client() -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model="Qwen/Qwen3.5-397B-A17B",
        api_key=os.getenv("NEBIUS_API_KEY"),
        base_url="https://api.tokenfactory.nebius.com/v1/",
    )


# --------------------------------------------------------------------------- #
# Specialists + manager
# --------------------------------------------------------------------------- #
researcher = Agent(
    client=_client(),
    name="DestinationResearcher",
    description="Finds destination facts, seasonality, and local context.",
    instructions=(
        "You research destinations. Provide facts, best timing, and local tips. "
        "Do not compute budgets or book flights/hotels."
    ),
)

flight_specialist = Agent(
    client=_client(),
    name="FlightSpecialist",
    description="Finds and recommends flights.",
    instructions="You find flights with the search_flights tool and recommend the best option.",
    tools=[search_flights],
)

hotel_specialist = Agent(
    client=_client(),
    name="HotelSpecialist",
    description="Finds and recommends lodging.",
    instructions="You find lodging with the search_hotels tool and recommend the best option.",
    tools=[search_hotels],
)

budget_analyst = Agent(
    client=_client(),
    name="BudgetAnalyst",
    description="Builds the cost breakdown.",
    instructions=(
        "You compute trip budgets with the estimate_costs tool and flag any "
        "overspend versus the traveler's stated budget."
    ),
    tools=[estimate_costs],
)

manager = Agent(
    client=_client(),
    name="MagenticManager",
    description="Coordinates the travel team and synthesizes the final plan.",
    instructions=(
        "You coordinate a travel team to produce a complete, budget-checked trip "
        "plan. Delegate to the researcher, flight, hotel, and budget specialists as "
        "needed, then synthesize one final itinerary with a cost summary."
    ),
)


async def main() -> None:
    workflow = MagenticBuilder(
        participants=[researcher, flight_specialist, hotel_specialist, budget_analyst],
        intermediate_output_from=[researcher, flight_specialist, hotel_specialist, budget_analyst],
        manager_agent=manager,
        max_round_count=12,
        max_stall_count=3,
        max_reset_count=2,
    ).build()

    task = (
        "Plan a 6-day trip from Chicago to Tokyo in October 2026 for two people. "
        "Keep the total under $6,000. I want a mix of culture and food, and a clear "
        "day-by-day itinerary with a final cost breakdown."
    )

    print("===== Magentic Travel Team =====")
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
