"""LLM providers behind one small interface.

- GeminiClient: Google Gemini (text + vision) with JSON-schema output. Default when GEMINI_API_KEY is set.
- OpenAICompatibleClient: any OpenAI-compatible endpoint (Nebius Token Factory, Groq, ...). Text only.
- OfflineLLM: deterministic stand-in so the whole workflow and the tests run with no key and no network.

Agents always pass `context` (the structured inputs) next to the prompt. Real providers ignore it;
OfflineLLM uses it to build a plausible, clearly labelled answer.
"""

from __future__ import annotations

import json
import os
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from . import schemas

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Any provider failure: timeout, quota, invalid JSON, unsupported input."""


class LLM(Protocol):
    name: str

    def generate(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[T],
        context: dict,
        image: bytes | None = None,
        image_mime: str = "image/jpeg",
    ) -> T: ...


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", timeout_s: float = 20.0):
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))
        self.model = model
        self.name = f"gemini:{model}"

    def generate(self, *, system, prompt, schema, context, image=None, image_mime="image/jpeg"):
        types = self._types
        contents: list = [prompt]
        if image is not None:
            contents = [types.Part.from_bytes(data=image, mime_type=image_mime), prompt]
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.2,
                ),
            )
        except Exception as exc:  # network, quota, safety block
            raise LLMError(f"Gemini call failed: {exc}") from exc
        if isinstance(response.parsed, schema):
            return response.parsed
        try:
            return schema.model_validate_json(response.text or "")
        except ValidationError as exc:
            raise LLMError(f"Gemini returned invalid JSON: {exc}") from exc


class OpenAICompatibleClient:
    """For OpenAI-compatible providers such as Nebius Token Factory or Groq. Text only."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float = 20.0):
        import httpx

        self._http = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_s, headers={"Authorization": f"Bearer {api_key}"}
        )
        self.model = model
        self.name = f"openai-compatible:{model}"

    def generate(self, *, system, prompt, schema, context, image=None, image_mime="image/jpeg"):
        if image is not None:
            raise LLMError("This provider is configured for text only; use Gemini for photos.")
        body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"{prompt}\n\nReturn JSON that matches this JSON schema:\n"
                    f"{json.dumps(schema.model_json_schema())}",
                },
            ],
        }
        try:
            response = self._http.post("/chat/completions", json=body)
            response.raise_for_status()
            return schema.model_validate_json(response.json()["choices"][0]["message"]["content"])
        except Exception as exc:
            raise LLMError(f"{self.name} call failed: {exc}") from exc


class OfflineLLM:
    """Deterministic stand-in. It never pretends to understand free text or images:
    text diagnoses come back as low-confidence `unclassified`, photos raise LLMError."""

    name = "offline"

    def __init__(self):
        self.calls: list[str] = []

    def generate(self, *, system, prompt, schema, context, image=None, image_mime="image/jpeg"):
        self.calls.append(schema.__name__)
        handler = getattr(self, f"_{schema.__name__}", None)
        if handler is None:
            raise LLMError(f"OfflineLLM has no handler for {schema.__name__}")
        return handler(context)

    @staticmethod
    def _TextDiagnosis(ctx):
        return schemas.TextDiagnosis(
            correct=False,
            misconception_tag="unclassified",
            error_step=None,
            confidence=0.2,
            feedback_student="Check each step against the worked example.",
        )

    @staticmethod
    def _PhotoDiagnosis(ctx):
        raise LLMError("Offline mode cannot read handwriting. Set GEMINI_API_KEY to diagnose photos.")

    @staticmethod
    def _Lesson(ctx):
        note = (
            ""
            if ctx["language"] == "en"
            else "(Offline mode shows English. Set GEMINI_API_KEY for Hindi or Kannada.)\n\n"
        )
        body = (
            f"{note}**Watch out:** {ctx['definition']}\n\n"
            f"**Do it this way:** {ctx['method']}\n\n"
            "**Tip:** check the denominators before you add, compare, multiply or divide."
        )
        practice = [schemas.PracticeItem(stem=q["stem"], answer=q["answer"]) for q in ctx["practice_seed"]][:3]
        return schemas.Lesson(language="en", lesson_md=body, practice=practice)  # offline text is always English

    @staticmethod
    def _CoachProposal(ctx):
        a = ctx["analysis"]
        revising = bool(ctx.get("critiques"))
        focus = a["focus_concept"]
        tag = (
            a["concepts"][focus]["top_misconceptions"][0][0]
            if a["concepts"][focus]["top_misconceptions"]
            else "unclassified"
        )
        affected = a["concepts"][focus]["affected_by_tag"].get(tag, 0)
        n = a["n_students"]
        example = ctx["worked_example"]
        if not revising:
            recs = [
                schemas.TeacherRecommendation(
                    group_label="Whole class",
                    concept_id=focus,
                    misconception_tag=tag,
                    headline=f"Re-teach {ctx['concept_names'][focus].lower()} to the whole class tomorrow",
                    plan_5min=[
                        "Show one wrong answer from today on the board",
                        "Ask the class what went wrong",
                        "Work the correct method together",
                        "Give 2 quick check questions",
                    ],
                    worked_example=example,
                    why=f"{affected} of {n} students show {tag} on {focus}; class average is {a['concepts'][focus]['avg']:.2f}.",
                )
            ]
        else:
            reteach = a["groups"]["reteach"]
            practice = a["groups"]["practice"]
            recs = [
                schemas.TeacherRecommendation(
                    group_label=f"Group A, {len(reteach)} students",
                    concept_id=focus,
                    misconception_tag=tag,
                    headline=f"Re-teach {ctx['concept_names'][focus].lower()} to Group A only",
                    plan_5min=[
                        "Seat Group A together",
                        "Show today's most common wrong answer",
                        "Work the correct method step by step",
                        "Each student solves one item on paper",
                        "Check answers and close with the one-line rule",
                    ],
                    worked_example=example,
                    why=f"Only {len(reteach)} of {n} are below 0.4 on {focus}; the rest do not need a re-teach.",
                ),
                schemas.TeacherRecommendation(
                    group_label=f"Group B, {len(practice)} students",
                    concept_id=focus,
                    misconception_tag=tag,
                    headline="Group B practises 3 targeted items while Group A is re-taught",
                    plan_5min=[
                        "Hand out 3 practice items",
                        "Pairs check each other's answers",
                        "Teacher checks one pair",
                    ],
                    worked_example=example,
                    why=f"{len(practice)} students are partly there (0.4 to 0.7) and need practice, not a lecture.",
                ),
            ]
        steps = [schemas.StudentNextSteps(student_id=s["student_id"], items=s["items"]) for s in ctx["next_steps_seed"]]
        return schemas.CoachProposal(recommendations=recs, student_next_steps=steps)

    @staticmethod
    def _CritiqueSet(ctx):
        return schemas.CritiqueSet(critiques=[schemas.Critique(**c) for c in ctx["rule_critiques"]])

    @staticmethod
    def _ParentMessage(ctx):
        from .agents.coach import parent_template

        return schemas.ParentMessage(**parent_template(ctx))


def source_of(llm: LLM) -> str:
    """How an LLM-produced output is labelled in the activity feed."""
    return "offline" if llm.name == "offline" else "llm"


def get_llm(offline: bool = False) -> LLM:
    """Pick a provider from the environment. Falls back to OfflineLLM when no key is configured."""
    if offline:
        return OfflineLLM()
    if os.getenv("GEMINI_API_KEY"):
        return GeminiClient(os.environ["GEMINI_API_KEY"], model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    if os.getenv("OPENAI_COMPAT_API_KEY") and os.getenv("OPENAI_COMPAT_BASE_URL"):
        return OpenAICompatibleClient(
            os.environ["OPENAI_COMPAT_BASE_URL"],
            os.environ["OPENAI_COMPAT_API_KEY"],
            os.getenv("OPENAI_COMPAT_MODEL", "meta-llama/Llama-3.3-70B-Instruct"),
        )
    return OfflineLLM()
