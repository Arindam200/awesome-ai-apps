"""Natural-language analytics: question -> validated read-only SQL -> rows.

Database-first, NOT RAG. Two independent guardrails:
  1. sqlglot AST validation — single SELECT, known tables only, no DML/DDL, forced LIMIT.
  2. Execution on a read-only Postgres role (cannot write regardless of SQL).
The user's question is never concatenated into SQL — only the LLM's validated
output runs. Each result row carries (entity_kind, id) so the UI can link to
evidence.
"""

import logging

import sqlglot
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from app.config import settings
from app.intelligence.llm import parse_structured

logger = logging.getLogger(__name__)

ALLOWED_TABLES = {
    "accounts", "transactions", "vendors", "contracts", "investments",
    "obligations", "tax_items", "entity_citations", "documents",
}
MAX_ROWS = 500

SCHEMA_DOC = """You write a single PostgreSQL SELECT query answering the user's question about a
financial-document database. Tables (all rows scoped to one workspace):

accounts(id, institution_name, account_holder, account_number_masked, account_type, currency,
         opening_balance numeric, closing_balance numeric, statement_period_start date,
         statement_period_end date, canonical_vendor_id)
transactions(id, account_id, txn_date date, description, counterparty, amount numeric,
             direction text /* 'debit'=money out, 'credit'=money in */, balance_after numeric,
             category, canonical_vendor_id)
vendors(id, name, normalized_name, address, tax_id, is_canonical bool, canonical_vendor_id)
  -- canonical vendors have is_canonical=true; every entity's canonical_vendor_id points to one.
contracts(id, contract_type /* 'vendor_contract'|'loan_agreement' */, counterparty,
          contract_value numeric, currency, start_date date, end_date date, renewal_terms,
          principal_amount numeric, interest_rate numeric, maturity_date date, company_address,
          canonical_vendor_id)
investments(id, holding_name, ticker, quantity numeric, cost_basis numeric, current_value numeric,
            ownership_percentage numeric, valuation_date date, canonical_vendor_id)
obligations(id, obligation_type, description, counterparty, amount numeric, due_date date,
            canonical_vendor_id)
tax_items(id, tax_year int, jurisdiction, filing_type, line_item, counterparty, amount numeric,
          canonical_vendor_id)

Rules:
- Return ONE SELECT statement only. No INSERT/UPDATE/DELETE/DDL.
- To total what a vendor was PAID, sum transactions.amount WHERE direction='debit', grouped by
  canonical_vendor_id, joined to vendors (is_canonical=true) for the name.
- "expiring this year" = end_date or maturity_date within the next 365 days of CURRENT_DATE.
- Always include the primary-key id of the main entity, and a literal column
  `entity_kind` naming that entity's kind (one of: account, transaction, vendor, contract,
  investment, obligation, tax) so results can link to evidence. Example:
  SELECT id, 'contract' AS entity_kind, counterparty, contract_value FROM contracts WHERE ...
- Prefer human-readable columns (names, amounts, dates) in the output.
- Today's date is available as CURRENT_DATE."""


class SqlQuery(BaseModel):
    sql: str = Field(description="A single PostgreSQL SELECT statement answering the question")
    rationale: str = Field(description="One sentence on what the query computes")


class SqlValidationError(Exception):
    pass


_ro_engine = None


def _readonly_engine():
    global _ro_engine
    if _ro_engine is None:
        url = settings.database_readonly_url or settings.database_url
        _ro_engine = create_engine(url, pool_pre_ping=True)
    return _ro_engine


def validate_sql(sql: str) -> str:
    """Parse + harden. Raises SqlValidationError on anything unsafe. Returns safe SQL."""
    statements = sqlglot.parse(sql, read="postgres")
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SqlValidationError("exactly one statement is allowed")
    stmt = statements[0]
    if stmt.key != "select":
        raise SqlValidationError("only SELECT statements are allowed")

    lowered = sql.lower()
    for banned in ("insert", "update", "delete", "drop", "alter", "truncate", "grant",
                   "revoke", "create", "copy", "merge", ";--", "/*", "pg_", "into "):
        if banned in lowered:
            raise SqlValidationError(f"disallowed token: {banned.strip()}")

    for tbl in stmt.find_all(sqlglot.exp.Table):
        if tbl.name.lower() not in ALLOWED_TABLES:
            raise SqlValidationError(f"unknown table: {tbl.name}")

    if not stmt.args.get("limit"):
        stmt.set("limit", sqlglot.exp.Limit(expression=sqlglot.exp.Literal.number(MAX_ROWS)))
    return stmt.sql(dialect="postgres")


def answer(question: str) -> dict:
    gen = parse_structured(
        tier="synthesis",
        system=SCHEMA_DOC,
        user_content=f"Question: {question}\n\nWrite the SELECT query.",
        output_model=SqlQuery,
        max_tokens=2000,
    )
    if gen is None:
        return {"error": "could not translate the question", "sql": None, "rows": []}

    try:
        safe_sql = validate_sql(gen.sql)
    except (SqlValidationError, Exception) as e:  # sqlglot may raise ParseError
        logger.warning("rejected SQL for %r: %s", question, e)
        return {"error": f"generated query was rejected: {e}", "sql": gen.sql, "rows": []}

    try:
        with _readonly_engine().connect() as conn:
            result = conn.execute(text(safe_sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, _row)) for _row in result.fetchall()]
    except Exception as e:
        logger.exception("read-only execution failed")
        return {"error": f"execution failed: {e}", "sql": safe_sql, "rows": []}

    # JSON-safe coercion (Decimal/date)
    from datetime import date, datetime
    from decimal import Decimal

    def _ser(v):
        if isinstance(v, Decimal):
            return float(v)
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        return v

    rows = [{k: _ser(v) for k, v in r.items()} for r in rows]
    return {"error": None, "sql": safe_sql, "rationale": gen.rationale, "columns": columns, "rows": rows}
