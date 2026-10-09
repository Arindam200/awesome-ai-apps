"""Centralized validation for LLM-generated SQL before execution.

analyst.py asks an LLM to translate a natural language question into SQL
against sales.db. LLM output is untrusted, so every generated query is
checked here before it ever reaches sqlite3 — single SELECT only,
whitelisted tables, no write/DDL/pragma keywords.
"""

from sqlglot import exp, parse

ALLOWED_TABLES = {"users", "orders"}

FORBIDDEN_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "truncate",
    "attach",
    "detach",
    "pragma",
    "vacuum",
    "exec",
    "execute",
)

MAX_QUERY_LENGTH = 2000
DEFAULT_LIMIT = 200


class SQLValidationError(ValueError):
    """Raised when generated SQL fails the safety checks."""


def validate_sql(sql_query: str) -> str:
    """Validate and normalize a single SQLite SELECT statement."""
    if not sql_query or not sql_query.strip():
        raise SQLValidationError("Empty query")

    if len(sql_query) > MAX_QUERY_LENGTH:
        raise SQLValidationError("Query exceeds maximum length")

    sql_lower = sql_query.lower()
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in sql_lower:
            raise SQLValidationError(f"Forbidden keyword detected: {keyword}")

    try:
        statements = [s for s in parse(sql_query, read="sqlite") if s is not None]
    except Exception as exc:
        raise SQLValidationError(f"Could not parse SQL: {exc}") from exc

    if len(statements) != 1:
        raise SQLValidationError("Only a single SELECT statement is allowed")

    stmt = statements[0]
    if not isinstance(stmt, exp.Select):
        raise SQLValidationError("Only SELECT queries are allowed")

    tables = {t.name.lower() for t in stmt.find_all(exp.Table)}
    disallowed = tables - ALLOWED_TABLES
    if disallowed:
        raise SQLValidationError(f"Access denied for tables: {sorted(disallowed)}")

    if not stmt.args.get("limit"):
        stmt.set("limit", exp.Limit(expression=exp.Literal.number(DEFAULT_LIMIT)))

    return stmt.sql(dialect="sqlite")
