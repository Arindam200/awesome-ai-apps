"""Handoff orchestration — a travel help desk that transfers control.

Pattern
-------
In HANDOFF orchestration agents transfer FULL control of the conversation to
one another based on context. There is no central orchestrator — agents form a
mesh and decide (via a handoff tool call) who should take over next. When an
agent does NOT hand off, it asks the user for more input.

Agents used here (5 agents):

    triage_agent   : front desk; routes the traveler to a specialist
    flight_agent   : flight booking / changes  (tool: search_flights)
    hotel_agent    : lodging                    (tool: search_hotels)
    visa_agent     : entry requirements / visas (tool: check_visa)
    refund_agent   : cancellations & refunds    (tool: process_refund)

Routing rules configured below:
    triage -> {flight, hotel, visa}      (triage cannot refund directly)
    flight/hotel/visa -> triage          (specialists can bounce back)
    flight -> refund                     (only a flight issue can escalate to refund)

This sample uses AUTONOMOUS MODE so it runs end-to-end without a human typing
between turns. Remove `.with_autonomous_mode()` for an interactive help desk.

Docs: https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff

Run:
    python agents/orchestrations/handoff_travel.py
"""

import asyncio
import os
from typing import Annotated

from dotenv import load_dotenv

load_dotenv()

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework.orchestrations import HandoffBuilder
from monocle_apptrace import setup_monocle_telemetry

setup_monocle_telemetry(
    workflow_name="okahu_demos_ms_openai_handoff_travel",
    monocle_exporters_list="file",
)


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@tool
def search_flights(
    origin: Annotated[str, "Departure city"],
    destination: Annotated[str, "Arrival city"],
    date: Annotated[str, "Travel date"],
) -> str:
    """Search for flights between two cities on a given date."""
    return f"Flights {origin}->{destination} on {date}: United $290, Delta $320."


@tool
def search_hotels(
    city: Annotated[str, "City to stay in"],
    nights: Annotated[int, "Number of nights"],
) -> str:
    """Search for hotels in a city for a number of nights."""
    return f"Hotels in {city} for {nights} nights: Hilton $165/night, Airbnb $120/night."


@tool
def check_visa(
    nationality: Annotated[str, "Traveler nationality"],
    destination: Annotated[str, "Destination country"],
) -> str:
    """Check visa / entry requirements."""
    return f"{nationality} citizens visiting {destination}: eVisa required, 30-day stay."


@tool
def process_refund(
    booking_id: Annotated[str, "Booking reference to refund"],
) -> str:
    """Process a refund for a booking reference."""
    return f"Refund initiated for booking {booking_id}; 5-10 business days. Welcome back!"


# --------------------------------------------------------------------------- #
# Agents
# --------------------------------------------------------------------------- #
def _client() -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model="Qwen/Qwen3.5-397B-A17B",
        api_key=os.getenv("NEBIUS_API_KEY"),
        base_url="https://api.tokenfactory.nebius.com/v1/",
    )


triage_agent = Agent(
    client=_client(),
    name="triage_agent",
    description="Front-desk triage that routes travelers to the right specialist.",
    instructions=(
        "You are the travel help-desk triage agent. Read the traveler's request "
        "and hand off to the specialist best suited to handle it (flights, hotels, "
        "visas). Do not try to solve specialist problems yourself."
    ),
    require_per_service_call_history_persistence=True,
)

flight_agent = Agent(
    client=_client(),
    name="flight_agent",
    description="Handles flight search and booking changes.",
    instructions=(
        "You handle flight requests using the search_flights tool. If the traveler "
        "actually wants to cancel and get money back, hand off to the refund agent."
    ),
    tools=[search_flights],
    require_per_service_call_history_persistence=True,
)

hotel_agent = Agent(
    client=_client(),
    name="hotel_agent",
    description="Handles lodging requests.",
    instructions="You handle hotel requests using the search_hotels tool.",
    tools=[search_hotels],
    require_per_service_call_history_persistence=True,
)

visa_agent = Agent(
    client=_client(),
    name="visa_agent",
    description="Handles entry-requirement and visa questions.",
    instructions="You answer visa/entry questions using the check_visa tool.",
    tools=[check_visa],
    require_per_service_call_history_persistence=True,
)

refund_agent = Agent(
    client=_client(),
    name="refund_agent",
    description="Handles cancellations and refunds.",
    instructions="You process refunds using the process_refund tool, then say 'welcome'.",
    tools=[process_refund],
    require_per_service_call_history_persistence=True,
)


async def main() -> None:
    workflow = (
        HandoffBuilder(
            name="travel_help_desk_handoff",
            participants=[triage_agent, flight_agent, hotel_agent, visa_agent, refund_agent],
        )
        .with_start_agent(triage_agent)
        # Routing rules — who may take over from whom.
        .add_handoff(triage_agent, [flight_agent, hotel_agent, visa_agent])
        .add_handoff(flight_agent, [triage_agent, refund_agent])
        .add_handoff(hotel_agent, [triage_agent])
        .add_handoff(visa_agent, [triage_agent])
        .add_handoff(refund_agent, [triage_agent])
        # Run autonomously so the demo completes without human input between turns.
        .with_autonomous_mode(turn_limits={triage_agent.name: 4})
        .build()
    )

    print("===== Handoff Help Desk =====")
    result = await workflow.run(
        "I'm a US citizen flying from Boston to Lisbon on 2026-09-12 and I need "
        "to know the visa rules and book a flight."
    )
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
