"""Semantic Kernel starter — a ChatCompletion agent with a simple plugin.

Uses OpenAIChatCompletion pointed at Nebius Token Factory (OpenAI-compatible).
"""
import asyncio
import os
from datetime import datetime
from typing import Annotated

from dotenv import load_dotenv
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.contents import ChatHistory
from semantic_kernel.functions import kernel_function

load_dotenv()


class TimePlugin:
    @kernel_function(description="Get the current date and time.")
    def now(self) -> Annotated[str, "Current local timestamp"]:
        return datetime.now().isoformat(timespec="seconds")


def build_agent() -> ChatCompletionAgent:
    kernel = Kernel()
    kernel.add_service(
        OpenAIChatCompletion(
            service_id="nebius",
            ai_model_id="Qwen/Qwen3-30B-A3B",
            api_key=os.getenv("NEBIUS_API_KEY"),
            base_url="https://api.tokenfactory.nebius.com/v1/",
        )
    )
    kernel.add_plugin(TimePlugin(), plugin_name="time")

    return ChatCompletionAgent(
        kernel=kernel,
        name="NebiusAssistant",
        instructions=(
            "You are a helpful assistant. When the user asks about the current "
            "time or date, always call the time.now function rather than guessing."
        ),
    )


async def chat():
    agent = build_agent()
    history = ChatHistory()
    print("🧩 Semantic Kernel agent ready. Type 'exit' to quit.\n")

    while True:
        user = input("You: ").strip()
        if user.lower() in {"exit", "quit"}:
            print("Goodbye! 👋")
            break
        if not user:
            continue

        history.add_user_message(user)
        async for response in agent.invoke(history):
            print(f"\nAgent: {response.content}\n")
            history.add_message(response)


if __name__ == "__main__":
    asyncio.run(chat())
