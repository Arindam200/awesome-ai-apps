"""Terminal chat with the support agent."""
from agent import build_agent


def main() -> None:
    agent = build_agent(verbose=False)
    print("🛟  NimbusCart support agent ready. Type 'exit' to quit.\n")

    history: list[tuple[str, str]] = []
    while True:
        user = input("You: ").strip()
        if user.lower() in {"exit", "quit"}:
            print("Goodbye 👋")
            break
        if not user:
            continue
        result = agent.invoke({"messages": history + [("human", user)]})
        answer = result["messages"][-1].content
        print(f"\nAgent: {answer}\n")
        history.extend([("human", user), ("ai", answer)])


if __name__ == "__main__":
    main()
