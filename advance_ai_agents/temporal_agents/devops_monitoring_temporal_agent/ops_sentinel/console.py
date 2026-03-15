import asyncio
import logging
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from temporalio.client import Client
from temporalio.worker import Worker

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import OPS_SENTINEL_TASK_QUEUE, TEMPORAL_HOST
from ops_sentinel.workflow_runtime import OPS_ACTIVITIES, OpsSentinelWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def build_workflow_id() -> str:
    return f"ops-sentinel-{uuid.uuid4()}"


async def run_worker() -> None:
    print(f"Connecting to Temporal at {TEMPORAL_HOST}...")
    client = await Client.connect(TEMPORAL_HOST)
    print(f"Connected. Listening on queue: {OPS_SENTINEL_TASK_QUEUE}")
    print("Press Ctrl+C to stop\n")

    worker = Worker(
        client,
        task_queue=OPS_SENTINEL_TASK_QUEUE,
        workflows=[OpsSentinelWorkflow],
        activities=OPS_ACTIVITIES,
        activity_executor=ThreadPoolExecutor(max_workers=5),
    )
    await worker.run()


async def run_console() -> None:
    print("=" * 64)
    print("Ops Sentinel Console")
    print("=" * 64)
    print("Temporal UI: http://localhost:8233")
    print()

    try:
        print(f"Connecting to Temporal at {TEMPORAL_HOST}...")
        client = await Client.connect(TEMPORAL_HOST)
        print("Connected\n")
    except Exception as error:
        print(f"Connection failed: {error}")
        print("Start Temporal first with: temporal server start-dev")
        return

    print("Try prompts like:")
    print("  - show running containers")
    print("  - inspect health for api")
    print("  - fetch logs from worker")
    print("  - restart cache and inspect health")
    print("Type 'quit' to exit\n")

    while True:
        try:
            user_request = input("ops> ").strip()
            if user_request.lower() in {"quit", "q", "exit"}:
                print("Session ended")
                break
            if not user_request:
                continue

            workflow_id = build_workflow_id()
            logger.info("Dispatching workflow %s", workflow_id)
            print(f"Executing workflow: {workflow_id[:18]}...")

            response = await client.execute_workflow(
                OpsSentinelWorkflow.run,
                user_request,
                id=workflow_id,
                task_queue=OPS_SENTINEL_TASK_QUEUE,
            )

            print("\n" + response + "\n")
        except KeyboardInterrupt:
            print("\nSession ended")
            break
        except Exception as error:
            logger.exception("Console request failed")
            print(f"Error: {error}\n")


def main() -> None:
    mode = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "console"
    if mode == "worker":
        asyncio.run(run_worker())
        return
    asyncio.run(run_console())


if __name__ == "__main__":
    main()
