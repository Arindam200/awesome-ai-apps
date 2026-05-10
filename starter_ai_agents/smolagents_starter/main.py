import os
from dotenv import load_dotenv
from smolagents import CodeAgent, DuckDuckGoSearchTool, OpenAIServerModel

load_dotenv()

model = OpenAIServerModel(
    model_id="Qwen/Qwen3-30B-A3B",
    api_base="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.getenv("NEBIUS_API_KEY"),
)

agent = CodeAgent(
    tools=[DuckDuckGoSearchTool()],
    model=model,
    add_base_tools=True,
)


def main():
    print("🤖 smolagents starter is ready! Type 'exit' to quit.\n")
    while True:
        q = input("You: ").strip()
        if q.lower() in {"exit", "quit"}:
            print("Goodbye! 👋")
            break
        if not q:
            continue
        result = agent.run(q)
        print(f"\nAgent: {result}\n")


if __name__ == "__main__":
    main()
