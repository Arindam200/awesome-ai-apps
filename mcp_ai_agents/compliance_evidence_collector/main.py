"""Compliance Evidence Collector.

An LLM agent gathers evidence from a local mock MCP server, maps it to audit
controls, flags missing/weak/conflicting evidence and writes a cited report.
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

INSTRUCTIONS = """You are a compliance auditor's assistant.
Call list_controls, then gather evidence with get_policy_documents, get_tickets,
get_deploy_logs and get_access_reviews. For EACH control produce:

### <control id> - <title>
- Status: Satisfied | Partially satisfied | Not satisfied
- Evidence found (cite every item by its ID or source, e.g. [AR-2024-Q4], [CHG-102], [policies/access-control-policy.md])
- Gaps: missing, weak or conflicting evidence (e.g. self-approved change, deploy with no ticket, unsigned review)
- Recommended remediation

Start with a one-paragraph executive summary. Only use facts returned by the
tools and cite them; if evidence is absent, say it is missing rather than guessing."""


async def main(prompt: str) -> None:
    if not API_KEY:
        sys.exit("Set LLM_API_KEY (or NEBIUS_API_KEY) in .env - see .env.example")
    client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
    server_path = Path(__file__).parent / "evidence_server.py"
    async with MCPServerStdio(
        name="compliance-evidence",
        params={"command": sys.executable, "args": [str(server_path)]},
    ) as server:
        agent = Agent(
            name="Compliance Evidence Collector",
            instructions=INSTRUCTIONS,
            mcp_servers=[server],
            model=OpenAIChatCompletionsModel(model=MODEL, openai_client=client),
        )
        result = await Runner.run(agent, prompt)
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "Assess all controls and produce the cited compliance report."))
