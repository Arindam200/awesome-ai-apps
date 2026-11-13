"""Discover the A2A services and delegate one task to each."""

import argparse
import asyncio
import logging
import uuid

import httpx
from a2a.client import A2ACardResolver, Client, ClientConfig, create_client
from a2a.helpers import get_artifact_text, get_message_text
from a2a.types import AgentCard, Message, Part, Role, SendMessageRequest, TaskState

logger = logging.getLogger(__name__)


async def read_response(client: Client, card: AgentCard, prompt: str) -> str:
    answer: str | None = None
    answer_artifact_id: str | None = None
    artifacts: dict[str, str] = {}
    completed = False
    request = SendMessageRequest(
        message=Message(
            role=Role.ROLE_USER,
            message_id=str(uuid.uuid4()),
            parts=[Part(text=prompt)],
        )
    )
    async for event in client.send_message(request):
        if event.HasField("task"):
            logger.info("[%s] task %s submitted", card.name, event.task.id)
        elif event.HasField("status_update"):
            status = event.status_update.status
            detail = (
                get_message_text(status.message) if status.HasField("message") else ""
            )
            logger.info("[%s] %s %s", card.name, TaskState.Name(status.state), detail)
            if status.state == TaskState.TASK_STATE_COMPLETED:
                completed = True
            elif status.state in (
                TaskState.TASK_STATE_FAILED,
                TaskState.TASK_STATE_CANCELED,
                TaskState.TASK_STATE_REJECTED,
            ):
                raise RuntimeError(
                    f"{card.name} ended in {TaskState.Name(status.state)}"
                )
        elif event.HasField("artifact_update"):
            update = event.artifact_update
            artifact_id = update.artifact.artifact_id
            if answer_artifact_id is None:
                answer_artifact_id = artifact_id
            text = get_artifact_text(update.artifact)
            artifacts[artifact_id] = (
                artifacts.get(artifact_id, "") + text if update.append else text
            )
            if artifact_id == answer_artifact_id:
                answer = artifacts[artifact_id]
            logger.info("[%s] artifact: %s", card.name, artifacts[artifact_id])
        elif event.HasField("message"):
            answer = get_message_text(event.message)
            completed = True
            logger.info("[%s] %s", card.name, answer)

    if not completed or answer is None:
        raise RuntimeError(f"{card.name} did not return a completed text answer")
    return answer


async def delegate(
    base_url: str, skill_id: str, prompt: str, *, timeout: float = 120.0
) -> str:
    async with httpx.AsyncClient(timeout=10.0) as http:
        card = await A2ACardResolver(http, base_url).get_agent_card()
    if skill_id not in {skill.id for skill in card.skills}:
        raise ValueError(f"{card.name} does not advertise {skill_id!r}")

    logger.info(
        "Discovered %s: %s via %s",
        card.name,
        skill_id,
        card.supported_interfaces[0].url,
    )
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as http:
        client = await create_client(
            card, client_config=ClientConfig(httpx_client=http)
        )
        try:
            return await asyncio.wait_for(
                read_response(client, card, prompt), timeout=timeout
            )
        finally:
            await client.close()


async def run(
    topic: str, architect_url: str, reviewer_url: str, *, timeout: float = 120.0
) -> str:
    plan = await delegate(architect_url, "draft_plan", topic, timeout=timeout)
    return await delegate(reviewer_url, "review_plan", plan, timeout=timeout)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description="Run the A2A planning workflow")
    parser.add_argument("topic", help="Idea for the architect to plan")
    parser.add_argument("--architect-url", default="http://127.0.0.1:8001")
    parser.add_argument("--reviewer-url", default="http://127.0.0.1:8002")
    parser.add_argument("--timeout", type=float, default=120.0, help="Seconds per task")
    args = parser.parse_args()
    asyncio.run(
        run(args.topic, args.architect_url, args.reviewer_url, timeout=args.timeout)
    )


if __name__ == "__main__":
    main()
