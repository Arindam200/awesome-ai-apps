"""Security connector: OSV.dev queries per package. No key needed."""

import logging
from datetime import datetime

import httpx

from app.connectors.base import RawItem

logger = logging.getLogger(__name__)

OSV_QUERY = "https://api.osv.dev/v1/query"


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch(project_config: dict, since: datetime) -> list[RawItem]:
    security = project_config.get("security") or {}
    packages = security.get("package_names") or []
    ecosystems = security.get("osv_ecosystems") or ["Go"]
    items: list[RawItem] = []

    with httpx.Client(timeout=30.0) as client:
        for pkg in packages:
            for eco in ecosystems:
                try:
                    resp = client.post(OSV_QUERY, json={"package": {"name": pkg, "ecosystem": eco}})
                    resp.raise_for_status()
                    vulns = resp.json().get("vulns", [])
                except Exception:
                    logger.exception("OSV query failed for %s (%s)", pkg, eco)
                    continue

                for v in vulns:
                    modified = _parse_dt(v.get("modified"))
                    if modified and modified < since:
                        continue
                    severity = "unknown"
                    for sev in v.get("severity", []):
                        severity = sev.get("score", severity)
                    items.append(
                        RawItem(
                            source_kind="osv",
                            source_url=f"https://osv.dev/vulnerability/{v['id']}",
                            title=f"{v['id']}: {v.get('summary', 'security advisory')}",
                            body=(v.get("details") or "")[:2000],
                            observed_at=modified or _parse_dt(v.get("published")),
                            extra={"vuln_id": v["id"], "package": pkg, "severity": severity,
                                   "aliases": v.get("aliases", [])},
                        )
                    )

    logger.info("osv: %d raw items", len(items))
    return items
