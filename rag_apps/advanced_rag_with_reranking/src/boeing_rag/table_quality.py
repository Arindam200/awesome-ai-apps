from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class TableQuality:
    score: float
    status: str
    issues: list[str]
    rows: int
    cols: int
    empty_cell_ratio: float
    span_cell_ratio: float


def assess_table_quality(df: pd.DataFrame, raw_table: dict[str, Any] | None = None) -> TableQuality:
    issues: list[str] = []
    rows, cols = df.shape
    score = 1.0

    if rows == 0 or cols == 0:
        return TableQuality(0.0, "failed", ["empty_table"], rows, cols, 1.0, 0.0)

    string_df = df.fillna("").astype(str).map(lambda value: value.strip())
    total_cells = rows * cols
    empty_cells = int((string_df == "").sum().sum())
    empty_ratio = empty_cells / total_cells if total_cells else 1.0
    if empty_ratio > 0.25:
        issues.append("many_empty_cells")
        score -= 0.2

    headers = [str(col).strip() for col in df.columns]
    generic_headers = sum(1 for header in headers if re.fullmatch(r"\d+|Unnamed:.*", header))
    if generic_headers:
        issues.append("generic_or_missing_headers")
        score -= min(0.25, 0.08 * generic_headers)

    duplicate_headers = len(headers) - len(set(headers))
    if duplicate_headers:
        issues.append("duplicate_headers")
        score -= min(0.2, 0.07 * duplicate_headers)

    long_cell_count = int(string_df.map(lambda value: len(value) > 350).sum().sum())
    if long_cell_count:
        issues.append("very_long_cells")
        score -= min(0.2, 0.04 * long_cell_count)

    span_ratio = 0.0
    if raw_table:
        cells = raw_table.get("data", {}).get("table_cells", [])
        if cells:
            span_cells = [
                cell
                for cell in cells
                if int(cell.get("row_span") or 1) > 1 or int(cell.get("col_span") or 1) > 1
            ]
            span_ratio = len(span_cells) / len(cells)
            if span_ratio > 0.08:
                issues.append("merged_or_spanning_cells")
                score -= min(0.25, span_ratio)

        expected_cells = int(raw_table.get("data", {}).get("num_rows") or rows) * int(
            raw_table.get("data", {}).get("num_cols") or cols
        )
        actual_cells = len(cells)
        if expected_cells and actual_cells / expected_cells < 0.75:
            issues.append("sparse_detected_grid")
            score -= 0.2

    if rows > 40 or cols > 4:
        issues.append("large_complex_table")
        score -= 0.1

    score = max(0.0, min(1.0, score))
    if score >= 0.82:
        status = "pass"
    elif score >= 0.62:
        status = "review"
    else:
        status = "fail"
    return TableQuality(
        score=round(score, 3),
        status=status,
        issues=issues,
        rows=rows,
        cols=cols,
        empty_cell_ratio=round(empty_ratio, 3),
        span_cell_ratio=round(span_ratio, 3),
    )
