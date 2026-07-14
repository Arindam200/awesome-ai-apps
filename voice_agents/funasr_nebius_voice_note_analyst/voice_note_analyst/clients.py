import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from openai import OpenAI
from pydantic import ValidationError

from voice_note_analyst.models import TranscriptionResult, VoiceNoteBrief


BRIEF_SYSTEM_PROMPT = """You turn a voice-note transcript into a concise structured brief.
Write every output field in the same language as the transcript.
Do not invent an owner or due date. Use null when either value is not explicit.
Return exactly one JSON object with these fields:
- summary: string
- key_points: array of strings
- action_items: array of objects with task, owner, and due fields
- follow_up_message: string
Do not include Markdown or commentary outside the JSON object."""


class ProviderError(RuntimeError):
    pass


def build_transcriptions_url(base_url: str) -> str:
    cleaned = base_url.strip().rstrip("/")
    try:
        parsed = urlsplit(cleaned)
        parsed.port
    except ValueError as exc:
        raise ValueError("FunASR base URL must be an absolute HTTP(S) URL.") from exc

    unsafe_authority = (
        parsed.username is not None
        or parsed.password is not None
        or any(character.isspace() for character in parsed.netloc)
    )
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or unsafe_authority:
        raise ValueError("FunASR base URL must be an absolute HTTP(S) URL without credentials.")
    if parsed.query or parsed.fragment:
        raise ValueError("FunASR base URL must not contain a query string or fragment.")

    path = parsed.path.rstrip("/")
    if path.endswith("/audio/transcriptions"):
        endpoint_path = path
    elif path.endswith("/v1"):
        endpoint_path = f"{path}/audio/transcriptions"
    else:
        endpoint_path = f"{path}/v1/audio/transcriptions"
    return urlunsplit((parsed.scheme, parsed.netloc, endpoint_path, "", ""))


class FunASRClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 120,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        cleaned_model = model.strip()
        if not cleaned_model:
            raise ValueError("FunASR model must not be empty.")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("FunASR timeout must be a finite number greater than zero.")

        self.endpoint = build_transcriptions_url(base_url)
        self.model = cleaned_model
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self._client = httpx.Client(timeout=timeout_seconds, transport=transport)

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        language: str | None = None,
    ) -> TranscriptionResult:
        if not audio_bytes:
            raise ValueError("Audio is empty.")

        data = {"model": self.model, "response_format": "verbose_json"}
        cleaned_language = language.strip() if language else None
        if cleaned_language and cleaned_language.lower() != "auto":
            data["language"] = cleaned_language
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else None
        safe_filename = Path(filename.replace("\\", "/")).name or "audio.wav"

        try:
            response = self._client.post(
                self.endpoint,
                data=data,
                files={
                    "file": (
                        safe_filename,
                        audio_bytes,
                        _audio_content_type(safe_filename),
                    )
                },
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise ProviderError("FunASR transcription timed out.") from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"Could not reach FunASR at {self.endpoint}.") from exc

        if not response.is_success:
            raise ProviderError(_http_error("FunASR", response, secrets=(self.api_key,)))
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("FunASR returned invalid JSON.") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
            raise ProviderError("FunASR response is missing the string field 'text'.")

        text = payload["text"].strip()
        if not text:
            raise ProviderError("FunASR returned an empty transcript.")
        language_value = payload.get("language")
        detected = language_value.strip() if isinstance(language_value, str) else None
        if not detected or detected.lower() == "auto":
            detected = None
        return TranscriptionResult(text=text, language=detected)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "FunASRClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class NebiusBriefClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: float = 60,
        client: Any | None = None,
    ) -> None:
        cleaned_model = model.strip()
        if not cleaned_model:
            raise ValueError("Nebius model must not be empty.")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Nebius timeout must be a finite number greater than zero.")

        if client is None:
            cleaned_key = api_key.strip() if api_key else ""
            if not cleaned_key:
                raise ValueError("NEBIUS_API_KEY is required to generate a brief.")
            client = OpenAI(
                api_key=cleaned_key,
                base_url=base_url,
                timeout=timeout_seconds,
            )
        self._client = client
        self.model = cleaned_model

    def create_brief(self, transcript: str) -> VoiceNoteBrief:
        cleaned = transcript.strip()
        if not cleaned:
            raise ValueError("Transcript is empty.")

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                max_tokens=1200,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": BRIEF_SYSTEM_PROMPT},
                    {"role": "user", "content": cleaned},
                ],
            )
        except Exception as exc:
            raise ProviderError("Nebius could not generate the voice-note brief.") from exc

        choices = getattr(response, "choices", None)
        if not choices:
            raise ProviderError("Nebius returned an empty response.")
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Nebius returned an empty response.")

        try:
            return VoiceNoteBrief.model_validate_json(_extract_json(content))
        except (ValueError, ValidationError) as exc:
            raise ProviderError("Nebius returned a brief with an invalid JSON shape.") from exc


def _audio_content_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return {
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
    }.get(suffix, "application/octet-stream")


def _extract_json(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) < 3 or lines[0].lower() not in {"```", "```json"} or lines[-1] != "```":
            raise ValueError("Response must contain one complete JSON object.")
        cleaned = "\n".join(lines[1:-1]).strip()
    if not cleaned.startswith("{") or not cleaned.endswith("}"):
        raise ValueError("Response must contain one complete JSON object.")
    return cleaned


def _http_error(
    provider: str,
    response: httpx.Response,
    *,
    secrets: tuple[str | None, ...] = (),
) -> str:
    detail = re.sub(r"\s+", " ", response.text).strip()
    for secret in secrets:
        if secret:
            detail = detail.replace(secret, "[redacted]")
    detail = detail[:1_000] or response.reason_phrase or "Request failed."
    return f"{provider} returned HTTP {response.status_code}: {detail}"
