"""Offline regression tests using the real Firecrawl, LiteLLM and ADK clients."""

import contextlib
import functools
import importlib.util
import io
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class ServiceHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append((self.path, payload))
        status = 200
        if self.path == "/v2/scrape":
            status, response = self.server.scrape_response
        elif self.path == "/v1/chat/completions":
            tools = payload.get("tools", [])
            if tools and payload["messages"][-1]["role"] != "tool":
                name = tools[0]["function"]["name"]
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_" + name,
                            "type": "function",
                            "function": {"name": name, "arguments": '{"_": "start"}'},
                        }
                    ],
                }
                finish_reason = "tool_calls"
            else:
                message = {"role": "assistant", "content": "Analysis complete"}
                finish_reason = "stop"
            response = {
                "id": "chatcmpl-local",
                "object": "chat.completion",
                "created": 0,
                "model": payload["model"],
                "choices": [
                    {"index": 0, "message": message, "finish_reason": finish_reason}
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            }
        else:
            status, response = 410, {"success": False, "error": "Retired endpoint"}
        raw = json.dumps(response).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class AgentTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ServiceHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.api_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.env = patch.dict(
            os.environ,
            {
                "NEBIUS_API_KEY": "test-key",
                "NEBIUS_API_BASE": cls.api_url + "/v1",
                "FIRECRAWL_API_KEY": "fc-test-key",
                "LITELLM_LOCAL_MODEL_COST_MAP": "True",
            },
        )
        cls.env.start()
        agent_path = Path(__file__).resolve().parents[1] / "agent.py"
        spec = importlib.util.spec_from_file_location(
            "trend_agent_under_test", agent_path
        )
        cls.agent = importlib.util.module_from_spec(spec)
        with patch("dotenv.load_dotenv", return_value=False):
            spec.loader.exec_module(cls.agent)
        cls.client = cls.agent.Firecrawl

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.server.requests = []
        self.server.scrape_response = (
            200,
            {
                "success": True,
                "data": {
                    "markdown": "# Model catalog",
                    "metadata": {"statusCode": 200},
                },
            },
        )
        client_patch = patch.object(
            self.agent,
            "Firecrawl",
            functools.partial(self.client, api_url=self.api_url),
        )
        client_patch.start()
        self.addCleanup(client_patch.stop)

    def test_scrape_uses_v2_and_unwraps_markdown(self):
        self.assertEqual(
            self.agent.firecrawl_scrape_nebius(""),
            {"type": "firecrawl", "markdown": "# Model catalog"},
        )
        self.assertEqual(len(self.server.requests), 1)
        path, payload = self.server.requests[0]
        self.assertEqual(path, "/v2/scrape")
        self.assertEqual(payload["url"], "https://tokenfactory.nebius.com/")
        self.assertEqual(payload["formats"], ["markdown"])
        self.assertIs(payload["onlyMainContent"], True)

    def test_scrape_http_errors_become_tool_errors(self):
        for status in (401, 402):
            with self.subTest(status=status):
                self.server.scrape_response = (
                    status,
                    {"success": False, "error": "Scrape rejected"},
                )
                result = self.agent.firecrawl_scrape_nebius("")
                self.assertEqual(result["type"], "firecrawl")
                self.assertIn("Scrape rejected", result["error"])
                self.assertNotIn("markdown", result)

    def test_scrape_unsuccessful_response_becomes_tool_error(self):
        self.server.scrape_response = (
            200,
            {"success": False, "error": "Scrape rejected"},
        )
        self.assertIn(
            "Scrape rejected", self.agent.firecrawl_scrape_nebius("")["error"]
        )

    def test_client_initialization_error_becomes_tool_error(self):
        with patch.object(
            self.agent, "Firecrawl", side_effect=ValueError("API key is required")
        ):
            self.assertEqual(
                self.agent.firecrawl_scrape_nebius(""),
                {"type": "firecrawl", "error": "API key is required"},
            )
        self.assertEqual(self.server.requests, [])

    def test_missing_markdown_becomes_tool_error(self):
        self.server.scrape_response = (200, {"success": True, "data": {}})
        result = self.agent.firecrawl_scrape_nebius("")
        self.assertIn("markdown", result["error"])
        self.assertNotIn("markdown", result)

    async def test_pipeline_creates_session_and_executes_all_stages(self):
        output = io.StringIO()
        with (
            patch.object(self.agent, "Exa") as exa,
            patch.object(self.agent, "TavilyClient") as tavily,
            patch.object(
                self.agent.session_service,
                "create_session",
                new_callable=AsyncMock,
                wraps=self.agent.session_service.create_session,
            ) as create_session,
            contextlib.redirect_stdout(output),
        ):
            exa.return_value.search_and_contents.return_value = SimpleNamespace(
                results=[]
            )
            tavily.return_value.search.return_value = {"results": []}
            await self.agent.run_ai_analysis()
        create_session.assert_awaited_once_with(
            app_name=self.agent.APP_NAME,
            user_id=self.agent.USER_ID,
            session_id=self.agent.SESSION_ID,
        )
        exa.return_value.search_and_contents.assert_called_once()
        tavily.return_value.search.assert_called_once()
        requests = [
            p for path, p in self.server.requests if path == "/v1/chat/completions"
        ]
        self.assertEqual(len(requests), 8)
        self.assertEqual(requests[-1]["model"], "openai/gpt-oss-120b")
        self.assertTrue(
            all(p["model"] == "Qwen/Qwen3-30B-A3B-Instruct-2507" for p in requests[:-1])
        )
        self.assertEqual(
            sum(path == "/v2/scrape" for path, _ in self.server.requests), 1
        )
        session = await self.agent.session_service.get_session(
            app_name=self.agent.APP_NAME,
            user_id=self.agent.USER_ID,
            session_id=self.agent.SESSION_ID,
        )
        for key in (
            "exa_results",
            "tavily_results",
            "final_summary",
            "firecrawl_content",
            "analysis_results",
        ):
            self.assertEqual(session.state[key], "Analysis complete")
        self.assertIn("Analysis complete", output.getvalue())


if __name__ == "__main__":
    unittest.main()
