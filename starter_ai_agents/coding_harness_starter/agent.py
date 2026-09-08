"""PydanticAI coding agent that can inspect files but cannot write them."""

from __future__ import annotations

import os

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from models import ChangeProposal
from tools import AgentDependencies, list_files, read_file

DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B"
NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1"

INSTRUCTIONS = """You are a careful coding agent working on a tiny repository.
Always call list_files first, then read every relevant file before proposing a change.
Return a short plan and the smallest complete-file replacement that solves the task.
Use only workspace-relative paths. Do not change tests unless the task explicitly asks
for a test change. You have no write or shell tools: your output is only a proposal
that a human will review before the application may modify any file.
"""


def build_agent() -> Agent[AgentDependencies, ChangeProposal]:
    """Create the agent using Nebius' OpenAI-compatible endpoint."""
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "NEBIUS_API_KEY is missing. Copy .env.example to .env and add your key."
        )

    model = OpenAIChatModel(
        model_name=os.getenv("NEBIUS_MODEL", DEFAULT_MODEL),
        provider=OpenAIProvider(base_url=NEBIUS_BASE_URL, api_key=api_key),
    )
    return Agent(
        model=model,
        deps_type=AgentDependencies,
        output_type=ChangeProposal,
        tools=[list_files, read_file],
        instructions=INSTRUCTIONS,
    )
