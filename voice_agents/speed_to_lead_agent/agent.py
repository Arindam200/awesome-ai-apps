"""Speed-to-lead voice agent.

Multi-agent handoff pattern:
    Router -> Qualifier (quote | schedule | emergency) -> CRM log on completion.

Pipeline: LiveKit WebRTC/SIP -> Deepgram STT -> Nebius LLM -> Cartesia TTS.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, JobContext, RunContext, function_tool
from livekit.plugins import cartesia, deepgram, openai, silero

from crm import log_lead

load_dotenv()
logger = logging.getLogger("speed-to-lead")


@dataclass
class LeadData:
    """Shared state across agent handoffs."""

    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    intent: Optional[str] = None  # quote | schedule | emergency
    problem: Optional[str] = None
    severity: Optional[str] = None  # low | medium | high
    source_form: dict = field(default_factory=dict)


# ---------- Qualifier agents ----------

class QuoteAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You collect quote requests. Ask for: service address, nature of the "
                "job, and rough scope. Keep it under 4 short questions. When you have "
                "enough, call finalize_lead."
            )
        )


class ScheduleAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You schedule service visits. Ask for: service address, problem "
                "description, and preferred day/time window. Keep it brief. When done, "
                "call finalize_lead."
            )
        )


class EmergencyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "This is an emergency intake. Stay calm and brief. Confirm: address, "
                "what is happening right now, and whether anyone is in danger. Then "
                "call finalize_lead with severity='high' immediately."
            )
        )


# ---------- Router ----------

class RouterAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are the first voice the caller hears after they submitted a form. "
                "Introduce yourself in one sentence, confirm their name, then ask what "
                "they need. Classify their intent as quote, schedule, or emergency, "
                "and call route_to_specialist. Do NOT try to qualify the lead yourself."
            )
        )

    @function_tool
    async def route_to_specialist(
        self,
        ctx: RunContext[LeadData],
        intent: str,
        caller_name: Optional[str] = None,
    ) -> Agent:
        """Route to the correct qualifier. intent must be quote, schedule, or emergency."""
        intent = intent.lower().strip()
        if caller_name:
            ctx.userdata.name = caller_name
        ctx.userdata.intent = intent

        logger.info("Routing to %s", intent)
        if intent == "emergency":
            return EmergencyAgent()
        if intent == "schedule":
            return ScheduleAgent()
        return QuoteAgent()


# ---------- Shared tool: finalize ----------

@function_tool
async def finalize_lead(
    ctx: RunContext[LeadData],
    address: str,
    problem: str,
    severity: str = "medium",
) -> str:
    """Log the qualified lead to the CRM and end the call politely."""
    data = ctx.userdata
    data.address = address
    data.problem = problem
    data.severity = severity

    result = log_lead(
        {
            "name": data.name,
            "phone": data.phone,
            "intent": data.intent,
            "address": address,
            "problem": problem,
            "severity": severity,
            "source_form": data.source_form,
        }
    )
    logger.info("Lead logged: %s", result)
    return (
        "Lead saved. Thank the caller, confirm a human will reach out shortly, "
        "and end the call."
    )


# Register the shared tool on qualifier classes.
for _cls in (QuoteAgent, ScheduleAgent, EmergencyAgent):
    _cls.finalize_lead = finalize_lead


# ---------- Entrypoint ----------

async def entrypoint(ctx: JobContext):
    await ctx.connect()

    # Form payload is passed via job metadata from dispatch.py.
    form = {}
    if ctx.job.metadata:
        try:
            form = json.loads(ctx.job.metadata)
        except json.JSONDecodeError:
            logger.warning("Bad job metadata; ignoring")

    userdata = LeadData(
        name=form.get("name"),
        phone=form.get("phone"),
        source_form=form,
    )

    session = AgentSession[LeadData](
        userdata=userdata,
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM.with_nebius(model="meta-llama/Meta-Llama-3.1-70B-Instruct"),
        tts=cartesia.TTS(),
    )

    await session.start(room=ctx.room, agent=RouterAgent())

    greeting = (
        f"Hi {userdata.name}, this is Aria calling about the form you just submitted. "
        "Do you have a quick minute?"
        if userdata.name
        else "Hi, this is Aria calling about the request you just submitted. "
        "Do you have a quick minute?"
    )
    await session.generate_reply(instructions=f"Say exactly: {greeting}")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint, agent_name="speed-to-lead")
    )
