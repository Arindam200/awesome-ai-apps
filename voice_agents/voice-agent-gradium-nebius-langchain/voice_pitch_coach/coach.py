from __future__ import annotations

import json
import re

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .schemas import CoachTurn


SYSTEM_PROMPT = """You are a practical voice coach for founders, builders, and technical speakers.
The product is a voice agent called PitchLoop. It helps a user practice high-stakes spoken moments:
startup pitches, job interviews, demo intros, sales discovery, and public speaking.

Coach style:
- Be direct, warm, and specific.
- Score the performance, but make the next action obvious.
- Prefer crisp rewrites that sound natural when spoken aloud.
- Ask exactly one follow-up question that keeps the practice conversation moving.
- Do not invent claims that the speaker did not make.

Return only JSON matching this schema:
{
  "mode": "pitch" | "interview" | "storytelling" | "sales",
  "overall_score": 0-100,
  "scores": {
    "clarity": 0-100,
    "structure": 0-100,
    "confidence": 0-100,
    "concision": 0-100,
    "audience_fit": 0-100
  },
  "transcript_summary": "one sentence",
  "strengths": ["specific strength", "specific strength"],
  "improvements": ["specific improvement", "specific improvement", "specific improvement"],
  "suggested_rewrite": "a tighter spoken version of the user's answer",
  "spoken_feedback": "2-3 concise sentences to be read aloud by TTS",
  "next_question": "one follow-up question",
  "practice_drill": "one short drill the user can do now"
}
Keep the JSON compact. Use short strings and no extra keys.
"""

USER_PROMPT = """Scenario: {scenario}
Audience: {audience}
Goal: {goal}
Previous coach question: {previous_question}
User transcript:
{transcript}

Analyze this turn and continue the voice-coaching conversation."""


class NebiusPitchCoach:
    def __init__(self, api_key: str, model: str) -> None:
        # Nebius exposes an OpenAI-compatible API, so ChatOpenAI keeps the
        # LangChain prompt/model flow while targeting Nebius.
        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url="https://api.studio.nebius.ai/v1/",
            model=model,
            temperature=0.2,
            top_p=0.95,
            max_tokens=4096,
        ).bind(response_format={"type": "json_object"})
        self.prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                ("user", USER_PROMPT),
            ]
        )

    def analyze(
        self,
        *,
        transcript: str,
        scenario: str,
        audience: str,
        goal: str,
        previous_question: str,
    ) -> CoachTurn:
        messages = self.prompt.format_messages(
            transcript=transcript,
            scenario=scenario,
            audience=audience,
            goal=goal,
            previous_question=previous_question or "Start with the user's opening answer.",
        )
        response = self.llm.invoke(messages)
        content = response.content if isinstance(response.content, str) else json.dumps(response.content)
        return CoachTurn.model_validate_json(_extract_json(content))


def _extract_json(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Nebius response did not include a JSON object: {cleaned[:300]}")
    return match.group(0)
