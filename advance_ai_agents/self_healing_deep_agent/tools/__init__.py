"""Tool registry. Each tool is tools/<name>.py exposing a function <name>().

The agent may patch those files, but never this registry."""
import importlib
from typing import Any

from pydantic import BaseModel, Field


class FetchUsageArgs(BaseModel):
    month: str = Field(description="Billing month as YYYY-MM, for example 2026-11.")


class SummarizeUsageArgs(BaseModel):
    path: str = Field(description="Path returned by fetch_usage.")


class FetchPricingArgs(BaseModel):
    model_id: str = Field(description="Exact model id, for example meta-llama/Llama-3.3-70B-Instruct.")


class ReportRow(BaseModel):
    model: str
    requests: int
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    input_usd_per_1m: float
    cached_usd_per_1m: float
    output_usd_per_1m: float


class ExportReportArgs(BaseModel):
    rows: list[ReportRow] = Field(description="One row per model: its usage totals plus its prices.")
    path: str = Field(default="reports/cost_report_2026-11.csv")


TOOLS: dict[str, dict[str, Any]] = {
    "fetch_usage": {
        "args": FetchUsageArgs,
        "description": "Download every request log for a billing month from the provider API "
                       "and save them to a JSON file. Returns the file path and row counts.",
    },
    "summarize_usage": {
        "args": SummarizeUsageArgs,
        "description": "Read a usage file from fetch_usage and return per-model totals: "
                       "requests, input_tokens, cached_tokens, output_tokens, cache_hit_rate.",
    },
    "fetch_pricing": {
        "args": FetchPricingArgs,
        "description": "Get a model's prices in USD per 1M tokens: input, cached input and output.",
    },
    "export_report": {
        "args": ExportReportArgs,
        "description": "Compute each model's cost and write the monthly cost report CSV. "
                       "Each row combines one model's usage totals with its prices.",
    },
}


def load_tool(name: str):
    """Import (or re-import) a tool so freshly patched source is always used."""
    importlib.invalidate_caches()
    module = importlib.reload(importlib.import_module(f"tools.{name}"))
    return getattr(module, name)
