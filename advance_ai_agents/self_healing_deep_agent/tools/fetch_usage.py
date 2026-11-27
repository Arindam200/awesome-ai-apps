"""Download one month of request logs from the provider's usage API."""
import json
from pathlib import Path

from provider_api.client import get_json


def fetch_usage(month: str) -> dict:
    rows, page, total = [], 1, 0
    while page:
        payload = get_json(f"/v2/usage?month={month}&page={page}")
        rows.extend(payload["data"])
        total = payload["total"]
        page = payload["next_page"]

    out = Path("data") / f"usage_{month}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return {"month": month, "path": str(out).replace("\\", "/"),
            "rows_fetched": len(rows), "total_reported": total}
