"""Offline checks of the real framework adapters and the A2A handoff."""

import asyncio
import logging
import socket
from contextlib import AsyncExitStack, asynccontextmanager

import pytest
import uvicorn
from a2a.types import (
    AgentCard,
    Artifact,
    Part,
    StreamResponse,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from fastapi import FastAPI, Request

import agents
from client import delegate, read_response, run
from server import create_app


@asynccontextmanager
async def serve(app_factory):
    # Keep the socket open so no other process can take the chosen port.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{sock.getsockname()[1]}"
        server = uvicorn.Server(
            uvicorn.Config(app_factory(url), log_level="error", lifespan="off")
        )
        task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            for _ in range(100):
                if server.started:
                    break
                await asyncio.sleep(0.02)
            assert server.started
            yield url
        finally:
            server.should_exit = True
            await task


@pytest.mark.asyncio
async def test_real_framework_adapters_with_local_model(monkeypatch):
    app = FastAPI()
    requests = []

    @app.post("/v1/chat/completions")
    async def complete(request: Request):
        body = await request.json()
        requests.append(body)
        topic = body["messages"][-1]["content"]
        return {
            "id": "test-completion",
            "object": "chat.completion",
            "created": 1,
            "model": agents.MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": f"Reply to {topic}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.setenv("NEBIUS_MODEL", agents.MODEL)
    async with serve(lambda _: app) as url:
        monkeypatch.setattr(agents, "NEBIUS_BASE_URL", f"{url}/v1/")
        plan = await agents.draft_plan("a search tool")
        assert plan == "Reply to a search tool"
        assert await agents.review_plan(plan) == "Reply to Reply to a search tool"
    assert len(requests) == 2
    assert all(request["model"] == agents.MODEL for request in requests)


@pytest.mark.asyncio
async def test_discovery_delegation_and_streaming(caplog):
    caplog.set_level(logging.INFO, logger="client")

    async def architect(topic):
        return f"Plan for {topic}"

    async def reviewer(plan):
        return f"Review of {plan}"

    async with AsyncExitStack() as stack:
        architect_url = await stack.enter_async_context(
            serve(lambda url: create_app("architect", url, architect))
        )
        reviewer_url = await stack.enter_async_context(
            serve(lambda url: create_app("reviewer", url, reviewer))
        )
        assert await run("a search tool", architect_url, reviewer_url) == (
            "Review of Plan for a search tool"
        )
        output = caplog.text
        assert "Discovered Agno Architect: draft_plan" in output
        assert "Discovered LangGraph Reviewer: review_plan" in output
        assert output.count("TASK_STATE_WORKING") == 2
        assert output.count("TASK_STATE_COMPLETED") == 2
        assert "artifact: Plan for a search tool" in output

        with pytest.raises(ValueError, match="does not advertise"):
            await delegate(architect_url, "review_plan", "a search tool")


@pytest.mark.asyncio
async def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Set NEBIUS_API_KEY in .env"):
        await agents.draft_plan("a search tool")
    with pytest.raises(RuntimeError, match="Set NEBIUS_API_KEY in .env"):
        await agents.review_plan("a plan")


@pytest.mark.asyncio
async def test_task_timeout():
    async def slow_answer(topic):
        await asyncio.sleep(0.2)
        return topic

    async with serve(lambda url: create_app("architect", url, slow_answer)) as url:
        with pytest.raises(asyncio.TimeoutError):
            await delegate(url, "draft_plan", "a search tool", timeout=0.05)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "updates,expected",
    [
        (
            [
                ("plan", "First", False),
                ("note", "Other artifact", False),
                ("plan", " second", True),
            ],
            "First second",
        ),
        (
            [("plan", "Old", False), ("plan", "New", False), ("plan", " plan", True)],
            "New plan",
        ),
    ],
)
async def test_chunked_artifacts_keep_their_own_text(updates, expected):
    class ChunkedClient:
        async def send_message(self, request):
            for artifact_id, text, append in updates:
                yield StreamResponse(
                    artifact_update=TaskArtifactUpdateEvent(
                        artifact=Artifact(
                            artifact_id=artifact_id, parts=[Part(text=text)]
                        ),
                        append=append,
                    )
                )
            yield StreamResponse(
                status_update=TaskStatusUpdateEvent(
                    status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED)
                )
            )

    assert (
        await read_response(ChunkedClient(), AgentCard(name="Chunked"), "idea")
        == expected
    )
