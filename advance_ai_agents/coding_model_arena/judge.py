"""LLM-as-judge: one call scores every contestant's submission together, so
rankings are relative and consistent rather than five independent, incomparable
scores.
"""

import json
import re
from dataclasses import dataclass, field

from openai import OpenAI

JUDGE_SYSTEM_PROMPT = (
    "You are an impartial code review judge in a coding-model competition. "
    "You will see the original challenge and several anonymized candidate "
    "submissions with their actual test results. Score each candidate "
    "independently. Test results are ground truth and must dominate the "
    "correctness score, do not contradict them.\n\n"
    "Respond with ONLY a JSON object of this exact shape, no prose:\n"
    "{\n"
    '  "scores": {\n'
    '    "<candidate_label>": {\n'
    '      "correctness": <0-50 int>,\n'
    '      "code_quality": <0-30 int>,\n'
    '      "efficiency": <0-20 int>,\n'
    '      "rationale": "<one or two sentences>"\n'
    "    }, ...\n"
    "  }\n"
    "}"
)

JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
JUDGE_TIMEOUT_SECONDS = 60


@dataclass
class JudgeScore:
    correctness: int
    code_quality: int
    efficiency: int
    rationale: str

    @property
    def total(self) -> int:
        return self.correctness + self.code_quality + self.efficiency


@dataclass
class JudgeVerdict:
    scores: dict[str, JudgeScore] = field(default_factory=dict)
    error: str | None = None


def _build_prompt(challenge_prompt: str, submissions: dict[str, dict]) -> str:
    parts = [f"## Challenge\n{challenge_prompt}\n"]
    for label, sub in submissions.items():
        passed_tests = sub.get("passed_tests", 1 if sub.get("passed") else 0)
        total_tests = sub.get("total_tests", 1)
        test_score = sub.get("test_score", 100 if sub.get("passed") else 0)
        test_status = f"{passed_tests}/{total_tests} hidden cases passed ({test_score}%)"
        parts.append(
            f"## Candidate: {label}\n"
            f"Test result: {test_status}\n"
            f"Test output/error: {sub['test_output'][:800]}\n"
            f"```python\n{sub['code'] or '(no code returned)'}\n```\n"
        )
    return "\n".join(parts)


def judge_submissions(
    client: OpenAI,
    judge_model: str,
    challenge_prompt: str,
    submissions: dict[str, dict],
) -> JudgeVerdict:
    """`submissions` maps a display label -> {"code", "passed", "test_output"}."""
    prompt = _build_prompt(challenge_prompt, submissions)
    try:
        response = client.chat.completions.create(
            model=judge_model,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=2000,
            response_format={"type": "json_object"},
            timeout=JUDGE_TIMEOUT_SECONDS,
        )
        raw = response.choices[0].message.content or ""
        if not raw.strip():
            finish_reason = response.choices[0].finish_reason or "unknown"
            raise ValueError(
                f"Judge returned an empty response (finish reason: {finish_reason})."
            )
        match = JSON_BLOCK_RE.search(raw)
        payload = json.loads(match.group(0) if match else raw)
        scores = {}
        for label, s in payload.get("scores", {}).items():
            scores[label] = JudgeScore(
                correctness=int(s.get("correctness", 0)),
                code_quality=int(s.get("code_quality", 0)),
                efficiency=int(s.get("efficiency", 0)),
                rationale=str(s.get("rationale", "")),
            )
        return JudgeVerdict(scores=scores)
    except Exception as exc:  # noqa: BLE001 - fall back to test-only scoring upstream
        return JudgeVerdict(error=str(exc))
