"""Schema registry + classify→schema routing for financial documents."""

import json
from functools import lru_cache
from pathlib import Path

SCHEMAS_DIR = Path(__file__).parent / "schemas"

# /classify requires categories as {name, description} objects
DOC_CATEGORIES = [
    {"name": "bank_statement", "description": "Bank or checking/savings account statement with a transaction table"},
    {"name": "investment_statement", "description": "Brokerage or investment account statement listing holdings and valuations"},
    {"name": "vendor_contract", "description": "Service agreement or contract with a vendor/supplier"},
    {"name": "loan_agreement", "description": "Loan, credit facility, or promissory note with principal and interest terms"},
    {"name": "tax_filing", "description": "Tax return or filing with line items and deductions"},
    {"name": "annual_report", "description": "Annual or quarterly financial report with statements and disclosures"},
    {"name": "audit_report", "description": "Audit report or financial review with findings and obligations"},
    {"name": "cap_table", "description": "Capitalization table listing equity holders and ownership"},
    {"name": "other", "description": "Any other financial document"},
]

# category -> which extraction schemas to run
CATEGORY_SCHEMAS: dict[str, list[str]] = {
    "bank_statement": ["accounts", "transactions"],
    "investment_statement": ["investments", "accounts"],
    "vendor_contract": ["vendors", "contracts"],
    "loan_agreement": ["loans"],
    "tax_filing": ["taxes", "obligations"],
    "annual_report": ["investments", "obligations", "vendors"],
    "audit_report": ["obligations", "investments"],
    "cap_table": ["investments"],
    "other": ["vendors"],
}

# schema name -> (array property in the result, entity_kind for citations/normalization)
# entity_kind keys map to ENTITY_MODELS in app.models
SCHEMA_ENTITY_MAP: dict[str, tuple[str, str]] = {
    "accounts": ("accounts", "account"),
    "transactions": ("transactions", "transaction"),
    "vendors": ("vendors", "vendor"),
    "contracts": ("contracts", "contract"),
    "loans": ("loans", "contract"),
    "investments": ("investments", "investment"),
    "obligations": ("obligations", "obligation"),
    "taxes": ("tax_items", "tax"),
}


@lru_cache
def get_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / f"{name}.json").read_text())


def schemas_for_category(category: str) -> list[str]:
    return CATEGORY_SCHEMAS.get(category, CATEGORY_SCHEMAS["other"])
