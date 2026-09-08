import asyncio
from pathlib import Path

from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from agent import build_agent
from models import ChangeProposal
from tools import AgentDependencies
from workspace import Workspace

models.ALLOW_MODEL_REQUESTS = False


def test_agent_tools_and_structured_output_without_network(
    tmp_path: Path, monkeypatch
) -> None:
    """The real agent wiring produces validated output with a test model."""
    (tmp_path / "calculator.py").write_text(
        "def add(left, right):\n    return left - right\n", encoding="utf-8"
    )
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    agent = build_agent()

    with agent.override(model=TestModel(call_tools="all")):
        result = asyncio.run(
            agent.run(
                "Fix calculator.add.", deps=AgentDependencies(Workspace(tmp_path))
            )
        )

    assert isinstance(result.output, ChangeProposal)
    assert result.output.plan
    assert result.output.changes
