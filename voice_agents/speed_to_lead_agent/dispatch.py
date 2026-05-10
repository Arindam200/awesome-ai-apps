"""Form webhook -> LiveKit agent dispatch.

POST /submit with JSON {name, phone, email?, message?} creates a LiveKit room,
dispatches the speed-to-lead agent into it, and returns a join token so a
browser client (or SIP bridge) can connect the caller within 60 seconds.
"""

import json
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI
from livekit import api
from pydantic import BaseModel

load_dotenv()

LIVEKIT_URL = os.environ["LIVEKIT_URL"]
LIVEKIT_API_KEY = os.environ["LIVEKIT_API_KEY"]
LIVEKIT_API_SECRET = os.environ["LIVEKIT_API_SECRET"]
AGENT_NAME = "speed-to-lead"

app = FastAPI()


class FormSubmission(BaseModel):
    name: str
    phone: str
    email: str | None = None
    message: str | None = None


@app.post("/submit")
async def submit(form: FormSubmission):
    room_name = f"lead-{uuid.uuid4().hex[:8]}"
    metadata = json.dumps(form.model_dump())

    lkapi = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME, room=room_name, metadata=metadata
            )
        )
    finally:
        await lkapi.aclose()

    caller_token = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(f"caller-{form.phone}")
        .with_name(form.name)
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )

    return {"room": room_name, "token": caller_token, "url": LIVEKIT_URL}
