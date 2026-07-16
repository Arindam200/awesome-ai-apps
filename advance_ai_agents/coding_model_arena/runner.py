"""Sends a challenge prompt to a Nebius Token Factory model and extracts the
single code block it returns.
"""

import re
import time
from dataclasses import dataclass

from openai import OpenAI

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1"

SYSTEM_PROMPT = (
    "You are a competitive programmer. Respond with ONLY a single Python code "
    "block implementing exactly the requested signature. No explanations, no "
    "tests, no extra prose before or after the code block."
)

CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)
INITIAL_COMPLETION_BUDGET = 6000
RETRY_COMPLETION_BUDGET = 10000


@dataclass
class GenerationResult:
    model_id: str
    code: str
    raw_response: str
    latency_seconds: float
    error: str | None = None
    finish_reason: str | None = None
    attempts: int = 1


def _extract_code(text: str) -> str:
    match = CODE_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def generate_solution(client: OpenAI, model_id: str, prompt: str) -> GenerationResult:
    start = time.perf_counter()
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        last_raw = ""
        last_finish_reason = "unknown"
        for attempt, budget in enumerate(
            (INITIAL_COMPLETION_BUDGET, RETRY_COMPLETION_BUDGET), start=1
        ):
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=0.2,
                max_completion_tokens=budget,
                reasoning_effort="low",
            )
            choice = response.choices[0]
            last_raw = choice.message.content or ""
            last_finish_reason = choice.finish_reason or "unknown"
            code = _extract_code(last_raw)

            # A length stop can leave a syntactically incomplete answer. Retry it
            # once with a larger combined reasoning + answer budget.
            if code and last_finish_reason != "length":
                return GenerationResult(
                    model_id=model_id,
                    code=code,
                    raw_response=last_raw,
                    latency_seconds=time.perf_counter() - start,
                    finish_reason=last_finish_reason,
                    attempts=attempt,
                )

        elapsed = time.perf_counter() - start
        return GenerationResult(
            model_id=model_id,
            code="",
            raw_response=last_raw,
            latency_seconds=elapsed,
            error=(
                "The model did not return a complete code answer after two attempts "
                f"(finish reason: {last_finish_reason})."
            ),
            finish_reason=last_finish_reason,
            attempts=2,
        )
    except Exception as exc:  # noqa: BLE001 - one model's failure shouldn't sink the arena
        elapsed = time.perf_counter() - start
        return GenerationResult(
            model_id=model_id,
            code="",
            raw_response="",
            latency_seconds=elapsed,
            error=str(exc),
            finish_reason="error",
        )
