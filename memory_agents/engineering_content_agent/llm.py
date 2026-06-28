"""Nebius Token Factory model setup for Agno agents."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from agno.agent import Agent
from agno.models.base import Model
from agno.models.nebius import Nebius

from config import Settings


def build_model(settings: Settings) -> Model:
    return Nebius(
        id=settings.nebius_model,
        api_key=settings.nebius_api_key,
        base_url=settings.nebius_base_url,
    )


def make_agent(model: Model, instructions: str, name: str) -> Agent:
    return Agent(
        name=name,
        model=model,
        instructions=[instructions],
        markdown=False,
    )


async def run_agent(agent: Agent, prompt: str) -> str:
    response = await asyncio.to_thread(agent.run, prompt)
    return str(getattr(response, "content", response) or "")


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from an Agno text response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Agno response did not contain a JSON object.")
    return parsed
