"""MCP Incident Response Agent.

Connects an LLM agent to a local mock MCP server (alerts, service status,
runbooks) and produces an incident summary, likely impact, recommended next
actions and a stakeholder status update.
"""
import asyncio
import os
import sys
from pathlib import Path

from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
from agents.mcp import MCPServerStdio
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
set_tracing_disabled(disabled=True)

API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("NEBIUS_API_KEY")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.tokenfactory.nebius.com/v1")
MODEL = os.environ.get("LLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct")

INSTRUCTIONS = """You are an SRE incident commander assistant.
Use the tools to investigate: list firing alerts, check the status of each
affected service and its dependencies, and search the runbooks. Then respond
with exactly these sections:

## Incident Summary
## Likely Impact
## Recommended Next Actions   (numbered, cite the runbook used)
## Status Update Draft        (short, plain-language, suitable for a status page)

Only state facts that the tools returned. If something is unknown, say so."""


async def main(prompt: str) -> None:
    if not API_KEY:
        sys.exit("Set LLM_API_KEY (or NEBIUS_API_KEY) in .env - see .env.example")
    client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
    server_path = Path(__file__).parent / "incident_server.py"
    async with MCPServerStdio(
        name="incident-response",
        params={"command": sys.executable, "args": [str(server_path)]},
    ) as server:
        agent = Agent(
            name="Incident Response Agent",
            instructions=INSTRUCTIONS,
            mcp_servers=[server],
            model=OpenAIChatCompletionsModel(model=MODEL, openai_client=client),
        )
        result = await Runner.run(agent, prompt)
        print(result.final_output)


if __name__ == "__main__":
    user_prompt = " ".join(sys.argv[1:]) or "Investigate the current incident and draft a status update."
    asyncio.run(main(user_prompt))
