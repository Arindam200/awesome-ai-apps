"""Write the monthly cost report as a CSV file."""
import csv
from pathlib import Path


def _header() -> list:
    return ["model", "requests", "input_tokens", "cached_tokens", "output_tokens", "cost_usd"]


def _cost(row: dict) -> float:
    fresh = row["input_tokens"] - row["cached_tokens"]
    usd = (fresh * row["input_usd_per_1m"] + row["cached_tokens"] * row["cached_usd_per_1m"]
           + row["output_tokens"] * row["output_usd_per_1m"]) / 1_000_000
    return round(usd, 6)


def export_report(rows: list, path: str = "reports/cost_report_2026-11.csv") -> dict:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    priced = [{**r, "cost_usd": _cost(r)} for r in rows]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_header(), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(priced)
    return {"path": str(out).replace("\\", "/"), "rows": len(priced),
            "total_cost_usd": round(sum(r["cost_usd"] for r in priced), 6)}
