"""Offline tests: the model and Loom are stubbed, so no key or server is needed.

python -m unittest discover -s tests
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Self
from unittest import mock

from loom.errors import BackendUnavailable
from loom.memory import MemorySearchHit, MemorySearchResult
from openai import OpenAIError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


class FakeMemory:
    """Stands in for `Agent.memory`: one store that both agents read and write."""

    def __init__(self) -> None:
        self.rows: dict[str, str] = {}

    async def set(self, memory_key: str, value: str) -> dict:
        for key, held in self.rows.items():
            if held == value:
                return {"memory_key": memory_key, "merged_into_key": key}
        self.rows[memory_key] = value
        return {"memory_key": memory_key, "merged_into_key": ""}

    async def search(self, query: str, top_k: int = 5) -> MemorySearchResult:
        words = set(query.lower().split())
        return MemorySearchResult(
            [
                MemorySearchHit(memory_key=key, memory_type="fact", content_excerpt=value)
                for key, value in self.rows.items()
                if words & set(value.lower().split())
            ][:top_k]
        )


def tool_call(call_id: str, name: str, arguments: dict) -> SimpleNamespace:
    function = SimpleNamespace(name=name, arguments=json.dumps(arguments))
    return SimpleNamespace(id=call_id, function=function)


def reply(content: str = "", tool_calls: list | None = None) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeLLM:
    """Returns the scripted replies in order and records the messages it was sent."""

    def __init__(self, replies: list[SimpleNamespace]) -> None:
        self.replies = list(replies)
        self.sent: list[list] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, model: str, messages: list, tools: list):
        self.sent.append(list(messages))
        return self.replies.pop(0)


def run(llm: FakeLLM, memory: FakeMemory, agent: str, prompt: str) -> str:
    return asyncio.run(main.run_agent(llm, "test-model", memory, agent, prompt))


DEPLOY = {"key": "deploy_days", "fact": "The team deploys on Tuesdays and Thursdays."}


class SharedMemoryTest(unittest.TestCase):
    def test_the_reviewer_reads_what_the_planner_saved(self) -> None:
        memory = FakeMemory()
        planner = FakeLLM([reply(tool_calls=[tool_call("1", "remember", DEPLOY)]), reply("Saved.")])
        run(planner, memory, "planner", "We deploy on Tuesdays and Thursdays.")
        self.assertEqual(memory.rows, {"deploy_days": DEPLOY["fact"]})

        reviewer = FakeLLM(
            [
                reply(
                    tool_calls=[tool_call("2", "recall", {"query": "when does the team deploy"})]
                ),
                reply("Tuesdays and Thursdays [deploy_days]."),
            ]
        )
        answer = run(reviewer, memory, "reviewer", "Can I deploy on Friday?")
        self.assertEqual(answer, "Tuesdays and Thursdays [deploy_days].")
        tool_message = reviewer.sent[1][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertEqual(tool_message["content"], "[deploy_days] " + DEPLOY["fact"])

    def test_a_key_no_recall_returned_is_flagged(self) -> None:
        memory = FakeMemory()
        memory.rows["deploy_days"] = DEPLOY["fact"]
        reviewer = FakeLLM(
            [
                reply(tool_calls=[tool_call("1", "recall", {"query": "deploys"})]),
                reply("Tuesdays [deploy_days] (#made_up) [other]."),
            ]
        )
        answer = run(reviewer, memory, "reviewer", "When do we deploy?")
        self.assertTrue(answer.endswith("(Not found in memory: made_up, other)"))

    def test_an_empty_reply_is_an_error(self) -> None:
        with self.assertRaises(RuntimeError):
            run(FakeLLM([reply("")]), FakeMemory(), "reviewer", "anything")

    def test_the_loop_stops_after_max_turns(self) -> None:
        looping = [
            reply(tool_calls=[tool_call(str(i), "recall", {"query": "x"})])
            for i in range(main.MAX_TURNS)
        ]
        answer = run(FakeLLM(looping), FakeMemory(), "reviewer", "loop")
        self.assertEqual(answer, "Stopped after too many tool calls.")

    def test_a_fact_already_held_reports_the_existing_key(self) -> None:
        memory = FakeMemory()
        memory.rows["deploy_days"] = DEPLOY["fact"]
        result = asyncio.run(main.remember(memory, "deploy_schedule", DEPLOY["fact"]))
        self.assertEqual(result, "already saved as deploy_days")

    def test_bad_arguments_go_back_to_the_model(self) -> None:
        result = asyncio.run(main.call_tool(FakeMemory(), "remember", "{}", set()))
        self.assertTrue(result.startswith("bad arguments for remember"))

    def test_an_empty_search_says_so(self) -> None:
        self.assertEqual(asyncio.run(main.recall(FakeMemory(), "x", set())), "no memories match")

    def test_abstention_with_rows_does_not_supply_or_admit_memories(self) -> None:
        memory = FakeMemory()
        memory.search = mock.AsyncMock(
            return_value=MemorySearchResult(
                [MemorySearchHit("rejected", "fact", "A fact the search declined to support.")],
                abstain=True,
            )
        )
        seen = {"earlier_accepted"}
        result = asyncio.run(main.recall(memory, "an unrelated question", seen))
        self.assertEqual(result, "no memories match")
        self.assertEqual(seen, {"earlier_accepted"})
        self.assertEqual(main.unknown_citations("Answer (#rejected)", seen), ["rejected"])

    def test_mixed_search_only_exposes_accepted_memories_and_citations(self) -> None:
        memory = FakeMemory()
        memory.search = mock.AsyncMock(
            return_value=MemorySearchResult(
                [
                    MemorySearchHit("weak", "fact", "Do not use this.", below_threshold=True),
                    MemorySearchHit("deploy_days", "fact", DEPLOY["fact"]),
                ]
            )
        )
        seen: set[str] = set()
        result = asyncio.run(main.recall(memory, "when do we deploy", seen))
        self.assertEqual(result, "[deploy_days] " + DEPLOY["fact"])
        self.assertEqual(seen, {"deploy_days"})
        self.assertEqual(main.unknown_citations("Answer (#deploy_days) (#weak)", seen), ["weak"])

    def test_only_below_threshold_rows_return_no_match(self) -> None:
        memory = FakeMemory()
        memory.search = mock.AsyncMock(
            return_value=MemorySearchResult(
                [MemorySearchHit("weak", "fact", "Do not use this.", below_threshold=True)]
            )
        )
        seen: set[str] = set()
        self.assertEqual(asyncio.run(main.recall(memory, "anything", seen)), "no memories match")
        self.assertEqual(seen, set())


class FakeAgent:
    """Stands in for `loom.Agent`; raises `fail` on entry when it is set."""

    fail: Exception | None = None

    def __init__(self, **identity: str) -> None:
        self.memory = FakeMemory()

    async def __aenter__(self) -> Self:
        if self.fail:
            raise self.fail
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def run_main(llm: FakeLLM, fail: Exception | None = None) -> tuple[int, str]:
    stderr = io.StringIO()
    FakeAgent.fail = fail
    argv = ["main.py", "--agent", "reviewer", "When do we deploy?"]
    with (
        mock.patch.object(sys, "argv", argv),
        mock.patch.dict(os.environ, {"NEBIUS_API_KEY": "test"}),
        mock.patch.object(main, "load_dotenv"),
        mock.patch.object(main, "Agent", FakeAgent),
        mock.patch.object(main, "AsyncOpenAI", lambda **kw: llm),
        contextlib.redirect_stderr(stderr),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        code = asyncio.run(main.main())
    return code, stderr.getvalue()


class RefusingLLM(FakeLLM):
    async def create(self, model: str, messages: list, tools: list):
        raise OpenAIError("invalid api key")


class ErrorTest(unittest.TestCase):
    def test_a_refused_model_request_is_one_line(self) -> None:
        code, err = run_main(RefusingLLM([]))
        self.assertEqual(
            (code, err), (1, "The model endpoint refused the request: invalid api key\n")
        )

    def test_loom_down_is_one_line(self) -> None:
        code, err = run_main(FakeLLM([]), fail=BackendUnavailable("cannot reach"))
        self.assertEqual(code, 1)
        self.assertIn("Loom is not reachable at", err)


if __name__ == "__main__":
    unittest.main()
