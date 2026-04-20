"""Letta starter — stateful agent with persistent memory.

Requires a running Letta server. Start one with:

    docker run -d --name letta -p 8283:8283 \\
      -e OPENAI_API_KEY=$NEBIUS_API_KEY \\
      -e OPENAI_API_BASE=https://api.tokenfactory.nebius.com/v1/ \\
      letta/letta:latest

Docs: https://docs.letta.com/
"""
import os
from dotenv import load_dotenv
from letta_client import Letta

load_dotenv()

BASE_URL = os.getenv("LETTA_BASE_URL", "http://localhost:8283")
AGENT_NAME = "nebius_memory_agent"
MODEL = "openai/Qwen/Qwen3-30B-A3B"
EMBEDDING = "openai/Qwen/Qwen3-Embedding-8B"

client = Letta(base_url=BASE_URL)


def get_or_create_agent():
    for a in client.agents.list():
        if a.name == AGENT_NAME:
            return a

    return client.agents.create(
        name=AGENT_NAME,
        model=MODEL,
        embedding=EMBEDDING,
        memory_blocks=[
            {"label": "human", "value": "The user's name is not yet known."},
            {
                "label": "persona",
                "value": (
                    "I am a helpful assistant with long-term memory. "
                    "I remember details about the user across sessions."
                ),
            },
        ],
    )


def main():
    agent = get_or_create_agent()
    print(f"🧠 Letta agent '{agent.name}' ready (id={agent.id}). Type 'exit' to quit.\n")

    while True:
        text = input("You: ").strip()
        if text.lower() in {"exit", "quit"}:
            print("Goodbye! 👋")
            break
        if not text:
            continue

        response = client.agents.messages.create(
            agent_id=agent.id,
            messages=[{"role": "user", "content": text}],
        )
        for msg in response.messages:
            if getattr(msg, "message_type", None) == "assistant_message":
                print(f"\nAgent: {msg.content}\n")


if __name__ == "__main__":
    main()
