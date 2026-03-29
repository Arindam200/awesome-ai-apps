import logging

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent
from livekit.plugins import google

load_dotenv(".env.local")
load_dotenv(".env", override=False)

logger = logging.getLogger(__name__)

REALTIME_MODEL = "gemini-3.1-flash-live-preview"
VOICE = "Zephyr"

INSTRUCTIONS = """You are a helpful voice assistant powered by Gemini.
Be concise, friendly, and conversational."""


class VoiceAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=INSTRUCTIONS)

server = AgentServer()

@server.rtc_session(agent_name="gemini-voice-agent")
async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            model=REALTIME_MODEL,
            voice=VOICE,
        )
    )

    await session.start(
        room=ctx.room,
        agent=VoiceAgent(),
    )

if __name__ == "__main__":
    agents.cli.run_app(server)
