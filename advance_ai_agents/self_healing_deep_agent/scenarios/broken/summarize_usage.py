"""Turn raw request logs into per-model token totals."""
import json
from pathlib import Path


def _to_int(value) -> int:
    return int(value)


def summarize_usage(path: str) -> dict:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    models: dict[str, dict] = {}
    for r in rows:
        m = models.setdefault(r["model"], {"model": r["model"], "requests": 0, "input_tokens": 0,
                                           "cached_tokens": 0, "output_tokens": 0})
        m["requests"] += 1
        m["input_tokens"] += _to_int(r["prompt_tokens"])
        m["cached_tokens"] += _to_int(r["cached_tokens"])
        m["output_tokens"] += _to_int(r["completion_tokens"])

    for m in models.values():
        m["cache_hit_rate"] = round(m["cached_tokens"] / m["input_tokens"], 3)
    return {"requests": len(rows), "models": list(models.values())}
