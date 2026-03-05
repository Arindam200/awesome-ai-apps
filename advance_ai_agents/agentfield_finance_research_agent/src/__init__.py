"""
Argus — Autonomous Research Agent
Exports the shared `app` Agent instance used across all modules.

Authentication is handled automatically via environment variables:
  NEBIUS_API_KEY       — used by AgentField/LiteLLM for all app.ai() calls
  AGENTFIELD_SERVER    — control plane URL (default: http://localhost:8080)
"""
import os

from agentfield import Agent, AIConfig
from dotenv import load_dotenv

load_dotenv()

app = Agent(
    node_id="argus-research-agent",
    # LiteLLM requires the provider prefix for Nebius Token Factory
    ai_config=AIConfig(model="nebius/openai/gpt-oss-120b"),
    # Connect to the AgentField control plane for dashboard visibility at /ui
    agentfield_server=os.getenv("AGENTFIELD_SERVER", "http://localhost:8080"),
    # dev_mode=True,
)
