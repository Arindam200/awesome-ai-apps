"""Runtime gateway for container operations used by Ops Sentinel workflows."""

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import docker
    from docker.errors import DockerException, NotFound
except ImportError:
    docker = None

    class DockerException(Exception):
        pass

    class NotFound(Exception):
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    CPU_THRESHOLD_PERCENT,
    DOCKER_TIMEOUT,
    MEMORY_THRESHOLD_PERCENT,
    RESTART_COUNT_THRESHOLD,
)

logger = logging.getLogger(__name__)


class RuntimeUnavailableError(Exception):
    pass


class ServiceMissingError(Exception):
    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(f"Service '{service_name}' was not found")


@dataclass
class ServiceSnapshot:
    container_id: str
    name: str
    state: str
    image: str
    created_at: datetime
    started_at: Optional[datetime] = None
    ports: Dict[str, List[str]] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "container_id": self.container_id,
            "name": self.name,
            "state": self.state,
            "image": self.image,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ports": self.ports,
            "labels": self.labels,
        }

    def summary(self) -> str:
        uptime = "not started"
        if self.started_at:
            delta = datetime.now(self.started_at.tzinfo) - self.started_at
            total_hours = delta.total_seconds() / 3600
            if total_hours < 1:
                uptime = f"{int(delta.total_seconds() / 60)} minutes"
            elif total_hours < 24:
                uptime = f"{int(total_hours)} hours"
            else:
                uptime = f"{int(total_hours / 24)} days"

        mapped_ports = ", ".join(
            f"{k}->{','.join(v)}" for k, v in self.ports.items()
        ) or "none"

        return (
            f"Service: {self.name} ({self.container_id})\n"
            f"  State: {self.state}\n"
            f"  Image: {self.image}\n"
            f"  Uptime: {uptime}\n"
            f"  Ports: {mapped_ports}"
        )


@dataclass
class ServiceHealth:
    service_name: str
    healthy: bool
    state: str
    probe_status: Optional[str] = None
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    restart_count: int = 0
    concerns: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "service_name": self.service_name,
            "healthy": self.healthy,
            "state": self.state,
            "probe_status": self.probe_status,
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "restart_count": self.restart_count,
            "concerns": self.concerns,
        }

    def summary(self) -> str:
        icon = "✓" if self.healthy else "✗"
        label = "Healthy" if self.healthy else "Unhealthy"
        lines = [f"{icon} {self.service_name}: {label}", f"  State: {self.state}"]

        if self.probe_status:
            lines.append(f"  Probe: {self.probe_status}")
        if self.cpu_percent is not None:
            lines.append(f"  CPU: {self.cpu_percent:.1f}%")
        if self.memory_percent is not None:
            lines.append(f"  Memory: {self.memory_percent:.1f}%")
        if self.restart_count:
            lines.append(f"  Restarts: {self.restart_count}")
        if self.concerns:
            lines.append(f"  Concerns: {', '.join(self.concerns)}")

        return "\n".join(lines)


@dataclass
class RuntimeActionReport:
    action: str
    success: bool
    payload: Any
    error: Optional[str] = None
    recorded_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "success": self.success,
            "payload": self.payload,
            "error": self.error,
            "recorded_at": self.recorded_at.isoformat(),
        }


class OpsRuntimeGateway:
    def __init__(self):
        if docker is None:
            raise RuntimeUnavailableError(
                "Python docker package is not installed. Install dependencies from requirements.txt."
            )
        try:
            self.client = docker.from_env(timeout=DOCKER_TIMEOUT)
            self.client.ping()
            logger.info("Connected to Docker runtime")
        except DockerException as error:
            logger.error("Docker runtime unavailable: %s", error)
            raise RuntimeUnavailableError(
                "Docker runtime is unavailable. Ensure Docker is running."
            ) from error

    def list_services(self, include_stopped: bool = True, filters: Optional[dict] = None) -> List[ServiceSnapshot]:
        try:
            containers = self.client.containers.list(all=include_stopped, filters=filters)
            return [self._to_snapshot(container) for container in containers]
        except DockerException as error:
            raise RuntimeUnavailableError("Unable to list services from Docker runtime") from error

    def _to_snapshot(self, container) -> ServiceSnapshot:
        created_raw = container.attrs.get("Created", "")
        created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00")) if created_raw else datetime.now()

        started_at = None
        state = container.attrs.get("State", {})
        started_raw = state.get("StartedAt", "")
        if started_raw and started_raw != "0001-01-01T00:00:00Z":
            started_at = datetime.fromisoformat(started_raw.replace("Z", "+00:00"))

        ports: Dict[str, List[str]] = {}
        mapped = container.attrs.get("NetworkSettings", {}).get("Ports", {})
        for container_port, host_bindings in (mapped or {}).items():
            if host_bindings:
                ports[container_port] = [f"{binding['HostIp']}:{binding['HostPort']}" for binding in host_bindings]

        return ServiceSnapshot(
            container_id=container.id[:12],
            name=container.name,
            state=container.status,
            image=container.image.tags[0] if container.image.tags else container.image.id[:12],
            created_at=created_at,
            started_at=started_at,
            ports=ports,
            labels=container.labels,
        )

    def fetch_logs(self, service_name: str, lines: int = 100) -> str:
        try:
            container = self.client.containers.get(service_name)
            output = container.logs(tail=lines, timestamps=True)
            return output.decode("utf-8") if output else ""
        except NotFound:
            raise ServiceMissingError(service_name)
        except DockerException as error:
            raise RuntimeUnavailableError(
                f"Unable to retrieve logs for service '{service_name}'"
            ) from error

    def restart_service(self, service_name: str, timeout: int = 10) -> bool:
        try:
            container = self.client.containers.get(service_name)
            container.restart(timeout=timeout)
            container.reload()
            return container.status == "running"
        except NotFound:
            raise ServiceMissingError(service_name)
        except DockerException as error:
            raise RuntimeUnavailableError(
                f"Unable to restart service '{service_name}'"
            ) from error

    def inspect_health(self, service_name: str) -> ServiceHealth:
        try:
            container = self.client.containers.get(service_name)
            container.reload()

            concerns: List[str] = []
            healthy = True
            state = container.status

            if state != "running":
                healthy = False
                concerns.append(f"service state is {state}")

            runtime_state = container.attrs.get("State", {})
            probe = runtime_state.get("Health", {})
            probe_status = probe.get("Status") if probe else None
            if probe_status == "unhealthy":
                healthy = False
                concerns.append("container health probe is unhealthy")

            restart_count = runtime_state.get("RestartCount", 0)
            if restart_count >= RESTART_COUNT_THRESHOLD:
                healthy = False
                concerns.append(f"restart count exceeded threshold ({restart_count})")

            cpu_percent = None
            memory_percent = None

            try:
                stats = container.stats(stream=False)
                cpu_delta = (
                    stats["cpu_stats"]["cpu_usage"]["total_usage"]
                    - stats["precpu_stats"]["cpu_usage"]["total_usage"]
                )
                system_delta = (
                    stats["cpu_stats"]["system_cpu_usage"]
                    - stats["precpu_stats"]["system_cpu_usage"]
                )
                cores = stats["cpu_stats"].get("online_cpus", 1)

                if system_delta > 0:
                    cpu_percent = (cpu_delta / system_delta) * cores * 100.0
                    if cpu_percent > CPU_THRESHOLD_PERCENT:
                        healthy = False
                        concerns.append(f"high cpu usage ({cpu_percent:.1f}%)")

                memory_usage = stats["memory_stats"].get("usage", 0)
                memory_limit = stats["memory_stats"].get("limit", 1)
                memory_percent = (memory_usage / memory_limit) * 100.0
                if memory_percent > MEMORY_THRESHOLD_PERCENT:
                    healthy = False
                    concerns.append(f"high memory usage ({memory_percent:.1f}%)")
            except (KeyError, ZeroDivisionError):
                pass

            return ServiceHealth(
                service_name=container.name,
                healthy=healthy,
                state=state,
                probe_status=probe_status,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                restart_count=restart_count,
                concerns=concerns,
            )
        except NotFound:
            raise ServiceMissingError(service_name)
        except DockerException as error:
            raise RuntimeUnavailableError(
                f"Unable to inspect health for service '{service_name}'"
            ) from error
