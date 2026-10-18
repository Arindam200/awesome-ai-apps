"""Run either framework agent as an A2A JSON-RPC service."""

import argparse
from collections.abc import Awaitable, Callable

import uvicorn
from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Part,
    Task,
    TaskState,
    TaskStatus,
)
from dotenv import load_dotenv
from fastapi import FastAPI

from agents import draft_plan, get_api_key, review_plan

Answer = Callable[[str], Awaitable[str]]

AGENTS: dict[str, tuple[str, str, Answer]] = {
    "architect": ("Agno Architect", "draft_plan", draft_plan),
    "reviewer": ("LangGraph Reviewer", "review_plan", review_plan),
}


class StreamingExecutor(AgentExecutor):
    def __init__(self, name: str, answer: Answer):
        self.name = name
        self.answer = answer

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if not context.message or not context.task_id or not context.context_id:
            return

        await event_queue.enqueue_event(
            Task(
                id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                history=[context.message],
            )
        )
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=context.task_id,
            context_id=context.context_id,
        )
        await updater.start_work(
            message=updater.new_agent_message(
                parts=[Part(text=f"{self.name} is working...")]
            )
        )
        answer = await self.answer(context.get_user_input())
        await updater.add_artifact(
            parts=[Part(text=answer)], name="response", last_chunk=True
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=context.task_id or "",
            context_id=context.context_id or "",
        )
        await updater.cancel()


def create_app(kind: str, public_url: str, answer: Answer | None = None) -> FastAPI:
    """Create one service; inject an answer function for offline integration tests."""
    name, skill_id, default_answer = AGENTS[kind]
    card = AgentCard(
        name=name,
        description=f"{name} in an A2A multi-agent planning example.",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id=skill_id,
                name=name,
                description=(
                    "Draft a three-step implementation plan"
                    if kind == "architect"
                    else "Review a plan and suggest an improvement"
                ),
                tags=["planning"],
                examples=["Plan a documentation search tool"],
            )
        ],
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                protocol_version="1.0",
                url=f"{public_url.rstrip('/')}/a2a/jsonrpc",
            )
        ],
    )
    handler = DefaultRequestHandler(
        agent_executor=StreamingExecutor(name, answer or default_answer),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    app = FastAPI()
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(card),
        jsonrpc_routes=create_jsonrpc_routes(handler, rpc_url="/a2a/jsonrpc"),
    )
    return app


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run an A2A example agent")
    parser.add_argument("kind", choices=AGENTS)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--public-url", help="URL clients use to reach this service")
    args = parser.parse_args()
    try:
        get_api_key()
    except RuntimeError as error:
        parser.error(str(error))
    public_url = args.public_url or f"http://{args.host}:{args.port}"
    uvicorn.run(create_app(args.kind, public_url), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
