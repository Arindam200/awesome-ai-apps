"""LangChain starter — a tool-calling agent powered by Novita AI."""
import os
from datetime import datetime

from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import count_tokens_approximately, trim_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv()

# Keep room in the model context for the prompt, tool definitions, current
# input, agent scratchpad, and generated output.
HISTORY_MAX_TOKENS = 24_000


@tool
def get_current_time() -> str:
    """Return the current local date and time as an ISO-8601 string."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


@tool
def word_count(text: str) -> int:
    """Count the number of whitespace-separated words in the given text."""
    return len(text.split())


def build_agent() -> AgentExecutor:
    llm = ChatOpenAI(
        model="deepseek/deepseek-v4-pro",
        base_url="https://api.novita.ai/openai",
        api_key=SecretStr(os.environ["NOVITA_API_KEY"]),
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are a helpful assistant. Use tools when they are relevant "
                    "instead of guessing."
                ),
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

        trimmed_history = trim_messages(
            history,
            token_counter=count_tokens_approximately,
            max_tokens=HISTORY_MAX_TOKENS,
            strategy="last",
            include_system=True,
            start_on="human",
        )
        result = agent.invoke({"input": user, "chat_history": trimmed_history})
        print(f"\nAgent: {result['output']}\n")
        history.extend(
            [("human", user), ("ai", result["output"])]
        )


if __name__ == "__main__":
    main()