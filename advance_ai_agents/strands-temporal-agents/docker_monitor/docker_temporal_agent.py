"""Temporal Docker Container Health Monitor with automatic retries and fault tolerance."""

import sys
from pathlib import Path
import logging
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@activity.defn
async def get_container_status_activity(filter_by: str = None) -> str:
    """Get container status with optional filtering."""
    from docker_monitor.docker_utils import DockerClientWrapper, DockerConnectionError
    
    activity.logger.info(f"Getting container status, filter: {filter_by}")
    
    try:
        docker_client = DockerClientWrapper()
        
        filters = None
        if filter_by:
            if filter_by.lower() in ['running', 'stopped', 'paused', 'exited', 'restarting']:
                filters = {'status': filter_by.lower()}
            else:
                filters = {'name': filter_by}
        
        containers = docker_client.get_containers(all=True, filters=filters)
        
        if not containers:
            return f"No containers found matching '{filter_by}'" if filter_by else "No containers found on this system"
        
        result = [f"Found {len(containers)} container(s):\n"]
        for container in containers:
            result.append(container.format_summary())
            result.append("")
        
        activity.logger.info(f"Successfully retrieved {len(containers)} containers")
        return "\n".join(result)
        
    except DockerConnectionError as e:
        activity.logger.error(f"Docker connection error: {e}")
        raise
    except Exception as e:
        activity.logger.exception("Unexpected error in get_container_status_activity")
        raise ApplicationError(f"Unexpected error: {str(e)}", non_retryable=True)


@activity.defn
async def check_container_health_activity(container_name: str = None) -> str:
    """Check health of specific container or all containers."""
    from docker_monitor.docker_utils import DockerClientWrapper, DockerConnectionError, ContainerNotFoundError
    
    activity.logger.info(f"Checking container health: {container_name or 'all'}")
    
    try:
        docker_client = DockerClientWrapper()
        
        if container_name:
            health = docker_client.check_container_health(container_name)
            activity.logger.info(f"Health check complete for {container_name}: {'healthy' if health.is_healthy else 'unhealthy'}")
            return health.format_summary()
        
        containers = docker_client.get_containers(all=False)
        if not containers:
            return "No running containers found"
        
        results = [f"Health check for {len(containers)} running container(s):\n"]
        healthy_count = 0
        
        for container in containers:
            try:
                health = docker_client.check_container_health(container.name)
                results.append(health.format_summary())
                results.append("")
                if health.is_healthy:
                    healthy_count += 1
            except Exception as e:
                results.append(f"✗ {container.name}: Error checking health - {str(e)}")
                results.append("")
        
        results.append(f"Summary: {healthy_count}/{len(containers)} containers healthy")
        activity.logger.info(f"Health check complete: {healthy_count}/{len(containers)} healthy")
        return "\n".join(results)
        
    except ContainerNotFoundError as e:
        activity.logger.error(f"Container not found: {e}")
        raise ApplicationError(f"Container '{e.container_name}' not found", non_retryable=True)
    except DockerConnectionError as e:
        activity.logger.error(f"Docker connection error: {e}")
        raise
    except Exception as e:
        activity.logger.exception("Unexpected error in check_container_health_activity")
        raise ApplicationError(f"Unexpected error: {str(e)}", non_retryable=True)


@activity.defn
async def get_container_logs_activity(container_name: str, lines: int = 100) -> str:
    """Retrieve container logs."""
    from docker_monitor.docker_utils import DockerClientWrapper, DockerConnectionError, ContainerNotFoundError
    
    activity.logger.info(f"Getting logs for {container_name}, lines: {lines}")
    
    try:
        docker_client = DockerClientWrapper()
        logs = docker_client.get_container_logs(container_name, lines=lines)
        
        if not logs:
            return f"No logs found for container '{container_name}'"
        
        result = f"Last {lines} lines from container '{container_name}':\n"
        result += "=" * 60 + "\n"
        result += logs
        
        activity.logger.info(f"Successfully retrieved logs for {container_name}")
        return result
        
    except ContainerNotFoundError as e:
        activity.logger.error(f"Container not found: {e}")
        raise ApplicationError(f"Container '{e.container_name}' not found", non_retryable=True)
    except DockerConnectionError as e:
        activity.logger.error(f"Docker connection error: {e}")
        raise
    except Exception as e:
        activity.logger.exception("Unexpected error in get_container_logs_activity")
        raise ApplicationError(f"Unexpected error: {str(e)}", non_retryable=True)


@activity.defn
async def restart_container_activity(container_name: str) -> str:
    """Restart a container."""
    from docker_monitor.docker_utils import DockerClientWrapper, DockerConnectionError, ContainerNotFoundError
    
    activity.logger.info(f"Restarting container: {container_name}")
    
    try:
        docker_client = DockerClientWrapper()
        success = docker_client.restart_container(container_name)
        
        if success:
            activity.logger.info(f"Successfully restarted {container_name}")
            return f"✓ Successfully restarted container '{container_name}'"
        
        activity.logger.warning(f"Container {container_name} restarted but may not be running properly")
        return f"Container '{container_name}' was restarted but may not be running properly"
        
    except ContainerNotFoundError as e:
        activity.logger.error(f"Container not found: {e}")
        raise ApplicationError(f"Container '{e.container_name}' not found", non_retryable=True)
    except DockerConnectionError as e:
        activity.logger.error(f"Docker connection error: {e}")
        raise
    except Exception as e:
        activity.logger.exception("Unexpected error in restart_container_activity")
        raise ApplicationError(f"Unexpected error: {str(e)}", non_retryable=True)


@activity.defn
async def ai_orchestrator_activity(task: str) -> str:
    """AI-powered task orchestration that analyzes queries and returns operation plans."""
    from config import NEBIUS_API_KEY, NEBIUS_MODEL_ID
    
    activity.logger.info(f"AI orchestrator processing task: {task}")
    
    try:
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
            system_prompt="""Analyze the user request and return a comma-separated list of Docker operations.

Available operations:
- status[:filter] - Get container status (optionally filtered by name or status)
- health[:container] - Check health (specific container or all if omitted)
- logs:container[:lines] - Get container logs (default 100 lines)
- restart:container - Restart a container

Examples:
"check container status" -> "status"
"show me nginx logs" -> "logs:nginx"
"is redis healthy?" -> "health:redis"
"restart postgres" -> "restart:postgres"
"check nginx health and show logs" -> "health:nginx,logs:nginx"
"show running containers" -> "status:running"

Return ONLY the comma-separated operation list, no explanations."""
        )
        
        result = agent(task)
        plan = str(result.content if hasattr(result, 'content') else result).strip()
        
        if not plan or len(plan) > 200:
            activity.logger.warning(f"AI returned invalid plan: {plan}")
            plan = "status"
        
        activity.logger.info(f"AI orchestrator generated plan: {plan}")
        return plan
        
    except Exception as e:
        activity.logger.warning(f"AI orchestrator failed: {e}, falling back to 'status'")
        return "status"


@workflow.defn
class DockerMonitorWorkflow:
    """Temporal workflow for Docker container monitoring with automatic retries."""
    
    @workflow.run
    async def run(self, task: str) -> str:
        """Execute Docker monitoring workflow."""
        workflow.logger.info(f"Starting Docker monitor workflow for task: {task}")
        
        plan = await workflow.execute_activity(
            ai_orchestrator_activity,
            task,
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(
                maximum_attempts=2,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=1),
                backoff_coefficient=1.0
            )
        )
        
        workflow.logger.info(f"Execution plan: {plan}")
        
        results = []
        operations = [op.strip() for op in plan.split(',') if op.strip()]
        
        for operation_spec in operations:
            try:
                result = await self._execute_operation(operation_spec)
                results.append(result)
            except Exception as e:
                workflow.logger.error(f"Operation {operation_spec} failed: {e}")
                results.append(f"Operation '{operation_spec}' failed: {str(e)}")
        
        final_result = "\n\n".join(results)
        workflow.logger.info("Workflow completed successfully")
        return final_result
    
    async def _execute_operation(self, operation_spec: str) -> str:
        """Execute a single operation based on the operation specification."""
        parts = operation_spec.split(':')
        operation = parts[0].lower()
        param1 = parts[1] if len(parts) > 1 else None
        param2 = parts[2] if len(parts) > 2 else None
        
        if operation == 'status':
            return await workflow.execute_activity(
                get_container_status_activity,
                param1,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=5),
                    backoff_coefficient=2.0
                )
            )
        
        elif operation == 'health':
            return await workflow.execute_activity(
                check_container_health_activity,
                param1,
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=10),
                    backoff_coefficient=2.0
                )
            )
        
        elif operation == 'logs':
            if not param1:
                return "Error: logs operation requires container name"
            
            lines = int(param2) if param2 else 100
            return await workflow.execute_activity(
                get_container_logs_activity,
                args=[param1, lines],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(
                    maximum_attempts=2,
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=5),
                    backoff_coefficient=2.0
                )
            )
        
        elif operation == 'restart':
            if not param1:
                return "Error: restart operation requires container name"
            
            return await workflow.execute_activity(
                restart_container_activity,
                param1,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=5,
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(seconds=30),
                    backoff_coefficient=2.0
                )
            )
        
        else:
            return f"Unknown operation: {operation}"
