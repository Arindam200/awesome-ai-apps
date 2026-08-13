"""A deterministic PydanticAI agent with time-aware local Lians memory."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lians import LocalLiansClient
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

AGENT_ID = "shipping-support-agent"
FACT_FILTER = {"entity": "order-1842", "field": "shipping_estimate"}
DB_PATH = Path(__file__).parent / ".data" / "memory.db"


def _contents(result: dict[str, Any]) -> list[str]:
    return [memory["content"] for memory in result["memories"]]


def run_demo() -> dict[str, Any]:
    """Store a correction, then ask an agent for current and historical truth."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    observed: dict[str, dict[str, Any]] = {}

    with LocalLiansClient(db_path=DB_PATH, embedding_provider="local") as memory:
        memory.add(
            agent_id=AGENT_ID,
            content="Order 1842 shipping estimate is Friday",
            event_time=datetime(2026, 8, 1, 9, tzinfo=UTC),
            metadata=FACT_FILTER,
            source="synthetic-order-event",
        )
        memory.add(
            agent_id=AGENT_ID,
            content="Order 1842 shipping estimate changed to Monday",
            event_time=datetime(2026, 8, 2, 15, tzinfo=UTC),
            metadata=FACT_FILTER,
            source="synthetic-order-event",
        )

        def recall_current_estimate() -> dict[str, Any]:
            """Return the currently valid shipping estimate from Lians."""
            result = memory.recall(
                agent_id=AGENT_ID,
                query="When will order 1842 ship?",
                filters=FACT_FILTER,
                k=3,
            )
            observed["current"] = result
            return result

        def recall_estimate_before_revision() -> dict[str, Any]:
            """Return the estimate valid before the August 2 revision."""
            result = memory.recall_at(
                agent_id=AGENT_ID,
                query="When was order 1842 expected to ship?",
                as_of=datetime(2026, 8, 2, 12, tzinfo=UTC),
                filters=FACT_FILTER,
                k=3,
            )
            observed["historical"] = result
            return result

        current_agent = Agent(
            TestModel(call_tools=["recall_current_estimate"]),
            instructions="Use Lians memory to answer with the current estimate.",
            tools=[recall_current_estimate],
        )
        historical_agent = Agent(
            TestModel(call_tools=["recall_estimate_before_revision"]),
            instructions="Use point-in-time Lians memory; never leak a later update.",
            tools=[recall_estimate_before_revision],
        )

        current_run = current_agent.run_sync("When will order 1842 ship?")
        historical_run = historical_agent.run_sync(
            "What was the shipping estimate at noon on August 2?"
        )

    return {
        "current": observed["current"],
        "historical": observed["historical"],
        "agent_outputs": {
            "current": current_run.output,
            "historical": historical_run.output,
        },
    }


def main() -> None:
    results = run_demo()
    print("Current recall:", json.dumps(_contents(results["current"]), indent=2))
    print(
        "Historical recall:",
        json.dumps(_contents(results["historical"]), indent=2),
    )


if __name__ == "__main__":
    main()
