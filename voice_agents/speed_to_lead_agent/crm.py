"""Mock CRM: append leads to a local JSON file."""

import json
from datetime import datetime, timezone
from pathlib import Path

LEADS_FILE = Path(__file__).parent / "leads.json"


def log_lead(lead: dict) -> dict:
    entry = {"logged_at": datetime.now(timezone.utc).isoformat(), **lead}
    leads = []
    if LEADS_FILE.exists():
        leads = json.loads(LEADS_FILE.read_text())
    leads.append(entry)
    LEADS_FILE.write_text(json.dumps(leads, indent=2))
    return {"ok": True, "lead_id": len(leads)}
