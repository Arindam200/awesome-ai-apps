"""Small chart suggestion helpers for query results."""
from __future__ import annotations

from typing import Any


def suggest_chart(rows: list[dict[str, Any]]) -> dict[str, str] | None:
    if len(rows) < 2:
        return None

    columns = list(rows[0])
    numeric_columns = [
        column
        for column in columns
        if all(_is_number(row.get(column)) for row in rows if row.get(column) not in (None, ""))
    ]
    text_columns = [column for column in columns if column not in numeric_columns]
    date_columns = [column for column in text_columns if "date" in column.lower() or "month" in column.lower()]

    if date_columns and numeric_columns:
        return {
            "type": "line",
            "x": date_columns[0],
            "y": numeric_columns[0],
            "title": f"{numeric_columns[0]} by {date_columns[0]}",
        }

    categorical_columns = [
        column
        for column in text_columns
        if 1 < len({row.get(column) for row in rows}) <= 12
    ]
    if categorical_columns and numeric_columns:
        return {
            "type": "bar",
            "x": categorical_columns[0],
            "y": numeric_columns[0],
            "title": f"{numeric_columns[0]} by {categorical_columns[0]}",
        }

    return None


def _is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True

