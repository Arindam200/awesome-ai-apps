from __future__ import annotations

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from coding_harness.agent import (
    CodingAgent,
    DEFAULT_MODEL_BASE_URL,
    DEFAULT_MODEL_NAME,
    ModelConfig,
    SYSTEM_INSTRUCTIONS,
    _build_prompt,
    _coerce_proposal,
)
from coding_harness.models import PatchProposal


VALID_PROPOSAL_JSON = """{
  "plan": {
    "task_understanding": "update todo filtering",
    "files_to_modify": ["todo.py"],
    "steps": ["implement filter"],
    "tests": ["tests/test_todo.py"],
    "risks_and_assumptions": []
  },
  "operations": [{
    "operation": "update",
    "path": "todo.py",
    "reason": "add filtering",
    "content": "new",
    "expected_old_text": "old"
  }]
}"""


class ModelConfigTests(unittest.TestCase):
    def test_only_api_key_is_required_and_optional_values_have_defaults(self) -> None:
        config = ModelConfig.from_environment({"MODEL_API_KEY": "not-a-real-key"})
        self.assertEqual(config.base_url, DEFAULT_MODEL_BASE_URL)
        self.assertEqual(config.model_name, DEFAULT_MODEL_NAME)

    def test_missing_key_error_never_echoes_available_secret_like_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "MODEL_API_KEY") as captured:
            ModelConfig.from_environment({"MODEL_NAME": "private-model"})
        self.assertNotIn("private-model", str(captured.exception))

    def test_instructions_explain_workspace_relative_paths(self) -> None:
        instructions = " ".join(SYSTEM_INSTRUCTIONS.split())
        self.assertIn("relative to the locked workspace root", instructions)
        self.assertIn("Do not prefix paths with a workspace name", instructions)
        self.assertIn("raw JSON or inside a single `json` code fence", instructions)
        self.assertIn("top-level object must have plan and operations", instructions)

        prompt = _build_prompt("add filtering", None, "tests must be a list")
        self.assertIn("no files were changed", prompt)
        self.assertIn("tests must be a list", prompt)

    def test_coerce_proposal_accepts_only_complete_json_or_single_json_fence(
        self,
    ) -> None:
        direct = _coerce_proposal(VALID_PROPOSAL_JSON)
        fenced = _coerce_proposal(f"```json\n{VALID_PROPOSAL_JSON}\n```")

        self.assertIsInstance(direct, PatchProposal)
        self.assertEqual(fenced.operations[0].path, "todo.py")

    def test_coerce_proposal_rejects_prose_multiple_objects_and_invalid_fields(
        self,
    ) -> None:
        invalid_outputs = [
            f"Here is the patch:\n{VALID_PROPOSAL_JSON}",
            VALID_PROPOSAL_JSON + "\n{}",
            VALID_PROPOSAL_JSON.replace(
                '"operations": [', '"unexpected": 1, "operations": ['
            ),
        ]

        for output in invalid_outputs:
            with self.subTest(output=output[:20]):
                with self.assertRaises(ValueError):
                    _coerce_proposal(output)

    def test_coding_agent_keeps_read_only_tools_and_locally_parses_final_json(
        self,
    ) -> None:
        captured_agent_kwargs: dict[str, object] = {}

        class FakeAgent:
            def __init__(self, **kwargs: object) -> None:
                captured_agent_kwargs.update(kwargs)

        class FakeRunner:
            @staticmethod
            async def run(agent: object, prompt: str) -> SimpleNamespace:
                return SimpleNamespace(final_output=VALID_PROPOSAL_JSON)

        class FakeAsyncOpenAI:
            instances: list["FakeAsyncOpenAI"] = []

            def __init__(self, **_: object) -> None:
                self.closed = False
                self.instances.append(self)

            async def close(self) -> None:
                self.closed = True

        class FakeWorkspace:
            def list_files(self) -> list[str]:
                return ["todo.py"]

            def read_file(self, path: str) -> str:
                return ""

            def search_text(self, query: str) -> list[dict[str, object]]:
                return []

        dependencies = (
            FakeAgent,
            FakeRunner,
            lambda **_: object(),
            FakeAsyncOpenAI,
            lambda function: function,
            lambda **_: None,
        )
        config = ModelConfig(
            api_key="not-a-real-key",
            base_url="https://example.invalid/v1",
            model_name="test-model",
        )

        with patch(
            "coding_harness.agent._load_agents_dependencies",
            return_value=dependencies,
        ):
            proposal = asyncio.run(
                CodingAgent(config).propose("change it", FakeWorkspace())
            )

        self.assertIsInstance(proposal, PatchProposal)
        self.assertEqual(len(captured_agent_kwargs["tools"]), 3)
        self.assertNotIn("output_type", captured_agent_kwargs)
        self.assertTrue(FakeAsyncOpenAI.instances[0].closed)


if __name__ == "__main__":
    unittest.main()
