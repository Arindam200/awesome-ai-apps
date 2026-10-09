"""Centralized validation for LLM-generated SQL before execution.

The chat UI lets an LLM turn free-form natural language into SQL. Since the
LLM output is never trustworthy input, every query must pass through here
before it reaches the database — single SELECT only, whitelisted tables,
no write/DDL keywords, and a bounded result size.
"""

from sqlglot import exp, parse

ALLOWED_TABLES = {
    "category",
    "product",
    "order",
    "user",
    "order_item",
    "product_category",
}

FORBIDDEN_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "truncate",
    "exec",
    "execute",
    "grant",
    "revoke",
    "call",
    "into outfile",
    "load_file",
    "information_schema",
)

MAX_QUERY_LENGTH = 5000
DEFAULT_LIMIT = 100


class SQLValidationError(ValueError):
    """Raised when generated SQL fails the safety checks."""


def validate_sql(sql_query: str) -> str:
    """Validate and normalize a single MySQL SELECT statement.

    Raises SQLValidationError if the query is anything other than a
    read-only SELECT against an allowed table. Returns the (possibly
    LIMIT-capped) query text to execute.
    """
    if not sql_query or not sql_query.strip():
        raise SQLValidationError("Empty query")

    if len(sql_query) > MAX_QUERY_LENGTH:
        raise SQLValidationError("Query exceeds maximum length")

    sql_lower = sql_query.lower()
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in sql_lower:
            raise SQLValidationError(f"Forbidden keyword detected: {keyword}")

    try:
        statements = [s for s in parse(sql_query, read="mysql") if s is not None]
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

    return stmt.sql(dialect="mysql")
