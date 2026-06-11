import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from monocle_apptrace import setup_monocle_telemetry

# Enable Monocle Tracing
setup_monocle_telemetry(
    workflow_name="okahu_demos_ms_openai_travel_agent",
    monocle_exporters_list="file",
)

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient


# Tools (stubs) — in production replace with real API integrations
@tool(approval_mode="never_require")
def search_flights(origin: str, destination: str, date: str) -> str:
    return f"Found 3 flights from {origin} to {destination} on {date}: Delta $320, United $290, JetBlue $275"


@tool(approval_mode="never_require")
def search_hotels(city: str, checkin: str, checkout: str) -> str:
    return f"Found hotels in {city} ({checkin} to {checkout}): Marriott $180/night, Hilton $165/night, Airbnb $120/night"


# Planner agent: takes raw search results and crafts an itinerary
planner_agent = Agent(
    client=OpenAIChatClient(model=os.getenv("OPENAI_CHAT_MODEL_ID", "gpt-4o-mini")),
    name="PlannerAgent",
    instructions=(
        "You are an itinerary planner. Given flight and hotel search results and user constraints,"
        " produce a concise 3-5 bullet itinerary with recommended flights and hotel, plus costs."
    ),
)


# Critic agent: reviews the itinerary and scores it
critic_agent = Agent(
    client=OpenAIChatClient(model=os.getenv("OPENAI_CHAT_MODEL_ID", "gpt-4o-mini")),
    name="CriticAgent",
    instructions=(
        "You are a critic. Evaluate the provided itinerary for completeness, accuracy, and user-fit. "
        "Return a short critique and a score from 1 to 10."
    ),
)


async def orchestrate_trip(
    origin: str, destination: str, depart: str, return_date: str
):
    # 1) Run quick searches (tools)
    flights = search_flights(origin, destination, depart)
    hotels = search_hotels(destination, depart, return_date)

    # 2) Ask planner agent to synthesize an itinerary
    planner_prompt = (
        f"User request: roundtrip from {origin} to {destination} departing {depart} returning {return_date}.\n"
        f"Flights:\n{flights}\nHotels:\n{hotels}\n\nCreate a succinct itinerary with chosen flight, hotel, total estimated cost."
    )
    itinerary = await planner_agent.run(planner_prompt)

    # 3) Ask critic agent to evaluate the itinerary
    critic_prompt = f"Itinerary:\n{itinerary}\n\nEvaluate the itinerary, list any issues or missing details, and give a score 1-10 with a one-line rationale."
    critique = await critic_agent.run(critic_prompt)

    return {
        "flights": flights,
        "hotels": hotels,
        "itinerary": itinerary,
        "critique": critique,
    }


async def main():
    out = await orchestrate_trip(
        "New York", "San Francisco", "2026-07-10", "2026-07-14"
    )
    print("--- Flights ---")
    print(out["flights"])
    print("\n--- Hotels ---")
    print(out["hotels"])
    print("\n--- Itinerary ---")
    print(out["itinerary"])
    print("\n--- Critique ---")
    print(out["critique"])


if __name__ == "__main__":
    asyncio.run(main())
