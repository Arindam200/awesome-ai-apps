import csv

from contracts import validate
from tools.export_report import export_report

ROWS = [
    {"model": "deepseek-ai/DeepSeek-V4.1-Flash-1017-fast", "requests": 2, "input_tokens": 2000,
     "cached_tokens": 1500, "output_tokens": 100,
     "input_usd_per_1m": 0.60, "cached_usd_per_1m": 0.012, "output_usd_per_1m": 2.40},
    {"model": "meta-llama/Llama-3.3-70B-Instruct", "requests": 1, "input_tokens": 500,
     "cached_tokens": 0, "output_tokens": 20,
     "input_usd_per_1m": 0.13, "cached_usd_per_1m": 0.013, "output_usd_per_1m": 0.40},
]


def test_report_passes_contract():
    args = {"rows": ROWS, "path": "reports/r.csv"}
    validate("export_report", args, export_report(**args))


def test_cost_column_is_written_and_correct():
    out = export_report(ROWS, "reports/r.csv")
    rows = list(csv.DictReader(open(out["path"], encoding="utf-8")))
    # 500 fresh * 0.60 + 1500 cached * 0.012 + 100 out * 2.40, per 1M tokens
    assert float(rows[0]["cost_usd"]) == 0.000558
    assert out["total_cost_usd"] == round(0.000558 + 0.000073, 6)
