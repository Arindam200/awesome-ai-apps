"""Final customer support voice agent: prompt + handoff + inactivity handling."""

import asyncio
import os

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    TurnHandlingOptions,
    UserStateChangedEvent,
    cli,
    function_tool,
    inference,
    room_io,
)
from livekit.plugins import noise_cancellation, openai, silero

load_dotenv()


SUPPORT_PROMPT = """
You are Maya, a friendly customer support agent.

Your job:
- Understand the customer's problem.
- Give clear and accurate answers.
- Ask one question at a time.
- Keep responses short because this is a voice conversation.
- Never make up information. If you do not know, say so.
- Never ask for passwords, OTPs, or full card details.
- If the customer asks for a manager, call transfer_to_manager.
- If you cannot solve the issue after two attempts, offer a manager transfer.
"""


class CustomerSupportAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            llm=openai.LLM.with_nebius(
                model=os.getenv("LLM_MODEL", "MiniMaxAI/MiniMax-M3"),
                api_key=os.getenv("NEBIUS_API_KEY"),
            ),
            instructions=SUPPORT_PROMPT,
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Introduce yourself as Maya from customer support, then ask how "
                "you can help. Keep it to one short sentence."
            )
        )

    @function_tool()
    async def transfer_to_manager(self) -> Agent:
        """Transfer when the customer asks for a manager or needs escalation."""
        return ManagerAgent(chat_ctx=self.chat_ctx)


class ManagerAgent(Agent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            llm=openai.LLM.with_nebius(
                model=os.getenv("LLM_MODEL", "MiniMaxAI/MiniMax-M3"),
                api_key=os.getenv("NEBIUS_API_KEY"),
            ),
            instructions="""
                You are Olivia, a senior customer support manager.

                - Continue from the existing conversation. Do not ask the customer to repeat it.
                - First acknowledge the unresolved issue.
                - Ask one question at a time and keep replies short.
                - Never promise a refund, credit, or action you cannot actually perform.
                - If the issue needs a human follow-up, explain that clearly.
            """,
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Introduce yourself as Olivia, the support manager. Briefly acknowledge "
                "the issue using the conversation so far, then ask how you can help."
            )
        )


server = AgentServer()


@server.rtc_session(agent_name="customer-support-agent")
async def agent_server(ctx: JobContext) -> None:
    session = AgentSession(
        stt=inference.STT(model="cartesia/ink-whisper", language="en"),
        tts=inference.TTS(
            model="cartesia/sonic-3",
            voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
            language="en",
        ),
        turn_handling=TurnHandlingOptions(
            preemptive_generation={"enabled": False},
            turn_detection=inference.TurnDetector(),
        ),
        user_away_timeout=12.5,
        vad=silero.VAD.load(),
    )

    # This task belongs to this call only. It is not shared across customers.
    inactivity_task: asyncio.Task | None = None

    async def check_inactivity() -> None:
        for _ in range(2):
            await session.generate_reply(
                instructions="Ask the customer briefly if they are still there."
            )
            await asyncio.sleep(10)

        await session.generate_reply(
            instructions="Say goodbye because the line has been inactive."
        )
        await session.shutdown()

    @session.on("user_state_changed")
    def on_user_state_changed(event: UserStateChangedEvent) -> None:
        nonlocal inactivity_task

        if event.new_state == "away":
            inactivity_task = asyncio.create_task(check_inactivity())
        elif inactivity_task is not None:
            inactivity_task.cancel()
            inactivity_task = None

    await session.start(
        agent=CustomerSupportAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC()
            )
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
