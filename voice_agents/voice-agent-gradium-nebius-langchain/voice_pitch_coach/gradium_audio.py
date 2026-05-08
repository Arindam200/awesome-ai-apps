from __future__ import annotations

from pathlib import Path

from gradium import client as gradium_client


class GradiumAudio:
    def __init__(self, api_key: str, base_url: str, voice_id: str) -> None:
        self.client = gradium_client.GradiumClient(base_url=base_url, api_key=api_key)
        self.voice_id = voice_id

    async def transcribe_wav(self, audio_bytes: bytes) -> str:
        result = await self.client.stt({"input_format": "wav"}, audio_bytes)
        return result.text.strip()

    async def speak_to_file(self, text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(await self.speak_bytes(text))
        return output_path

    async def speak_bytes(self, text: str) -> bytes:
        setup = {"output_format": "wav"}
        if self.voice_id:
            setup["voice_id"] = self.voice_id
        result = await self.client.tts(setup, text)
        return result.raw_data
