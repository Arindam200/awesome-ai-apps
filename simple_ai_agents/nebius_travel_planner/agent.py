"""LangChain agent for the Nebius travel planner."""
from __future__ import annotations

import os
from datetime import date

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_nebius import ChatNebius

from tools import TRAVEL_TOOLS

load_dotenv()

DEFAULT_MODEL = os.getenv("NEBIUS_MODEL", "Qwen/Qwen3-30B-A3B")


def _system_prompt() -> str:
    today = date.today().isoformat()
    return f"""You are VoyageCompass, a practical travel planning agent.

Current date: {today}

Your job is to create realistic, useful travel plans from the user's brief.
Use the available tools before making factual claims about live conditions,
destination details, exchange rates, weather, or budgets.

Tool policy:
1. Use `geocode_destination` when the destination might be ambiguous or when
   weather/location context is needed.
2. Use `get_weather_summary` for destination weather. If requested dates are
   outside the forecast window, say that the weather is an estimate and avoid
   pretending it is a live forecast.
3. Use `destination_research` for attractions, neighborhoods, restaurants,
   local transport, opening hours, safety, visas, and current travel context.
4. Use `estimate_daily_budget` and `convert_currency` for calculations.
5. Label inferred numbers as estimates. Do not invent exact hotel, ticket, or
   transport prices unless tool output supports them.

Planning rules:
- If the user omits a detail, make a reasonable assumption and state it.
- Ask one concise clarifying question only when a plan would be unsafe or
  unusable without the answer.
- Prefer compact, scannable answers with tables where helpful.
- Include weather notes, neighborhood/base recommendation, day-by-day plan,
  food and transit ideas, budget breakdown, and practical cautions.
- End with two or three follow-up options the traveler can ask for next.
"""


def build_agent(
    *,
    api_key: str | None = None,
    model_name: str | None = None,
    temperature: float = 0.25,
    debug: bool = False,
):
    """Create the LangChain agent backed by Nebius ChatNebius."""
    resolved_api_key = api_key or os.getenv("NEBIUS_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("Set NEBIUS_API_KEY in .env, Streamlit secrets, or the sidebar.")

    llm = ChatNebius(
        model=model_name or DEFAULT_MODEL,
        api_key=resolved_api_key,
        temperature=temperature,
        top_p=0.9,
    )
    return create_agent(
        model=llm,
        tools=TRAVEL_TOOLS,
        system_prompt=_system_prompt(),
        debug=debug,
    )
