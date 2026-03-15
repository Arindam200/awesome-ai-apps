"""Simple Temporal Agent - time, weather, files, and AI facts.

Usage:
    python temporal_agent.py worker   # Start the worker (Terminal 1)
    python temporal_agent.py          # Start the client (Terminal 2)
"""

import os
import sys
import asyncio
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import Worker

# ── Config ───────────────────────────────────────────────────────────────────

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TASK_QUEUE = "strands-temporal-agent-queue"
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")
NEBIUS_MODEL_ID = os.getenv("NEBIUS_MODEL_ID", "nebius/deepseek-ai/DeepSeek-V3-0324")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Activities ───────────────────────────────────────────────────────────────


@activity.defn
def get_time_activity() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@activity.defn
def get_weather_activity(city: str) -> str:
    import requests

    try:
        response = requests.get(f"https://wttr.in/{city}?format=%C+%t", timeout=10)
        if response.status_code == 200:
            return f"{city}: {response.text.strip()}"
        return f"Weather unavailable for {city}"
    except requests.RequestException:
        raise


@activity.defn
def list_files_activity() -> str:
    files = [f for f in os.listdir(".") if f.endswith(".py")]
    return f"Files: {', '.join(files[:5])}"


@activity.defn
def get_fact_activity(topic: str) -> str:
    from strands import Agent
    from strands.models.litellm import LiteLLMModel

    agent = Agent(
        model=LiteLLMModel(
            client_args={
                "api_key": NEBIUS_API_KEY,
            },
            model_id=NEBIUS_MODEL_ID,
            params={
                "max_tokens": 1500,
                "temperature": 0.7,
            },
        ),
        system_prompt="Provide interesting, accurate facts about the requested topic. Be concise.",
    )

    result = agent(f"Tell me an interesting fact about {topic}")
    return str(result).strip()


@activity.defn
def ai_orchestrator_activity(task: str) -> str:
    from strands import Agent
    from strands.models.litellm import LiteLLMModel

    agent = Agent(
        model=LiteLLMModel(
            client_args={
                "api_key": NEBIUS_API_KEY,
            },
            model_id=NEBIUS_MODEL_ID,
            params={
                "max_tokens": 1500,
                "temperature": 0.7,
            },
        ),
        system_prompt="""Analyze the user request and return a comma-separated list of activities.

Available: time, weather:city, files, fact:topic

Examples:
"what time is it" -> "time"
"weather in tokyo" -> "time,weather:tokyo"
"show files and weather in london" -> "time,files,weather:london"

Always include 'time' first. Extract cities/topics accurately.""",
    )

    try:
        plan = str(agent(task)).strip()
        return plan
    except Exception as e:
        logger.warning(f"AI orchestrator failed: {e}")
        return "time"


ALL_ACTIVITIES = [
    get_time_activity,
    get_weather_activity,
    list_files_activity,
    get_fact_activity,
    ai_orchestrator_activity,
]

# ── Workflow ─────────────────────────────────────────────────────────────────


@workflow.defn
class TemporalAgentWorkflow:

    @workflow.run
    async def run(self, task: str) -> str:
        try:
            plan = await workflow.execute_activity(
                ai_orchestrator_activity,
                task,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
        except Exception:
            plan = "time"

        results = []
        for activity_spec in [s.strip() for s in plan.split(",") if s.strip()]:
            if ":" in activity_spec:
                activity_name, param = activity_spec.split(":", 1)
            else:
                activity_name, param = activity_spec, None

            try:
                if activity_name == "time":
                    r = await workflow.execute_activity(
                        get_time_activity,
                        start_to_close_timeout=timedelta(seconds=5),
                    )
                    results.append(f"Time: {r}")

                elif activity_name == "weather" and param:
                    r = await workflow.execute_activity(
                        get_weather_activity,
                        param,
                        start_to_close_timeout=timedelta(seconds=15),
                        retry_policy=RetryPolicy(maximum_attempts=3),
                    )
                    results.append(f"Weather: {r}")

                elif activity_name == "files":
                    r = await workflow.execute_activity(
                        list_files_activity,
                        start_to_close_timeout=timedelta(seconds=5),
                    )
                    results.append(f"Files: {r}")

                elif activity_name == "fact" and param:
                    r = await workflow.execute_activity(
                        get_fact_activity,
                        param,
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                    results.append(f"Fact: {r}")

            except Exception as e:
                results.append(f"{activity_name}: failed - {e}")

        return " | ".join(results)


# ── Worker ───────────────────────────────────────────────────────────────────


async def run_worker():
    print(f"Connecting to Temporal at {TEMPORAL_HOST}...")
    client = await Client.connect(TEMPORAL_HOST)
    print(f"✓ Connected. Listening on queue: {TASK_QUEUE}")
    print("Press Ctrl+C to stop\n")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TemporalAgentWorkflow],
        activities=ALL_ACTIVITIES,
        activity_executor=ThreadPoolExecutor(max_workers=5),
    )
    await worker.run()


# ── Client ───────────────────────────────────────────────────────────────────


async def run_client():
    print("=" * 60)
    print("Simple Temporal Agent")
    print("=" * 60)

    try:
        print(f"Connecting to Temporal at {TEMPORAL_HOST}...")
        client = await Client.connect(TEMPORAL_HOST)
        print("✓ Connected\n")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        print("Make sure Temporal is running: temporal server start-dev")
        return

    print("Example queries:")
    print("  - What time is it?")
    print("  - Weather in Tokyo")
    print("  - Show files and weather in London")
    print("  - Tell me a fact about black holes")
    print("\nType 'quit' to stop")
    print("=" * 60 + "\n")

    while True:
        try:
            task = input("Enter task: ").strip()
            if task.lower() in ("quit", "q", "exit"):
                print("Goodbye!")
                break
            if not task:
                continue

            workflow_id = f"agent-workflow-{uuid.uuid4()}"
            print("Processing...")

            result = await client.execute_workflow(
                TemporalAgentWorkflow.run,
                task,
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
            print(f"\nResult: {result}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\n✗ Error: {e}\n")


# ── Main ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "client"

    if mode == "worker":
        asyncio.run(run_worker())
    else:
        asyncio.run(run_client())
