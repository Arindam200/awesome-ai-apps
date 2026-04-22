"""Outbound RSVP confirmation agent.

Reads `attendee_id` from the SIP participant's job metadata, looks up the
attendee record, and runs a short scripted conversation to confirm whether
they are still attending. Updates the JSON DB via tool calls.

Run as a LiveKit agent worker:

    python agent.py dev
"""

import json
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import cartesia, deepgram, openai, silero
from loguru import logger

import tools as db

load_dotenv(override=True)

CARTESIA_VOICE = "71a7ad14-091c-4e8e-a314-022ece01c121"  # warm female


@dataclass
class CallState:
    attendee_id: str
    attendee: dict[str, Any]
    event: dict[str, Any]


class RSVPAgent(Agent):
    def __init__(self, state: CallState) -> None:
        self.state = state
        event = state.event
        attendee = state.attendee
        guests_line = (
            f"They originally said they would bring {attendee['guests']} guest(s)."
            if attendee.get("guests")
            else "They are RSVPed solo."
        )

        instructions = f"""You are Aria, a friendly assistant calling on behalf of {event['host']}
to confirm RSVPs for an upcoming event.

The person you are calling:
- Name: {attendee['name']}
- RSVP id: {attendee['id']}
- {guests_line}

The event:
- {event['name']} on {event['date']} at {event['time']}
- Venue: {event['venue']}

Your job, in 3 to 4 short turns:
1. Greet them by first name and identify yourself and the event by name and date.
2. Ask if they are still planning to attend.
3. If yes, confirm the guest count and call `confirm_attendance`.
   If no, ask briefly for a reason (optional) and call `decline_attendance`.
   If unsure, call `mark_maybe`.
4. Thank them warmly and call `end_call`.

Style:
- One short sentence at a time. Conversational, not scripted.
- Never mention internal IDs out loud.
- If they sound confused or it's clearly voicemail (long silence after greeting),
  leave a brief 10-second message and call `end_call`.
"""
        super().__init__(instructions=instructions)

    @function_tool()
    async def confirm_attendance(
        self,
        context: RunContext,
        guests_count: int,
    ) -> dict[str, Any]:
        """Mark the attendee as confirmed.

        Args:
            guests_count: Number of additional guests they will bring (0 if solo).
        """
        updated = db.update_attendee(
            self.state.attendee_id,
            status="confirmed",
            guests=guests_count,
        )
        logger.info(f"Confirmed {updated['name']} (+{guests_count})")
        return {"status": "confirmed", "guests": guests_count}

    @function_tool()
    async def decline_attendance(
        self,
        context: RunContext,
        reason: str = "",
    ) -> dict[str, Any]:
        """Mark the attendee as not attending.

        Args:
            reason: Optional short reason they gave for declining.
        """
        updated = db.update_attendee(
            self.state.attendee_id,
            status="declined",
            notes=reason,
        )
        logger.info(f"Declined {updated['name']}: {reason!r}")
        return {"status": "declined"}

    @function_tool()
    async def mark_maybe(
        self,
        context: RunContext,
        follow_up_note: str = "",
    ) -> dict[str, Any]:
        """Mark the attendee as undecided; we'll follow up later.

        Args:
            follow_up_note: Short note about why they are unsure.
        """
        updated = db.update_attendee(
            self.state.attendee_id,
            status="maybe",
            notes=follow_up_note,
        )
        logger.info(f"Marked maybe for {updated['name']}: {follow_up_note!r}")
        return {"status": "maybe"}

    @function_tool()
    async def end_call(self, context: RunContext) -> dict[str, str]:
        """End the call after the RSVP is recorded or voicemail is left."""
        logger.info(f"Ending call with {self.state.attendee['name']}")
        await context.session.aclose()
        return {"status": "ended"}


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    metadata: dict[str, Any] = {}
    if ctx.job.metadata:
        try:
            metadata = json.loads(ctx.job.metadata)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse job metadata: {ctx.job.metadata!r}")

    attendee_id = metadata.get("attendee_id")
    if not attendee_id:
        logger.error("No attendee_id in job metadata; aborting")
        return

    attendee = db.get_attendee(attendee_id)
    if not attendee:
        logger.error(f"Unknown attendee_id={attendee_id}; aborting")
        return

    db.increment_attempts(attendee_id)
    state = CallState(attendee_id=attendee_id, attendee=attendee, event=db.get_event())

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="en"),
        llm=openai.LLM.with_nebius(
            model="meta-llama/Meta-Llama-3.1-70B-Instruct",
            api_key=os.getenv("NEBIUS_API_KEY"),
        ),
        tts=cartesia.TTS(voice=CARTESIA_VOICE),
        vad=silero.VAD.load(),
    )

    await session.start(room=ctx.room, agent=RSVPAgent(state))

    # Kick off the conversation; the agent's instructions tell it how to greet.
    await session.generate_reply(
        instructions=f"Greet {attendee['name'].split()[0]} and start the RSVP confirmation."
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=os.getenv("AGENT_NAME", "rsvp-agent"),
        )
    )
