"""Read-only SQL validation for generated SQLite queries."""
from __future__ import annotations

from dataclasses import dataclass
import re

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|"
    r"pragma|vacuum|reindex|load_extension)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    sql: str | None = None
    error: str | None = None


def validate_select_sql(
    sql: str,
    allowed_tables: set[str],
    default_limit: int = 50,
) -> ValidationResult:
    """Validate and normalize a generated SQL query.

    The policy is intentionally narrow: one SELECT or WITH query, no comments,
    no write operations, and only the tables assigned to the chosen domain.
    """
    cleaned = _clean_sql(sql)
    if not cleaned:
        return ValidationResult(ok=False, error="The model did not return SQL.")

    lowered = cleaned.lower()
    if "--" in cleaned or "/*" in cleaned or "*/" in cleaned:
        return ValidationResult(ok=False, error="Comments are not allowed in generated SQL.")
    if FORBIDDEN_SQL.search(cleaned):
        return ValidationResult(ok=False, error="Only read-only SELECT queries are allowed.")
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return ValidationResult(ok=False, error="Query must start with SELECT or WITH.")

    parsed_tables = _extract_tables_with_sqlglot(cleaned)
    if parsed_tables is None:
        parsed_tables = _extract_tables_with_regex(cleaned)

    unknown_tables = parsed_tables - allowed_tables
    if unknown_tables:
        tables = ", ".join(sorted(unknown_tables))
        return ValidationResult(ok=False, error=f"Query used tables outside this domain: {tables}")

    if ";" in cleaned.rstrip(";"):
        return ValidationResult(ok=False, error="Multiple SQL statements are not allowed.")

    return ValidationResult(ok=True, sql=_ensure_limit(cleaned, default_limit))


def _clean_sql(sql: str) -> str:
    cleaned = sql.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_+-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    match = re.search(r"\b(with|select)\b", cleaned, re.IGNORECASE)
    if match:
        cleaned = cleaned[match.start() :]
    return cleaned.strip().rstrip(";").strip()


def _ensure_limit(sql: str, default_limit: int) -> str:
    if re.search(r"\blimit\s+\d+\b", sql, re.IGNORECASE):
        return sql
    return f"{sql} LIMIT {default_limit}"


def _extract_tables_with_sqlglot(sql: str) -> set[str] | None:
    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        return None

    try:
        statements = sqlglot.parse(sql, read="sqlite")
    except Exception:
        return None

    if len(statements) != 1 or statements[0] is None:
        return set()

    expression = statements[0]
    if FORBIDDEN_SQL.search(expression.sql(dialect="sqlite")):
        return set()
    return {table.name for table in expression.find_all(exp.Table)}


def _extract_tables_with_regex(sql: str) -> set[str]:
    tables: set[str] = set()
    for match in re.finditer(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.IGNORECASE):
        tables.add(match.group(1))
    return tables

