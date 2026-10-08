import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from agents import Model, ModelResponse, RunConfig, Runner, Usage
from mcp.types import CallToolResult, TextContent
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

from main import Finding, Report, TranscriptSearch, main, make_agent, render_report, run


def tool_result(value=None, **extra):
    data = {"ok": True, "value": value or {"chunks": []}, **extra}
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(data))])


def passage(**extra):
    return {
        "text": "A fixture quote, not a real speaker's words.",
        "video_id": "fixture1234",
        "video_title": "Synthetic test recording",
        "channel_name": "Fixture channel",
        "start_seconds": 65.75,
        **extra,
    }


def fake_server(*results):
    server = AsyncMock()
    server.call_tool.side_effect = [
        CallToolResult(content=[TextContent(type="text", text="Search reference")]),
        *results,
    ]
    return server


class ScriptedModel(Model):
    """Exercise the real SDK tool loop without a provider or credentials."""

    def __init__(self):
        self.step = 0

    async def get_response(self, *args, **kwargs):
        self.step += 1
        if self.step == 1:
            output = [
                ResponseFunctionToolCall(
                    id="test-tool",
                    call_id="test-call",
                    type="function_call",
                    name="search_transcripts",
                    arguments=json.dumps({"query": "fixture"}),
                )
            ]
        else:
            output = [
                ResponseOutputMessage(
                    id="test-message",
                    type="message",
                    role="assistant",
                    status="completed",
                    content=[
                        ResponseOutputText(
                            type="output_text",
                            annotations=[],
                            text=json.dumps(
                                {
                                    "findings": [
                                        {
                                            "interpretation": "A synthetic example.",
                                            "source_ids": ["S1"],
                                        }
                                    ]
                                }
                            ),
                        )
                    ],
                )
            ]
        return ModelResponse(output=output, usage=Usage(), response_id=None)

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError("This example does not stream.")
        yield


class ResearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_sdk_tool_loop_renders_retrieved_source(self):
        server = fake_server(tool_result({"chunks": [passage()]}))
        search = TranscriptSearch(server)
        agent = make_agent(search, ScriptedModel())
        self.assertEqual([tool.name for tool in agent.tools], ["search_transcripts"])
        self.assertEqual(agent.mcp_servers, [])
        result = await Runner.run(
            agent, "fixture question", run_config=RunConfig(tracing_disabled=True)
        )
        report = render_report("fixture question", result.final_output, search)
        self.assertIn("A fixture quote, not a real speaker's words.", report)
        self.assertIn(
            "[1:05](https://www.youtube.com/watch?v=fixture1234&t=65s)", report
        )
        self.assertIn("A synthetic example. (S1)", report)
        self.assertIn(
            "[Arcmira transcript](https://arcmira.com/watch?v=fixture1234&t=65)", report
        )
        self.assertEqual(
            server.call_tool.call_args_list[0].args,
            ("arcmira_describe", {"topic": "search"}),
        )

    async def test_query_cannot_inject_javascript_or_other_methods(self):
        server = fake_server(tool_result())
        search = TranscriptSearch(server)
        query = '"); await arcmira.transcript("other"); //\n'
        await search.search(query)
        name, arguments = server.call_tool.call_args_list[-1].args
        self.assertEqual(name, "arcmira_execute_read")
        code = arguments["code"]
        self.assertTrue(code.startswith("return await arcmira.search("))
        self.assertTrue(code.endswith(");"))
        self.assertEqual(
            json.loads(code[len("return await arcmira.search(") : -2]),
            {"query": query, "limit": 3},
        )

    async def test_search_limit_is_enforced_before_another_call(self):
        server = fake_server(tool_result(), tool_result(), tool_result())
        search = TranscriptSearch(server)
        for _ in range(3):
            await search.search("test")
        with self.assertRaisesRegex(RuntimeError, "at most three"):
            await search.search("fourth")
        self.assertEqual(server.call_tool.call_count, 4)

    async def test_incomplete_results_are_not_rendered_as_verbatim_quotes(self):
        for flag in ("truncated", "outcome_uncertain"):
            server = fake_server(tool_result({"chunks": [passage()]}, **{flag: True}))
            search = TranscriptSearch(server)
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                await search.search("test")
            self.assertEqual(search.sources, {})

    async def test_api_gate_preserves_error_code_and_does_not_retry(self):
        result = tool_result(
            ok=False, error={"code": "quota_exceeded", "retry_after_seconds": 60}
        )
        server = fake_server(result)
        with self.assertRaisesRegex(RuntimeError, "quota_exceeded.*60"):
            await TranscriptSearch(server).search("test")
        self.assertEqual(server.call_tool.call_count, 2)

    async def test_empty_index_result_cannot_become_a_claim(self):
        search = TranscriptSearch(fake_server(tool_result()))
        await search.search("unmatched")
        report = render_report(
            "question",
            Report(
                findings=[
                    Finding(interpretation="No one ever said this", source_ids=[])
                ]
            ),
            search,
        )
        self.assertIn(
            "No passages were returned. See the query coverage and access details below.",
            report,
        )
        self.assertNotIn("No one ever", report)

    async def test_invalid_timestamp_or_video_rejects_entire_batch(self):
        for bad in (
            {"start_seconds": -1},
            {"start_seconds": float("nan")},
            {"video_id": "https://evil.example"},
        ):
            search = TranscriptSearch(
                fake_server(tool_result({"chunks": [passage(), passage(**bad)]}))
            )
            with self.assertRaises(ValueError):
                await search.search("test")
            self.assertEqual(search.sources, {})

    async def test_nullable_metadata_keeps_passage_without_inventing_timestamp(self):
        source = passage(
            start_seconds=None,
            video_title=None,
            channel_name=None,
            published_at=None,
            source=None,
        )
        search = TranscriptSearch(fake_server(tool_result({"chunks": [source]})))
        await search.search("test")
        output = render_report("test", Report(), search)
        self.assertIn("Unknown title", output)
        self.assertIn("Unknown channel", output)
        self.assertIn(
            "[timestamp unavailable](https://www.youtube.com/watch?v=fixture1234)",
            output,
        )
        self.assertNotIn("&t=0", output)
        self.assertIn(
            "[Arcmira transcript](https://arcmira.com/watch?v=fixture1234)", output
        )
        self.assertIn("Published: unknown", output)

    async def test_partial_gated_results_preserve_evidence_and_query_metadata(self):
        metadata = {
            "window": {"after": "2026-08-01", "before": None},
            "as_of": "2026-08-21T12:00:00Z",
            "search_index": {"state": "catching_up", "missing_before": "2026-08-01"},
            "partial": True,
            "failed_batches": 2,
            "access": {
                "code": "freshness_required",
                "gate": "freshness",
                "unlock": {
                    "tier": "pro",
                    "url": "https://arcmira.com/pricing?src=test",
                },
            },
            "note": "Some passages were withheld.",
        }
        source = passage(published_at="2026-08-21T12:00:00Z", source="creator_captions")
        search = TranscriptSearch(
            fake_server(tool_result({"chunks": [source], **metadata}))
        )
        returned = await search.search("test")
        self.assertEqual(returned["search_metadata"], {"query": "test", **metadata})
        output = render_report("test", Report(), search)
        self.assertIn("Transcript source: creator\\_captions", output)
        self.assertIn("Published: 2026-08-21T12:00:00Z", output)
        self.assertIn("not global index freshness", output)
        for fact in (
            '"partial": true',
            '"failed_batches": 2',
            '"state": "catching_up"',
            '"code": "freshness_required"',
            "https://arcmira.com/pricing?src=test",
        ):
            self.assertIn(fact, output)
        self.assertIn("A fixture quote", output)

    async def test_unknown_model_citation_is_rejected(self):
        search = TranscriptSearch(fake_server(tool_result({"chunks": [passage()]})))
        await search.search("test")
        with self.assertRaisesRegex(ValueError, "not retrieved"):
            render_report(
                "question",
                Report(findings=[Finding(interpretation="Claim", source_ids=["S999"])]),
                search,
            )

    async def test_source_markdown_cannot_add_external_links(self):
        search = TranscriptSearch(
            fake_server(
                tool_result(
                    {
                        "chunks": [
                            passage(
                                text="[click](https://evil.example) <script>bad</script>"
                            )
                        ]
                    }
                )
            )
        )
        await search.search("test")
        output = render_report("test", Report(), search)
        self.assertNotIn("[click](https://evil.example)", output)
        self.assertNotIn("<script>", output)

    async def test_mcp_error_stops_before_search(self):
        server = AsyncMock()
        server.call_tool.return_value = CallToolResult(is_error=True, content=[])
        with self.assertRaisesRegex(RuntimeError, "reference"):
            await TranscriptSearch(server).search("test")
        self.assertEqual(server.call_tool.call_count, 1)

    async def test_missing_credentials_prevents_connection(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("main.MCPServerStreamableHttp") as connect,
        ):
            with self.assertRaisesRegex(
                ValueError, "ARCMIRA_API_KEY, OPENAI_API_KEY, OPENAI_MODEL"
            ):
                await run("test")
            connect.assert_not_called()

    async def test_existing_output_prevents_paid_work(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "existing.md"
            target.write_text("keep this")
            with (
                patch("sys.argv", ["main.py", "test", "--output", str(target)]),
                patch("main.run", new_callable=AsyncMock) as research,
            ):
                with self.assertRaises(SystemExit) as failure:
                    main()
                self.assertEqual(failure.exception.code, 2)
                research.assert_not_called()
                self.assertEqual(target.read_text(), "keep this")

    async def test_no_search_is_not_reported_as_no_results(self):
        with self.assertRaisesRegex(ValueError, "did not perform"):
            render_report("test", Report(), TranscriptSearch(AsyncMock()))


if __name__ == "__main__":
    unittest.main()
