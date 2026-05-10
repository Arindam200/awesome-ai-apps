from __future__ import annotations

import asyncio
import base64
from functools import lru_cache
import logging
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from voice_pitch_coach.coach import NebiusPitchCoach
from voice_pitch_coach.gradium_audio import GradiumAudio
from voice_pitch_coach.settings import load_settings


ROOT = Path(__file__).parent
MAX_AUDIO_UPLOAD_BYTES = 15 * 1024 * 1024
logger = logging.getLogger(__name__)

app = FastAPI(title="PitchLoop Voice Agent")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@lru_cache(maxsize=1)
def get_clients() -> tuple[GradiumAudio, NebiusPitchCoach]:
    settings = load_settings()
    return (
        GradiumAudio(
            api_key=settings.gradium_api_key,
            base_url=settings.gradium_base_url,
            voice_id=settings.gradium_voice_id,
        ),
        NebiusPitchCoach(api_key=settings.nebius_api_key, model=settings.nebius_model),
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/turn")
async def voice_turn(
    request: Request,
    audio: Annotated[UploadFile, File()],
    scenario: Annotated[str, Form()] = "startup pitch",
    audience: Annotated[str, Form()] = "early-stage investors",
    goal: Annotated[str, Form()] = "earn a follow-up meeting",
    previous_question: Annotated[str, Form()] = "Give me your 45-second opening pitch.",
) -> dict:
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio upload is too large.")

    audio_bytes = await read_limited_upload(audio, MAX_AUDIO_UPLOAD_BYTES)
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="No audio was uploaded.")

    try:
        gradium_audio, coach = get_clients()
        transcript = await gradium_audio.transcribe_wav(audio_bytes)
        if not transcript:
            raise RuntimeError("Gradium returned an empty transcript.")

        result = await asyncio.to_thread(
            coach.analyze,
            transcript=transcript,
            scenario=scenario,
            audience=audience,
            goal=goal,
            previous_question=previous_question,
        )

        spoken_reply = f"{result.spoken_feedback} {result.next_question}"
        reply_audio = await gradium_audio.speak_bytes(spoken_reply)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Voice turn failed")
        raise HTTPException(status_code=500, detail="Voice turn failed. Please try again.") from exc

    return {
        "transcript": transcript,
        "coach": result.model_dump(),
        "spoken_reply": spoken_reply,
        "audio_base64": base64.b64encode(reply_audio).decode("ascii"),
        "audio_content_type": "audio/wav",
    }


async def read_limited_upload(upload: UploadFile, max_bytes: int) -> bytes:
    chunks = []
    total = 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="Audio upload is too large.")
        chunks.append(chunk)
    return b"".join(chunks)
