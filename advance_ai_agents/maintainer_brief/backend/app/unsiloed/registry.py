"""Schema registry + classify→schema routing."""

import json
from functools import lru_cache
from pathlib import Path

SCHEMAS_DIR = Path(__file__).parent / "schemas"

# /classify requires categories as objects with name + description
DOC_CATEGORIES = [
    {"name": "conference_program", "description": "Conference schedule, session catalog, or CFP listing"},
    {"name": "speaker_deck", "description": "Presentation or talk slides"},
    {"name": "industry_report", "description": "Survey, market analysis, or industry report"},
    {"name": "rfc_or_design_doc", "description": "RFC, proposal, design document, or roadmap"},
    {"name": "security_advisory", "description": "Security advisory, CVE bulletin, or vulnerability report"},
    {"name": "other", "description": "Anything else"},
]

# Which extraction schemas run for each document category
CATEGORY_SCHEMAS: dict[str, list[str]] = {
    "conference_program": ["ecosystem_mention", "competitor_launch"],
    "speaker_deck": ["ecosystem_mention", "competitor_launch"],
    "industry_report": ["ecosystem_mention", "competitor_launch", "feature_request"],
    "rfc_or_design_doc": ["feature_request"],
    "security_advisory": ["security_signal"],
    "other": ["ecosystem_mention"],
}

# Maps schema name -> (array property in the schema, signal_type for normalized rows)
SCHEMA_SIGNAL_MAP: dict[str, tuple[str, str]] = {
    "feature_request": ("feature_requests", "feature_request"),
    "competitor_launch": ("competitor_launches", "competitor_launch"),
    "ecosystem_mention": ("ecosystem_mentions", "ecosystem_mention"),
    "security_signal": ("security_signals", "security"),
}


@lru_cache
def get_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / f"{name}.json").read_text())


def schemas_for_category(category: str) -> list[str]:
    return CATEGORY_SCHEMAS.get(category, CATEGORY_SCHEMAS["other"])
