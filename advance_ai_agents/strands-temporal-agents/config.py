import os

# Core configuration
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TASK_QUEUE = "strands-temporal-agent-queue"

# LiteLLM + Nebius configuration
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")
NEBIUS_MODEL_ID = os.getenv("NEBIUS_MODEL_ID", "nebius/deepseek-ai/DeepSeek-V3-0324")

# Docker configuration
DOCKER_HOST = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "30"))

# Docker Monitor Task Queue
DOCKER_MONITOR_TASK_QUEUE = "docker-monitor-queue"

# Operation timeouts (seconds)
STATUS_CHECK_TIMEOUT = 10
HEALTH_CHECK_TIMEOUT = 15
LOG_RETRIEVAL_TIMEOUT = 10
RESTART_TIMEOUT = 30
AI_ORCHESTRATOR_TIMEOUT = 15

# Resource thresholds for health checks
CPU_THRESHOLD_PERCENT = 90.0
MEMORY_THRESHOLD_PERCENT = 90.0
RESTART_COUNT_THRESHOLD = 5

# Timeouts (legacy - for existing agents)
WEATHER_TIMEOUT = 15
