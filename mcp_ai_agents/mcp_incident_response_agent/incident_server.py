"""Local mock MCP server exposing alerts, service status and runbook search.

All data comes from the JSON/markdown fixtures in ./data, so no external
accounts or credentials are needed.
"""
import json
import re
from pathlib import Path

from fastmcp import FastMCP

DATA = Path(__file__).parent / "data"
mcp = FastMCP("incident-response")


def _load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@mcp.tool()
def list_alerts(service: str = "", status: str = "firing") -> list[dict]:
    """List alerts. Optionally filter by service name and status (firing/resolved)."""
    alerts = _load("alerts.json")
    if service:
        alerts = [a for a in alerts if a["service"] == service]
    if status:
        alerts = [a for a in alerts if a["status"] == status]
    return alerts


@mcp.tool()
def get_service_status(service: str) -> dict:
    """Return health, owner, dependencies and last deploy time for a service."""
    services = _load("services.json")
    if service not in services:
        return {"error": f"unknown service '{service}'", "known": sorted(services)}
    return {"service": service, **services[service]}


@mcp.tool()
def search_runbooks(query: str, limit: int = 3) -> list[dict]:
    """Keyword search over the runbook markdown files. Returns best matches first."""
    terms = set(re.findall(r"[a-z0-9\-]+", query.lower()))
    results = []
    for path in sorted((DATA / "runbooks").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        words = set(re.findall(r"[a-z0-9\-]+", text.lower()))
        score = len(terms & words)
        if score:
            results.append({"runbook": path.stem, "score": score, "content": text})
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


if __name__ == "__main__":
    mcp.run()
