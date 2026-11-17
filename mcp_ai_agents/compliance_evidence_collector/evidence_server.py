"""Local mock MCP server exposing enterprise evidence sources.

Sources: control catalogue, policy documents, ticket records, deployment logs
and access reviews, all read from ./data fixtures (no external accounts).
"""
import json
from pathlib import Path

from fastmcp import FastMCP

DATA = Path(__file__).parent / "data"
mcp = FastMCP("compliance-evidence")


def _load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@mcp.tool()
def list_controls() -> list[dict]:
    """List the audit controls to be assessed, with requirement text and needed evidence types."""
    return _load("controls.json")


@mcp.tool()
def get_policy_documents() -> list[dict]:
    """Return policy documents as {source, content}. Cite as the `source` value."""
    return [
        {"source": f"policies/{p.name}", "content": p.read_text(encoding="utf-8")}
        for p in sorted((DATA / "policies").glob("*.md"))
    ]


@mcp.tool()
def get_tickets(ticket_type: str = "") -> list[dict]:
    """Return ticket records (e.g. change tickets). Optionally filter by type."""
    t = _load("tickets.json")
    return [x for x in t if not ticket_type or x["type"] == ticket_type]


@mcp.tool()
def get_deploy_logs() -> list[dict]:
    """Return production deployment log entries with their linked change ticket (null if none)."""
    return _load("deploy_logs.json")


@mcp.tool()
def get_access_reviews() -> list[dict]:
    """Return quarterly privileged-access review records."""
    return _load("access_reviews.json")


if __name__ == "__main__":
    mcp.run()
