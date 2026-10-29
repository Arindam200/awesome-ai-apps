"""Offline request-boundary checks; run with python -m unittest test_nebius_requests.

UI, scraping, and memory storage are doubles. The application functions and
OpenAI SDK serialization are real; httpx.MockTransport captures every request.
"""

import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import MagicMock, patch

import httpx
from openai import OpenAI


class SessionState(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


class NebiusRequestTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.network = patch(
            "socket.socket", side_effect=AssertionError("Network forbidden")
        )
        self.network.start()
        self.addCleanup(self.network.stop)
        self.requests = []
        self.clients = []
        self.st = MagicMock()
        self.st.session_state = SessionState()
        self.st.text_input.side_effect = lambda *args, **kwargs: kwargs.get("value", "")
        self.st.button.return_value = False
        self.st.chat_input.return_value = "Suggest one video about Python."
        self.st.stop.side_effect = AssertionError("Unexpected Streamlit stop")
        self.st.error.side_effect = AssertionError
        self.st.warning.side_effect = AssertionError

        # Stub unrelated integrations without replacing any application function.
        sqlalchemy = ModuleType("sqlalchemy")
        sqlalchemy.create_engine = MagicMock()
        sqlalchemy.text = lambda value: value
        orm = ModuleType("sqlalchemy.orm")
        orm.sessionmaker = MagicMock()
        memori = ModuleType("memori")
        self.memory = MagicMock()
        memori.Memori = MagicMock()
        memori.Memori.return_value.openai.register.return_value = self.memory
        exa = ModuleType("exa_py")
        exa.Exa = MagicMock()
        modules = {
            "streamlit": self.st,
            "yt_dlp": ModuleType("yt_dlp"),
            "exa_py": exa,
            "memori": memori,
            "sqlalchemy": sqlalchemy,
            "sqlalchemy.orm": orm,
        }
        self.module_patch = patch.dict("sys.modules", modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        with patch("dotenv.load_dotenv"):
            self.core = self.load_module("core", "core.py")
            with patch.dict("sys.modules", {"core": self.core}):
                self.app = self.load_module("trend_app", "app.py")
        self.app.load_dotenv = lambda: None
        self.app.OpenAI = self.make_client
        self.core.OpenAI = self.make_client
        self.addCleanup(lambda: [client.close() for client in self.clients])

    @staticmethod
    def load_module(name, filename):
        spec = importlib.util.spec_from_file_location(
            name, Path(__file__).with_name(filename)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def make_client(self, **kwargs):
        client = OpenAI(
            **kwargs,
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(self.capture)),
        )
        self.clients.append(client)
        return client

    def capture(self, request):
        body = json.loads(request.content)
        self.assertEqual(
            str(request.url), "https://api.tokenfactory.nebius.com/v1/chat/completions"
        )
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.headers["authorization"], "Bearer fixture-session-key")
        self.requests.append({"url": str(request.url), "body": body})
        return httpx.Response(
            200,
            json={
                "id": "fixture-completion",
                "object": "chat.completion",
                "created": 0,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Fixture answer"},
                    }
                ],
            },
        )

    def configure(self, model=None):
        # Existing session settings take precedence over environment defaults.
        self.st.session_state.update(
            nebius_api_key="fixture-session-key",
            nebius_base_url="https://api.tokenfactory.nebius.com/v1",
        )
        os.environ["NEBIUS_API_KEY"] = "fixture-environment-key"
        if model is not None:
            os.environ["YOUTUBE_TREND_MODEL"] = model
            os.environ["YOUTUBE_TREND_INGEST_MODEL"] = model

    def assert_payload(self, expected_model):
        self.assertEqual(len(self.requests), 1)
        body = self.requests[0]["body"]
        self.assertEqual(body["model"], expected_model)
        # No direct-provider reasoning or gateway tuning is silently imposed.
        self.assertEqual(set(body), {"model", "messages"})
        return body

    def test_chat_default_and_explicit_models(self):
        for model in [
            None,
            "MiniMaxAI/MiniMax-M3",
            "MiniMaxAI/MiniMax-M2.5",
            "MiniMax-M2.1",
            "custom/team-model",
            "Qwen/Qwen3.5-397B-A17B",
        ]:
            with self.subTest(model=model):
                self.requests.clear()
                self.st.session_state.clear()
                self.configure(model)
                self.app.main()
                body = self.assert_payload(model or "MiniMaxAI/MiniMax-M3")
                self.assertEqual(body["messages"][0]["role"], "system")
                self.assertIn(
                    "Suggest one video about Python.", body["messages"][1]["content"]
                )
                self.assertEqual(
                    self.st.session_state.messages[-1]["content"], "Fixture answer"
                )

    def test_ingestion_default_and_explicit_models(self):
        video = {
            "title": "Python fixture",
            "url": "https://www.youtube.com/watch?v=fixture",
            "description": "Unicode metadata: 测试",
            "topics": ["Python"],
            "views": 123,
        }
        for model in [
            None,
            "MiniMaxAI/MiniMax-M3",
            "MiniMaxAI/MiniMax-M2.5",
            "MiniMax-M2.1",
            "custom/team-model",
            "Qwen/Qwen3.5-397B-A17B",
        ]:
            with self.subTest(model=model):
                self.requests.clear()
                self.st.session_state.clear()
                self.configure(model)
                with patch.object(
                    self.core, "fetch_channel_videos", return_value=[video]
                ):
                    count = self.core.ingest_channel_into_memori(
                        "https://www.youtube.com/@fixture"
                    )
                self.assertEqual(count, 1)
                body = self.assert_payload(model or "MiniMaxAI/MiniMax-M3")
                self.assertEqual(body["messages"][0]["role"], "user")
                self.assertIn("Python fixture", body["messages"][0]["content"])
                self.assertIn("Unicode metadata: 测试", body["messages"][0]["content"])
                self.memory.config.storage.adapter.commit.assert_called()

    def test_environment_only_defaults_initialize_both_clients(self):
        os.environ["NEBIUS_API_KEY"] = "fixture-session-key"
        self.app.main()
        self.assert_payload("MiniMaxAI/MiniMax-M3")
        self.st.session_state.clear()
        self.requests.clear()
        with patch.object(
            self.core,
            "fetch_channel_videos",
            return_value=[{"title": "Environment fixture"}],
        ):
            self.assertEqual(
                self.core.ingest_channel_into_memori(
                    "https://www.youtube.com/@fixture"
                ),
                1,
            )
        self.assert_payload("MiniMaxAI/MiniMax-M3")

    def test_saved_client_is_reused_and_explicit_model_is_not_reset(self):
        self.configure("custom/saved-model")
        self.app.main()
        saved_client = self.st.session_state.openai_client
        self.app.main()
        self.assertIs(self.st.session_state.openai_client, saved_client)
        self.assertEqual(len(self.clients), 1)
        self.assertEqual(
            [request["body"]["model"] for request in self.requests],
            ["custom/saved-model"] * 2,
        )


if __name__ == "__main__":
    unittest.main()
