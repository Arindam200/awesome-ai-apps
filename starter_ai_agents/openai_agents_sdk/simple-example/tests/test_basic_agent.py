import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "basic-agent.py"


def load_basic_agent():
    agents = ModuleType("agents")
    agents.Agent = MagicMock(name="Agent")
    agents.AsyncOpenAI = MagicMock(name="AsyncOpenAI")
    agents.OpenAIChatCompletionsModel = MagicMock(name="OpenAIChatCompletionsModel")
    agents.Runner = MagicMock(name="Runner")

    dotenv = ModuleType("dotenv")
    dotenv.load_dotenv = MagicMock(name="load_dotenv")

    spec = importlib.util.spec_from_file_location("basic_agent", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"agents": agents, "dotenv": dotenv}):
        spec.loader.exec_module(module)
    return module, agents, dotenv


class BasicAgentTests(unittest.TestCase):
    def setUp(self):
        self.module, self.agents, self.dotenv = load_basic_agent()

    def test_import_has_no_runtime_side_effects(self):
        self.dotenv.load_dotenv.assert_not_called()
        self.agents.Runner.run_sync.assert_not_called()

    def test_create_agent_uses_default_configuration(self):
        client = self.agents.AsyncOpenAI.return_value
        model = self.agents.OpenAIChatCompletionsModel.return_value

        with patch.dict(os.environ, {"NEBIUS_API_KEY": "test-key"}, clear=True):
            created_agent = self.module.create_agent()

        self.dotenv.load_dotenv.assert_called_once_with()
        self.agents.AsyncOpenAI.assert_called_once_with(
            base_url=self.module.DEFAULT_BASE_URL,
            api_key="test-key",
        )
        self.agents.OpenAIChatCompletionsModel.assert_called_once_with(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            openai_client=client,
        )
        self.agents.Agent.assert_called_once_with(
            name="Assistant",
            instructions=ANY,
            model=model,
        )
        self.assertIs(created_agent, self.agents.Agent.return_value)

    def test_create_agent_requires_nebius_api_key(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(ValueError, "NEBIUS_API_KEY"),
        ):
            self.module.create_agent()

        self.agents.AsyncOpenAI.assert_not_called()
        self.agents.Agent.assert_not_called()

    def test_main_runs_synchronously_and_prints_final_output(self):
        agent = object()
        self.module.create_agent = MagicMock(return_value=agent)
        self.agents.Runner.run_sync.return_value = SimpleNamespace(
            final_output="Example response"
        )

        with patch("builtins.print") as print_mock:
            self.module.main()

        self.agents.Runner.run_sync.assert_called_once_with(
            agent,
            self.module.DEFAULT_PROMPT,
        )
        print_mock.assert_called_once_with("Example response")


if __name__ == "__main__":
    unittest.main()
