"""Simple Docker Container Health Monitor Agent using Strands framework."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from strands import Agent, tool
from strands.models.litellm import LiteLLMModel
from config import NEBIUS_API_KEY, NEBIUS_MODEL_ID
from docker_monitor.docker_utils import (
    DockerClientWrapper,
    DockerConnectionError,
    ContainerNotFoundError
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    docker_client = DockerClientWrapper()
except DockerConnectionError as e:
    logger.error(f"Failed to initialize Docker client: {e}")
    docker_client = None


@tool
def get_container_status(filter_by: str = None) -> str:
    """Get status of all containers or filter by name/status."""
    if docker_client is None:
        return "Docker daemon is not accessible. Please ensure Docker is running."
    
    try:
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
        
        return "\n".join(result)
        
    except DockerConnectionError:
        return "Docker daemon is not accessible. Please ensure Docker is running."
    except Exception as e:
        logger.exception("Unexpected error in get_container_status")
        return "An unexpected error occurred. Check logs for details."


@tool
def check_container_health(container_name: str = None) -> str:
    """Check health of specific container or all containers."""
    if docker_client is None:
        return "Docker daemon is not accessible. Please ensure Docker is running."
    
    try:
        if container_name:
            health = docker_client.check_container_health(container_name)
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
        return "\n".join(results)
        
    except ContainerNotFoundError as e:
        return f"Container '{e.container_name}' not found"
    except DockerConnectionError:
        return "Docker daemon is not accessible. Please ensure Docker is running."
    except Exception as e:
        logger.exception("Unexpected error in check_container_health")
        return "An unexpected error occurred. Check logs for details."


@tool
def get_container_logs(container_name: str, lines: int = 100) -> str:
    """Retrieve recent logs from a container."""
    if docker_client is None:
        return "Docker daemon is not accessible. Please ensure Docker is running."
    
    try:
        logs = docker_client.get_container_logs(container_name, lines=lines)
        if not logs:
            return f"No logs found for container '{container_name}'"
        
        result = f"Last {lines} lines from container '{container_name}':\n"
        result += "=" * 60 + "\n"
        result += logs
        return result
        
    except ContainerNotFoundError as e:
        return f"Container '{e.container_name}' not found"
    except DockerConnectionError:
        return "Docker daemon is not accessible. Please ensure Docker is running."
    except Exception as e:
        logger.exception("Unexpected error in get_container_logs")
        return "An unexpected error occurred. Check logs for details."


@tool
def restart_container(container_name: str) -> str:
    """Restart a specific container."""
    if docker_client is None:
        return "Docker daemon is not accessible. Please ensure Docker is running."
    
    try:
        logger.info(f"Restarting container: {container_name}")
        success = docker_client.restart_container(container_name)
        
        if success:
            return f"✓ Successfully restarted container '{container_name}'"
        return f"Container '{container_name}' was restarted but may not be running properly"
        
    except ContainerNotFoundError as e:
        return f"Container '{e.container_name}' not found"
    except DockerConnectionError:
        return "Docker daemon is not accessible. Please ensure Docker is running."
    except Exception as e:
        logger.exception("Unexpected error in restart_container")
        return "An unexpected error occurred. Check logs for details."


@tool
def analyze_container_logs(container_name: str, lines: int = 100) -> str:
    """Analyze and summarize container logs to identify patterns, errors, and issues."""
    if docker_client is None:
        return "Docker daemon is not accessible. Please ensure Docker is running."
    
    try:
        logs = docker_client.get_container_logs(container_name, lines=lines)
        if not logs:
            return f"No logs found for container '{container_name}'"
        
        log_lines = logs.strip().split('\n')
        total_lines = len(log_lines)
        
        info_count = sum(1 for line in log_lines if 'INFO' in line.upper())
        warn_count = sum(1 for line in log_lines if 'WARN' in line.upper())
        error_count = sum(1 for line in log_lines if 'ERROR' in line.upper())
        debug_count = sum(1 for line in log_lines if 'DEBUG' in line.upper())
        
        error_lines = [line for line in log_lines if 'ERROR' in line.upper()]
        recent_errors = error_lines[-5:] if error_lines else []
        
        result = [f"Log Analysis for '{container_name}' (last {lines} lines)", "=" * 60, ""]
        
        result.append("📊 Log Level Distribution:")
        result.append(f"  • Total log lines: {total_lines}")
        result.append(f"  • INFO:  {info_count} ({info_count*100//total_lines if total_lines > 0 else 0}%)")
        result.append(f"  • WARN:  {warn_count} ({warn_count*100//total_lines if total_lines > 0 else 0}%)")
        result.append(f"  • ERROR: {error_count} ({error_count*100//total_lines if total_lines > 0 else 0}%)")
        result.append(f"  • DEBUG: {debug_count} ({debug_count*100//total_lines if total_lines > 0 else 0}%)")
        result.append("")
        
        if error_count == 0:
            result.append("✓ Health: No errors detected in recent logs")
        elif error_count < 5:
            result.append(f"⚠ Health: {error_count} error(s) detected - review recommended")
        else:
            result.append(f"✗ Health: {error_count} errors detected - immediate attention needed")
        result.append("")
        
        if recent_errors:
            result.append(f"🔴 Recent Errors (last {len(recent_errors)}):")
            for i, error in enumerate(recent_errors, 1):
                error_preview = error[:100] + "..." if len(error) > 100 else error
                result.append(f"  {i}. {error_preview}")
            result.append("")
        
        result.append("📝 Activity Summary:")
        if total_lines > 0:
            first_line = log_lines[0][:80] + "..." if len(log_lines[0]) > 80 else log_lines[0]
            last_line = log_lines[-1][:80] + "..." if len(log_lines[-1]) > 80 else log_lines[-1]
            result.append(f"  • First log: {first_line}")
            result.append(f"  • Last log:  {last_line}")
        result.append("")
        
        result.append("💡 Recommendations:")
        if error_count > 10:
            result.append("  • High error rate detected - investigate root cause")
            result.append("  • Consider restarting the container if errors persist")
        elif error_count > 0:
            result.append("  • Review error messages above for specific issues")
        else:
            result.append("  • Container logs look healthy")
        
        if warn_count > total_lines * 0.3:
            result.append("  • High warning rate - may indicate configuration issues")
        
        return "\n".join(result)
        
    except ContainerNotFoundError as e:
        return f"Container '{e.container_name}' not found"
    except DockerConnectionError:
        return "Docker daemon is not accessible. Please ensure Docker is running."
    except Exception as e:
        logger.exception("Unexpected error in analyze_container_logs")
        return "An unexpected error occurred. Check logs for details."


def create_agent() -> Agent:
    """Create and configure the Docker monitoring agent."""
    return Agent(
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
        tools=[get_container_status, check_container_health, get_container_logs, restart_container, analyze_container_logs],
        system_prompt="""You are a Docker container health monitoring assistant. 
You can check container status, verify health, retrieve logs, restart containers, and analyze log patterns.

Use the available tools to help users monitor and manage their Docker containers.
When users ask for log summaries or analysis, use the analyze_container_logs tool.
Provide clear, helpful responses and explain what actions you're taking."""
    )


def main():
    """Main entry point for the simple Docker agent."""
    print("=" * 60)
    print("Docker Container Health Monitor - Simple Agent")
    print("=" * 60)
    print()
    
    if docker_client is None:
        print("ERROR: Could not connect to Docker daemon.")
        print("Please ensure Docker is running and try again.")
        return
    
    print("Connected to Docker daemon successfully!")
    print()
    print("Example queries:")
    print("  - Check container status")
    print("  - Show me logs for nginx")
    print("  - Analyze logs from demo-logger")
    print("  - Give me a summary of demo-redis logs")
    print("  - Is redis healthy?")
    print("  - Restart the postgres container")
    print()
    print("Type 'quit' or 'exit' to stop")
    print("=" * 60)
    print()
    
    agent = create_agent()
    
    while True:
        try:
            task = input("Enter task: ").strip()
            
            if task.lower() in ['quit', 'q', 'exit']:
                print("Goodbye!")
                break
            
            if not task:
                continue
            
            print("Processing...")
            result = agent(task)
            print(f"\n{result}\n")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.exception("Error processing task")
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
