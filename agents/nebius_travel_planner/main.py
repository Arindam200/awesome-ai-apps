"""Small CLI entry point for quick non-Streamlit checks."""
from __future__ import annotations

import sys

from agent import build_agent


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip()
    if not prompt:
        prompt = "Plan a 3-day standard-budget trip to Rome for two people in USD."

    agent = build_agent(debug=False)
    result = agent.invoke({"messages": [("human", prompt)]})
    print(result["messages"][-1].content)


if __name__ == "__main__":
    main()
