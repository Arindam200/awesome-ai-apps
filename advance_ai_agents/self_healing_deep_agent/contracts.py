"""Output checks run after every tool call. "It returned" is not the same as "it's right".

This file lives outside tools/, so the agent can read it but never edit it."""
import csv
import json
from pathlib import Path

REPORT_COLUMNS = ["model", "requests", "input_tokens", "cached_tokens", "output_tokens", "cost_usd"]


class ContractError(Exception):
    """The tool returned, but its output is wrong."""


def validate(tool_name: str, args: dict, result) -> None:
    checker = _CHECKERS.get(tool_name)
    if checker:
        checker(args, result)


def _check_usage(args, result):
    rows = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    if len(rows) != result["total_reported"]:
        raise ContractError(
            f"fetch_usage saved {len(rows)} rows but the API reported total={result['total_reported']}. "
            "Some request logs are missing.")


def _check_summary(args, result):
    rows = json.loads(Path(args["path"]).read_text(encoding="utf-8"))
    if result.get("requests") != len(rows):
        raise ContractError(f"summarize_usage counted {result.get('requests')} requests, file has {len(rows)}")
    for m in result["models"]:
        for key in ("requests", "input_tokens", "cached_tokens", "output_tokens"):
            if not isinstance(m.get(key), int):
                raise ContractError(f"summarize_usage: '{key}' for {m.get('model')} must be an int")
    if sum(m["requests"] for m in result["models"]) != len(rows):
        raise ContractError("summarize_usage: per-model requests don't add up to the row count")


def _check_pricing(args, result):
    for key in ("input_usd_per_1m", "cached_usd_per_1m", "output_usd_per_1m"):
        if not isinstance(result.get(key), float):
            raise ContractError(f"fetch_pricing must return a float '{key}'")


def _check_report(args, result):
    path = Path(result["path"])
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    if header != REPORT_COLUMNS:
        missing = [c for c in REPORT_COLUMNS if c not in header]
        raise ContractError(f"report header is {header}, expected {REPORT_COLUMNS} (missing: {missing})")
    if len(body) != len(args["rows"]):
        raise ContractError(f"expected {len(args['rows'])} data rows, found {len(body)}")


_CHECKERS = {
    "fetch_usage": _check_usage,
    "summarize_usage": _check_summary,
    "fetch_pricing": _check_pricing,
    "export_report": _check_report,
}
