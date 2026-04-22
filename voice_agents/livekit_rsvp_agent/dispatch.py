"""Dispatcher: places outbound calls to every pending RSVP.

For each attendee with status "pending" (and under the retry cap), this:
  1. Creates a LiveKit room.
  2. Dispatches the RSVP agent to that room with the attendee_id in metadata.
  3. Creates a SIP participant which dials the attendee's phone number.

Run:

    python dispatch.py            # dial all pending attendees
    python dispatch.py --id A1    # dial just one attendee
"""

import argparse
import asyncio
import json
import os
import uuid

from dotenv import load_dotenv
from livekit import api
from loguru import logger

import tools as db

load_dotenv(override=True)

MAX_ATTEMPTS = 2


async def dial_attendee(lkapi: api.LiveKitAPI, attendee: dict) -> None:
    trunk_id = os.environ["SIP_OUTBOUND_TRUNK_ID"]
    agent_name = os.getenv("AGENT_NAME", "rsvp-agent")
    room_name = f"rsvp-{attendee['id']}-{uuid.uuid4().hex[:6]}"
    metadata = json.dumps({"attendee_id": attendee["id"]})

    logger.info(f"Dialing {attendee['name']} ({attendee['phone']}) in room {room_name}")

    await lkapi.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name=agent_name,
            room=room_name,
            metadata=metadata,
        )
    )

    try:
        await lkapi.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=trunk_id,
                sip_call_to=attendee["phone"],
                room_name=room_name,
                participant_identity=f"caller-{attendee['id']}",
                participant_name=attendee["name"],
                participant_metadata=metadata,
                krisp_enabled=True,
                wait_until_answered=True,
            )
        )
    except Exception as e:
        logger.error(f"SIP call to {attendee['name']} failed: {e}")
        attempts = attendee.get("attempts", 0) + 1
        if attempts >= MAX_ATTEMPTS:
            db.update_attendee(attendee["id"], status="no_answer", attempts=attempts)
            logger.warning(f"Marked {attendee['name']} as no_answer after {attempts} attempts")
        else:
            db.update_attendee(attendee["id"], attempts=attempts)


async def main(only_id: str | None = None) -> None:
    if only_id:
        attendee = db.get_attendee(only_id)
        if not attendee:
            logger.error(f"Attendee {only_id} not found")
            return
        targets = [attendee]
    else:
        targets = [
            a for a in db.list_attendees()
            if a["status"] == "pending" and a.get("attempts", 0) < MAX_ATTEMPTS
        ]

    if not targets:
        logger.info("No attendees to dial.")
        return

    lkapi = api.LiveKitAPI()
    try:
        for attendee in targets:
            await dial_attendee(lkapi, attendee)
            await asyncio.sleep(1)  # gentle pacing
    finally:
        await lkapi.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dispatch RSVP confirmation calls.")
    parser.add_argument("--id", help="Dial only this attendee id (e.g., A1).")
    args = parser.parse_args()
    asyncio.run(main(only_id=args.id))
