"""AutoGen starter — an AssistantAgent with a tool, powered by Nebius."""
import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_core.models import ModelFamily, ModelInfo
from autogen_ext.models.openai import OpenAIChatCompletionClient

load_dotenv()


def get_current_time() -> str:
    """Return the current local date and time as an ISO-8601 string."""
    return datetime.now().isoformat(timespec="seconds")


def build_agent() -> AssistantAgent:
    model_client = OpenAIChatCompletionClient(
        model="Qwen/Qwen3-30B-A3B",
        base_url="https://api.tokenfactory.nebius.com/v1/",
        api_key=os.getenv("NEBIUS_API_KEY"),
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=True,
            family=ModelFamily.UNKNOWN,
            structured_output=False,
        ),
    )

    return AssistantAgent(
        name="NebiusAssistant",
        model_client=model_client,
        tools=[get_current_time],
        system_message=(
            "You are a helpful assistant. When the user asks about the current "
            "time or date, call the get_current_time tool instead of guessing."
        ),
        reflect_on_tool_use=True,
    )


async def chat():
    agent = build_agent()
    print("🤖 AutoGen agent ready. Type 'exit' to quit.\n")

    while True:
        user = input("You: ").strip()
        if user.lower() in {"exit", "quit"}:
            print("Goodbye! 👋")
            break
        if not user:
            continue

        await Console(agent.run_stream(task=user))


if __name__ == "__main__":
    asyncio.run(chat())
