"""LangGraph starter — a prebuilt ReAct agent powered by Nebius."""
import os
from datetime import datetime

from dotenv import load_dotenv
from pydantic import SecretStr
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()


@tool
def get_current_time() -> str:
    """Return the current local date and time as an ISO-8601 string."""
    return datetime.now().isoformat(timespec="seconds")


@tool
def word_count(text: str) -> int:
    """Count the number of whitespace-separated words in the given text."""
    return len(text.split())


def build_agent():
    llm = ChatOpenAI(
        model="Qwen/Qwen3-30B-A3B",
        base_url="https://api.tokenfactory.nebius.com/v1/",
        api_key=SecretStr(os.environ["NEBIUS_API_KEY"]),
    )

    return create_react_agent(
        model=llm,
        tools=[get_current_time, word_count],
        prompt=(
            "You are a helpful assistant. Use tools when they are relevant "
            "instead of guessing."
        ),
    )


def main():
    agent = build_agent()
    print("🕸️  LangGraph ReAct agent ready. Type 'exit' to quit.\n")

    messages = []
    while True:
        user = input("You: ").strip()
        if user.lower() in {"exit", "quit"}:
            print("Goodbye! 👋")
            break
        if not user:
            continue

        messages.append({"role": "user", "content": user})
        result = agent.invoke({"messages": messages})
        messages = result["messages"]
        print(f"\nAgent: {messages[-1].content}\n")


if __name__ == "__main__":
    main()
