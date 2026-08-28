import asyncio
import os

from dotenv import load_dotenv
from agents import Agent, Runner, set_tracing_disabled
from agents.mcp import MCPServerStdio


SAND_BASE_PACKAGE = (
    "https://github.com/sandbaseai/cli/releases/download/"
    "v0.1.17/sandbaseai-cli-0.1.17.tgz"
)


async def main() -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required; copy .env.example to .env")

    set_tracing_disabled(disabled=True)
    async with MCPServerStdio(
        cache_tools_list=True,
        params={"command": "npx", "args": ["-y", SAND_BASE_PACKAGE, "connect"]},
    ) as server:
        agent = Agent(
            name="SandBase model explorer",
            instructions=(
                "Use the SandBase MCP tools. First inspect available models and choose one "
                "that can answer a short text prompt. Then make exactly one request and "
                "report the selected provider and model. Do not change configuration."
            ),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            mcp_servers=[server],
        )
        result = await Runner.run(
            starting_agent=agent,
            input="Say hello in one sentence and include the model you used.",
        )
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
