"""Dependency-free client for the MiniMax synchronous text-to-speech API."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ENDPOINTS = {
    "global_en": "https://api.minimax.io/v1/t2a_v2",
    "cn_zh": "https://api.minimaxi.com/v1/t2a_v2",
}
MODELS = (
    "speech-2.8-hd",
    "speech-2.8-turbo",
    "speech-2.6-hd",
    "speech-2.6-turbo",
    "speech-02-hd",
    "speech-02-turbo",
    "speech-01-hd",
    "speech-01-turbo",
)
AUDIO_FORMATS = ("mp3", "wav", "flac", "pcm")
OUTPUT_FORMATS = ("hex", "url")
DEFAULT_MODEL = "speech-2.8-hd"

Transport = Callable[[str, Mapping[str, str], bytes, float], bytes]


class MiniMaxSpeechError(RuntimeError):
    """Raised when a speech request or response is invalid."""


@dataclass(frozen=True)
class SpeechResult:
    """Decoded audio or a temporary audio URL returned by the service."""

    status: int
    audio: bytes | None = None
    url: str | None = None


def _urllib_transport(
    endpoint: str, headers: Mapping[str, str], body: bytes, timeout: float
) -> bytes:
    request = Request(endpoint, data=body, headers=dict(headers), method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as exc:
        message = f"Speech request failed with HTTP {exc.code}."
        raise MiniMaxSpeechError(message) from exc
    except URLError as exc:
        raise MiniMaxSpeechError("Speech request could not reach the API.") from exc


class MiniMaxSpeechClient:
    """Create speech with either the global or China regional endpoint."""

    def __init__(
        self,
        api_key: str,
        *,
        region: str = "global_en",
        timeout: float = 60,
        transport: Transport = _urllib_transport,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        if region not in ENDPOINTS:
            raise ValueError(f"region must be one of: {', '.join(ENDPOINTS)}")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self.api_key = api_key
        self.endpoint = ENDPOINTS[region]
        self.timeout = timeout
        self.transport = transport

    def synthesize(
        self,
        text: str,
        *,
        model: str = DEFAULT_MODEL,
        output_format: str = "hex",
        language_boost: str | None = None,
        voice_setting: Mapping[str, Any] | None = None,
        pronunciation_dict: Mapping[str, Any] | None = None,
        audio_setting: Mapping[str, Any] | None = None,
        voice_modify: Mapping[str, Any] | None = None,
        subtitle_enable: bool | None = None,
    ) -> SpeechResult:
        """Synthesize text and parse the API's audio response."""

        if not text.strip():
            raise ValueError("text must not be empty")
        if model not in MODELS:
            raise ValueError(f"model must be one of: {', '.join(MODELS)}")
        if output_format not in OUTPUT_FORMATS:
            options = ", ".join(OUTPUT_FORMATS)
            raise ValueError(f"output_format must be one of: {options}")

        settings = dict(audio_setting or {})
        audio_format = settings.get("format", "mp3")
        if audio_format not in AUDIO_FORMATS:
            raise ValueError(f"audio format must be one of: {', '.join(AUDIO_FORMATS)}")
        settings["format"] = audio_format

        payload: dict[str, Any] = {
            "model": model,
            "text": text,
            "stream": False,
            "output_format": output_format,
            "audio_setting": settings,
        }
        optional_fields = {
            "language_boost": language_boost,
            "voice_setting": voice_setting,
            "pronunciation_dict": pronunciation_dict,
            "voice_modify": voice_modify,
            "subtitle_enable": subtitle_enable,
        }
        payload.update(
            {key: value for key, value in optional_fields.items() if value is not None}
        )

        raw_response = self.transport(
            self.endpoint,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json.dumps(payload).encode("utf-8"),
            self.timeout,
        )
        return self._parse_response(raw_response, output_format)

    @staticmethod
    def _parse_response(raw_response: bytes, output_format: str) -> SpeechResult:
        try:
            response = json.loads(raw_response)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MiniMaxSpeechError("Speech response was not valid JSON.") from exc

        base_response = response.get("base_resp")
        if not isinstance(base_response, dict) or base_response.get("status_code") != 0:
            message = (
                base_response.get("status_msg", "unknown API error")
                if isinstance(base_response, dict)
                else "missing base_resp"
            )
            raise MiniMaxSpeechError(f"Speech API rejected the request: {message}.")

        data = response.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("audio"), str):
            raise MiniMaxSpeechError("Speech response did not include data.audio.")

        status = data.get("status")
        if not isinstance(status, int):
            raise MiniMaxSpeechError("Speech response did not include data.status.")

        audio_value = data["audio"]
        if output_format == "url":
            parsed_url = urlparse(audio_value)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                message = "Speech response included an invalid audio URL."
                raise MiniMaxSpeechError(message)
            return SpeechResult(status=status, url=audio_value)

        try:
            audio = bytes.fromhex(audio_value)
        except ValueError as exc:
            message = "Speech response included invalid hex audio."
            raise MiniMaxSpeechError(message) from exc
        return SpeechResult(status=status, audio=audio)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create speech with MiniMax.")
    parser.add_argument("text", help="Text to synthesize.")
    parser.add_argument("--output", type=Path, default=Path("speech.mp3"))
    parser.add_argument(
        "--region",
        choices=ENDPOINTS,
        default=os.getenv("MINIMAX_REGION", "global_en"),
    )
    parser.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)
    parser.add_argument("--voice-id", default=os.getenv("MINIMAX_VOICE_ID"))
    parser.add_argument("--language-boost", default="auto")
    parser.add_argument("--audio-format", choices=AUDIO_FORMATS, default="mp3")
    parser.add_argument("--sample-rate", type=int, default=32000)
    parser.add_argument("--bitrate", type=int, default=128000)
    parser.add_argument("--channel", type=int, choices=(1, 2), default=1)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    api_key = os.getenv("MINIMAX_API_KEY", "")
    if not api_key:
        raise SystemExit("MINIMAX_API_KEY is required.")

    voice_setting = {"voice_id": args.voice_id} if args.voice_id else None
    result = MiniMaxSpeechClient(api_key, region=args.region).synthesize(
        args.text,
        model=args.model,
        language_boost=args.language_boost,
        voice_setting=voice_setting,
        audio_setting={
            "format": args.audio_format,
            "sample_rate": args.sample_rate,
            "bitrate": args.bitrate,
            "channel": args.channel,
        },
    )
    if result.audio is None:
        message = "The command-line tool expected an inline audio response."
        raise MiniMaxSpeechError(message)
    args.output.write_bytes(result.audio)
    print(f"Audio written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
