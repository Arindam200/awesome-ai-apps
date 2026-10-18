"""Discover the A2A services and delegate one task to each."""

import argparse
import asyncio
import uuid

import httpx
from a2a.client import A2ACardResolver, create_client
from a2a.helpers import get_artifact_text, get_message_text
from a2a.types import Message, Part, Role, SendMessageRequest, TaskState


async def delegate(base_url: str, skill_id: str, prompt: str) -> str:
    async with httpx.AsyncClient() as http:
        card = await A2ACardResolver(http, base_url).get_agent_card()
    if skill_id not in {skill.id for skill in card.skills}:
        raise ValueError(f"{card.name} does not advertise {skill_id!r}")

    print(f"Discovered {card.name}: {skill_id} via {card.supported_interfaces[0].url}")
    client = await create_client(card)
    answer: str | None = None
    completed = False
    try:
        request = SendMessageRequest(
            message=Message(
                role=Role.ROLE_USER,
                message_id=str(uuid.uuid4()),
                parts=[Part(text=prompt)],
            )
        )
        async for event in client.send_message(request):
            if event.HasField("task"):
                print(f"[{card.name}] task {event.task.id} submitted")
            elif event.HasField("status_update"):
                status = event.status_update.status
                detail = (
                    get_message_text(status.message)
                    if status.HasField("message")
                    else ""
                )
                print(f"[{card.name}] {TaskState.Name(status.state)} {detail}".rstrip())
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
                answer = get_artifact_text(event.artifact_update.artifact)
                print(f"[{card.name}] artifact: {answer}")
            elif event.HasField("message"):
                answer = get_message_text(event.message)
                completed = True
                print(f"[{card.name}] {answer}")
    finally:
        await client.close()

    if not completed or answer is None:
        raise RuntimeError(f"{card.name} did not return a completed text answer")
    return answer


async def run(topic: str, architect_url: str, reviewer_url: str) -> str:
    plan = await delegate(architect_url, "draft_plan", topic)
    return await delegate(reviewer_url, "review_plan", plan)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the A2A planning workflow")
    parser.add_argument("topic", help="Idea for the architect to plan")
    parser.add_argument("--architect-url", default="http://127.0.0.1:8001")
    parser.add_argument("--reviewer-url", default="http://127.0.0.1:8002")
    args = parser.parse_args()
    asyncio.run(run(args.topic, args.architect_url, args.reviewer_url))


if __name__ == "__main__":
    main()
