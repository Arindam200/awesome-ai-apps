import json

from contracts import validate
from tools.summarize_usage import summarize_usage

ROWS = [
    {"model": "a", "prompt_tokens": "1,240", "cached_tokens": "1,000", "completion_tokens": "96"},
    {"model": "a", "prompt_tokens": 760, "cached_tokens": 500, "completion_tokens": 4},
    {"model": "b", "prompt_tokens": 500, "cached_tokens": 0, "completion_tokens": 20},  # never cached
]


def _write(tmp_path, rows):
    p = tmp_path / "usage.json"
    p.write_text(json.dumps(rows), encoding="utf-8")
    return str(p)


def test_thousands_separators_are_parsed(tmp_path):
    out = summarize_usage(_write(tmp_path, ROWS))
    a = next(m for m in out["models"] if m["model"] == "a")
    assert (a["requests"], a["input_tokens"], a["cached_tokens"], a["output_tokens"]) == (2, 2000, 1500, 100)
    assert a["cache_hit_rate"] == 0.75


def test_model_with_no_cache_hits(tmp_path):
    out = summarize_usage(_write(tmp_path, ROWS))
    b = next(m for m in out["models"] if m["model"] == "b")
    assert b["cache_hit_rate"] == 0.0


def test_output_passes_contract(tmp_path):
    args = {"path": _write(tmp_path, ROWS)}
    validate("summarize_usage", args, summarize_usage(**args))
