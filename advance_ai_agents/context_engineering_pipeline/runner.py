"""Core evaluation harness: runs prompt formats over an eval set via Nebius."""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from openai import OpenAI

ROOT = Path(__file__).parent
PROMPTS_DIR = ROOT / "prompts"
DATA_DIR = ROOT / "data"

FORMATS = ["xml", "json", "markdown"]
TASKS = {
    "extraction": {
        "eval_file": "extraction_eval.jsonl",
        "prompt_stem": "extraction",
    },
    "classification": {
        "eval_file": "classification_eval.jsonl",
        "prompt_stem": "classification",
    },
}


def get_client() -> OpenAI:
    return OpenAI(
        base_url="https://api.tokenfactory.nebius.com/v1/",
        api_key=os.environ["NEBIUS_API_KEY"],
    )


def load_prompt(task: str, fmt: str) -> str:
    return (PROMPTS_DIR / f"{TASKS[task]['prompt_stem']}_{fmt}.txt").read_text()


def load_eval(task: str, limit: int | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with (DATA_DIR / TASKS[task]["eval_file"]).open() as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items[:limit] if limit else items


# ---------- grading ----------

def _parse_json_obj(raw: str) -> dict[str, Any] | None:
    """Best-effort JSON object extraction from a model response."""
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.MULTILINE).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def grade_extraction(raw: str, expected: dict[str, str]) -> dict[str, Any]:
    parsed = _parse_json_obj(raw) or {}
    fields = ["name", "email", "company", "role"]
    per_field = {}
    hits = 0
    for key in fields:
        got = str(parsed.get(key, "")).strip().lower()
        want = str(expected.get(key, "")).strip().lower()
        ok = got == want
        per_field[key] = ok
        hits += int(ok)
    return {
        "correct": hits == len(fields),
        "field_accuracy": hits / len(fields),
        "per_field": per_field,
        "parsed": parsed,
        "parse_ok": bool(parsed),
    }


def grade_classification(raw: str, expected: str) -> dict[str, Any]:
    norm = raw.strip().strip(".").strip('"').strip("'").lower()
    # Extract the first occurrence of a valid label if wrapped in extra text.
    for label in ("positive", "negative", "neutral"):
        if label in norm.split() or norm == label:
            norm = label
            break
    correct = norm == expected.strip().lower()
    return {
        "correct": correct,
        "field_accuracy": 1.0 if correct else 0.0,
        "predicted": norm,
        "parse_ok": norm in {"positive", "negative", "neutral"},
    }


GRADERS: dict[str, Callable[[str, Any], dict[str, Any]]] = {
    "extraction": grade_extraction,
    "classification": grade_classification,
}


# ---------- run ----------

@dataclass
class RunResult:
    task: str
    fmt: str
    model: str
    items: list[dict[str, Any]] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        if not self.items:
            return 0.0
        return sum(i["grade"]["correct"] for i in self.items) / len(self.items)

    @property
    def field_accuracy(self) -> float:
        if not self.items:
            return 0.0
        return sum(i["grade"]["field_accuracy"] for i in self.items) / len(self.items)

    @property
    def avg_latency_ms(self) -> float:
        if not self.items:
            return 0.0
        return sum(i["latency_ms"] for i in self.items) / len(self.items)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(i.get("prompt_tokens", 0) for i in self.items)

    @property
    def total_completion_tokens(self) -> int:
        return sum(i.get("completion_tokens", 0) for i in self.items)

    def summary(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "format": self.fmt,
            "model": self.model,
            "n": len(self.items),
            "accuracy": round(self.accuracy, 4),
            "field_accuracy": round(self.field_accuracy, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
        }


def run_one(
    client: OpenAI,
    model: str,
    task: str,
    fmt: str,
    items: list[dict[str, Any]],
    on_progress: Callable[[int, int], None] | None = None,
    temperature: float = 0.0,
) -> RunResult:
    template = load_prompt(task, fmt)
    grader = GRADERS[task]
    result = RunResult(task=task, fmt=fmt, model=model)

    for idx, item in enumerate(items):
        prompt = template.replace("{text}", item["text"])
        t0 = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            raw = resp.choices[0].message.content or ""
            usage = getattr(resp, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
            error = None
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            raw = ""
            prompt_tokens = 0
            completion_tokens = 0
            error = str(exc)

        grade = grader(raw, item["expected"]) if error is None else {
            "correct": False, "field_accuracy": 0.0, "parse_ok": False,
        }
        result.items.append({
            "input": item["text"],
            "expected": item["expected"],
            "raw": raw,
            "grade": grade,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "error": error,
        })
        if on_progress:
            on_progress(idx + 1, len(items))
    return result


def run_all(
    model: str,
    tasks: Iterable[str] = tuple(TASKS),
    formats: Iterable[str] = tuple(FORMATS),
    limit: int | None = None,
    on_progress: Callable[[str, str, int, int], None] | None = None,
) -> list[RunResult]:
    client = get_client()
    results: list[RunResult] = []
    for task in tasks:
        items = load_eval(task, limit=limit)
        for fmt in formats:
            def _cb(done: int, total: int, t=task, f=fmt):
                if on_progress:
                    on_progress(t, f, done, total)
            results.append(run_one(client, model, task, fmt, items, on_progress=_cb))
    return results


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen3-30B-A3B")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--task", choices=list(TASKS) + ["all"], default="all")
    args = parser.parse_args()

    tasks = list(TASKS) if args.task == "all" else [args.task]

    def _p(task: str, fmt: str, done: int, total: int) -> None:
        print(f"  [{task}/{fmt}] {done}/{total}", end="\r")

    results = run_all(args.model, tasks=tasks, limit=args.limit, on_progress=_p)
    print()
    print(json.dumps([r.summary() for r in results], indent=2))
