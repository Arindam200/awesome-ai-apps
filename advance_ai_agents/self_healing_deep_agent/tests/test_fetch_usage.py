import json

from contracts import validate
from tools.fetch_usage import fetch_usage


def test_downloads_every_page():
    out = fetch_usage("2026-11")
    rows = json.loads(open(out["path"], encoding="utf-8").read())
    assert out["total_reported"] == 26
    assert len(rows) == 26                       # 3 pages of 10, 10 and 6
    assert len({r["request_id"] for r in rows}) == 26


def test_output_passes_contract():
    args = {"month": "2026-11"}
    validate("fetch_usage", args, fetch_usage(**args))
