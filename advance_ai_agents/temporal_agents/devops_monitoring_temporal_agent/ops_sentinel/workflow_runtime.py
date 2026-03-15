"""Temporal workflow runtime for Ops Sentinel."""

import logging
import sys
from datetime import timedelta
from pathlib import Path
from typing import List

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@activity.defn
async def inspect_services_activity(filter_token: str = None) -> str:
    from ops_sentinel.runtime_gateway import OpsRuntimeGateway, RuntimeUnavailableError

    activity.logger.info("Inspecting services with filter token: %s", filter_token)
    try:
        gateway = OpsRuntimeGateway()
        filters = None
        if filter_token:
            normalized = filter_token.lower()
            if normalized in {"running", "stopped", "paused", "exited", "restarting"}:
                filters = {"status": normalized}
            else:
                filters = {"name": filter_token}

        snapshots = gateway.list_services(include_stopped=True, filters=filters)
        if not snapshots:
            return f"No services matched '{filter_token}'" if filter_token else "No services found"

        lines = [f"Discovered {len(snapshots)} service(s):", ""]
        for snapshot in snapshots:
            lines.append(snapshot.summary())
            lines.append("")
        return "\n".join(lines).strip()
    except RuntimeUnavailableError as error:
        raise error
    except Exception as error:
        raise ApplicationError(f"service inspection failed: {error}", non_retryable=True)


@activity.defn
async def health_overview_activity(service_name: str = None) -> str:
    from ops_sentinel.runtime_gateway import OpsRuntimeGateway, RuntimeUnavailableError, ServiceMissingError

    activity.logger.info("Generating health overview for %s", service_name or "all running")
    try:
        gateway = OpsRuntimeGateway()
        if service_name:
            return gateway.inspect_health(service_name).summary()

        running = gateway.list_services(include_stopped=False)
        if not running:
            return "No running services found"

        healthy_count = 0
        lines = [f"Health overview for {len(running)} running service(s):", ""]
        for service in running:
            report = gateway.inspect_health(service.name)
            lines.append(report.summary())
            lines.append("")
            if report.healthy:
                healthy_count += 1

        lines.append(f"Summary: {healthy_count}/{len(running)} services healthy")
        return "\n".join(lines)
    except ServiceMissingError as error:
        raise ApplicationError(str(error), non_retryable=True)
    except RuntimeUnavailableError as error:
        raise error
    except Exception as error:
        raise ApplicationError(f"health overview failed: {error}", non_retryable=True)


@activity.defn
async def collect_logs_activity(service_name: str, lines: int = 100) -> str:
    from ops_sentinel.runtime_gateway import OpsRuntimeGateway, RuntimeUnavailableError, ServiceMissingError

    activity.logger.info("Collecting logs for %s with %s lines", service_name, lines)
    try:
        gateway = OpsRuntimeGateway()
        content = gateway.fetch_logs(service_name, lines=lines)
        if not content:
            return f"No log output found for service '{service_name}'"
        return f"Last {lines} lines for '{service_name}':\n{'=' * 64}\n{content}"
    except ServiceMissingError as error:
        raise ApplicationError(str(error), non_retryable=True)
    except RuntimeUnavailableError as error:
        raise error
    except Exception as error:
        raise ApplicationError(f"log collection failed: {error}", non_retryable=True)


@activity.defn
async def recycle_service_activity(service_name: str) -> str:
    from ops_sentinel.runtime_gateway import OpsRuntimeGateway, RuntimeUnavailableError, ServiceMissingError

    activity.logger.info("Recycling service %s", service_name)
    try:
        gateway = OpsRuntimeGateway()
        restarted = gateway.restart_service(service_name)
        if restarted:
            return f"Service '{service_name}' restarted successfully"
        return f"Service '{service_name}' restart was issued but service is not running"
    except ServiceMissingError as error:
        raise ApplicationError(str(error), non_retryable=True)
    except RuntimeUnavailableError as error:
        raise error
    except Exception as error:
        raise ApplicationError(f"service recycle failed: {error}", non_retryable=True)


@activity.defn
async def build_execution_plan_activity(user_request: str) -> str:
    from config import NEBIUS_API_KEY, NEBIUS_MODEL_ID
    from strands import Agent
    from strands.models.litellm import LiteLLMModel

    activity.logger.info("Generating execution plan for request: %s", user_request)
    try:
        planner = Agent(
            model=LiteLLMModel(
                client_args={"api_key": NEBIUS_API_KEY},
                model_id=NEBIUS_MODEL_ID,
                params={"max_tokens": 1200, "temperature": 0.2},
            ),
            system_prompt="""You are a runtime operations planner.

Return only a comma-separated execution plan from these actions:
- inspect[:filter]
- health[:service]
- logs:service[:lines]
- recycle:service

Examples:
"show running services" -> "inspect:running"
"is redis healthy" -> "health:redis"
"show logs for api" -> "logs:api"
"restart worker and check health" -> "recycle:worker,health:worker"

Keep plans concise and syntactically valid.""",
        )
        plan_output = planner(user_request)
        plan_text = str(plan_output.content if hasattr(plan_output, "content") else plan_output).strip()
        if not plan_text or len(plan_text) > 300:
            return "inspect"
        return plan_text
    except Exception as error:
        activity.logger.warning("Planner failed (%s). Using fallback plan.", error)
        return "inspect"


OPS_ACTIVITIES = [
    inspect_services_activity,
    health_overview_activity,
    collect_logs_activity,
    recycle_service_activity,
    build_execution_plan_activity,
]


@workflow.defn
class OpsSentinelWorkflow:
    @workflow.run
    async def run(self, user_request: str) -> str:
        workflow.logger.info("Starting Ops Sentinel workflow for request: %s", user_request)

        plan = await workflow.execute_activity(
            build_execution_plan_activity,
            user_request,
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        steps = [segment.strip() for segment in plan.split(",") if segment.strip()]
        if not steps:
            steps = ["inspect"]

        outputs: List[str] = []
        for step in steps:
            try:
                outputs.append(await self._run_step(step))
            except Exception as error:
                workflow.logger.error("Step failed (%s): %s", step, error)
                outputs.append(f"Step '{step}' failed: {error}")

        return "\n\n".join(outputs)

    async def _run_step(self, step: str) -> str:
        tokens = step.split(":")
        action = tokens[0].strip().lower()
        first = tokens[1].strip() if len(tokens) > 1 else None
        second = tokens[2].strip() if len(tokens) > 2 else None

        if action == "inspect":
            return await workflow.execute_activity(
                inspect_services_activity,
                first,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

        if action == "health":
            return await workflow.execute_activity(
                health_overview_activity,
                first,
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

        if action == "logs":
            if not first:
                return "Step 'logs' requires a service name"
            line_count = int(second) if second else 100
            return await workflow.execute_activity(
                collect_logs_activity,
                args=[first, line_count],
                start_to_close_timeout=timedelta(seconds=12),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

        if action == "recycle":
            if not first:
                return "Step 'recycle' requires a service name"
            return await workflow.execute_activity(
                recycle_service_activity,
                first,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=4),
            )

        return f"Unknown action: {action}"
