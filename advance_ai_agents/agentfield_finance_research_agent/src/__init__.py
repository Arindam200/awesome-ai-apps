"""
Argus — Autonomous Research Agent
Exports the shared `app` Agent instance used across all modules.

Authentication is handled automatically via environment variables:
  NEBIUS_API_KEY  — used by AgentField/LiteLLM for all app.ai() calls
"""
from agentfield import Agent, AIConfig
from dotenv import load_dotenv

load_dotenv()

app = Agent(
    node_id="argus-research-agent",
    # LiteLLM requires the provider prefix for Nebius Token Factory
    ai_config=AIConfig(model="nebius/openai/gpt-oss-120b"),
    # Disable cloud hub connection — we run fully local, no AgentField cloud needed.
    # Without this, AgentField endlessly retries WebSocket to localhost:8080 (HTTP 403).
    agentfield_server="",
)
