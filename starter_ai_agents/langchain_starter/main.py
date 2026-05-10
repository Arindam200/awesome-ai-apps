"""LangChain starter — a tool-calling agent powered by Nebius."""
import os
from datetime import datetime

from dotenv import load_dotenv
from pydantic import SecretStr
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent

load_dotenv()


@tool
def get_current_time() -> str:
    """Return the current local date and time as an ISO-8601 string."""
    return datetime.now().isoformat(timespec="seconds")


@tool
def word_count(text: str) -> int:
    """Count the number of whitespace-separated words in the given text."""
    return len(text.split())


def build_agent() -> AgentExecutor:
    llm = ChatOpenAI(
        model="Qwen/Qwen3-30B-A3B",
        base_url="https://api.tokenfactory.nebius.com/v1/",
        api_key=SecretStr(os.environ["NEBIUS_API_KEY"]),
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant. Use tools when they are relevant "
                "instead of guessing.",
            ),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    tools = [get_current_time, word_count]
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)


def main():
    agent = build_agent()
    print("🔗 LangChain agent ready. Type 'exit' to quit.\n")

    history = []
    while True:
        user = input("You: ").strip()
        if user.lower() in {"exit", "quit"}:
            print("Goodbye! 👋")
            break
        if not user:
            continue

        result = agent.invoke({"input": user, "chat_history": history})
        print(f"\nAgent: {result['output']}\n")
        history.extend(
            [("human", user), ("ai", result["output"])]
        )


if __name__ == "__main__":
    main()
