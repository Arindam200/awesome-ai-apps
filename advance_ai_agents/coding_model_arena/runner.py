"""Sends a challenge prompt to a Nebius Token Factory model and extracts the
single code block it returns.
"""

import ast
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
MINIMAX_COMPLETION_BUDGETS = (24000, 32000)
REQUEST_TIMEOUT_SECONDS = 90
NON_THINKING_MODEL_PREFIXES = ("zai-org/GLM-", "Qwen/Qwen3.5-")


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


def _expected_entrypoint(prompt: str) -> str | None:
    """Extract the exact function/class name requested by a preset prompt."""
    match = re.search(r"^\s*(?:def|class)\s+([A-Za-z_]\w*)", prompt, re.MULTILINE)
    return match.group(1) if match else None


def _code_error(code: str, prompt: str) -> str | None:
    """Return why a response is not an executable answer, or ``None``."""
    if not code.strip():
        return "the response contained no code"
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"the returned code was incomplete or invalid ({exc.msg})"

    entrypoint = _expected_entrypoint(prompt)
    defined = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    if entrypoint and entrypoint not in defined:
        return f"the required entrypoint {entrypoint!r} was not defined"
    return None


def _model_options(model_id: str) -> dict:
    """Keep hybrid models from spending the whole arena budget on reasoning."""
    if model_id.startswith(NON_THINKING_MODEL_PREFIXES):
        return {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
    return {}


def _completion_budgets(model_id: str) -> tuple[int, int]:
    """Reserve enough room for models that require long native reasoning."""
    if model_id == "MiniMaxAI/MiniMax-M3":
        return MINIMAX_COMPLETION_BUDGETS
    return INITIAL_COMPLETION_BUDGET, RETRY_COMPLETION_BUDGET


def generate_solution(client: OpenAI, model_id: str, prompt: str) -> GenerationResult:
    start = time.perf_counter()
    attempt = 0
    last_raw = ""
    last_finish_reason = "unknown"
    last_code_error = "the response contained no code"
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        for attempt, budget in enumerate(_completion_budgets(model_id), start=1):
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=0.2,
                max_completion_tokens=budget,
                reasoning_effort="low",
                timeout=REQUEST_TIMEOUT_SECONDS,
                **_model_options(model_id),
            )
            choice = response.choices[0]
            last_raw = choice.message.content or ""
            last_finish_reason = choice.finish_reason or "unknown"
            code = _extract_code(last_raw)
            last_code_error = _code_error(code, prompt) or ""

            # A length stop can leave a syntactically incomplete answer. Retry it
            # once with a larger combined reasoning + answer budget. Some models
            # also report "stop" after returning prose, an empty answer, or a
            # malformed code block, so validate the answer rather than trusting
            # finish_reason alone.
            if not last_code_error and last_finish_reason != "length":
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
                f"(finish reason: {last_finish_reason}; {last_code_error})."
            ),
            finish_reason=last_finish_reason,
            attempts=2,
        )
    except Exception as exc:  # noqa: BLE001 - one model's failure shouldn't sink the arena
        elapsed = time.perf_counter() - start
        detail = str(exc) or type(exc).__name__
        if "timed out" in detail.lower():
            detail = (
                f"Generation timed out after {REQUEST_TIMEOUT_SECONDS}s. "
                "The model did not complete a code answer in the arena time limit."
            )
        return GenerationResult(
            model_id=model_id,
            code="",
            raw_response=last_raw,
            latency_seconds=elapsed,
            error=detail,
            finish_reason="error",
            attempts=max(attempt, 1),
        )
