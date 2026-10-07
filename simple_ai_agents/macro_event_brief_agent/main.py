"""Macro event brief agent.

Builds a pre-trade brief of the scheduled macro releases for one currency:
when each release is due, what the last print was, when it was published and
where it came from. Data comes from the FXMacroData REST API; an optional
Nebius Token Factory model turns the evidence into a short brief in which
every point must cite an evidence ID.

Standard library only.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

FXMD_BASE_URL = "https://api.fxmacrodata.com/v1"
NEBIUS_CHAT_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"
DEFAULT_NEBIUS_MODEL = "Qwen/Qwen3-30B-A3B"
TIMEOUT_SECONDS = 30
MAX_EVENTS = 12
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
USER_AGENT = "awesome-ai-apps-macro-event-brief/1.0"

CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
SLUG_RE = re.compile(r"^[a-z0-9_]{1,64}$")
KEY_RE = re.compile(r"^[!-~]{1,256}$")
EVIDENCE_ID_RE = re.compile(r"^E\d{1,2}$")

Opener = Any  # anything with .open(request, timeout=...)


class BriefError(Exception):
    """An error whose message is safe to print."""


class Secret:
    """Keeps a credential out of repr(), str() and tracebacks."""

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "Secret('***')"

    __str__ = __repr__


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never replay a credential header to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BriefError(f"Refused an HTTP {code} redirect.")


def read_key(name: str, environ: dict[str, str]) -> Secret | None:
    value = environ.get(name, "").strip()
    if not value:
        return None
    if not KEY_RE.match(value):
        raise BriefError(f"{name} contains spaces or control characters.")
    return Secret(value)


def redact(text: str, *keys: Secret | None) -> str:
    for key in keys:
        if key is not None:
            for form in (key.reveal(), json.dumps(key.reveal())[1:-1]):
                text = text.replace(form, "***")
    return text


def http_json(opener: Opener, request: urllib.request.Request, service: str) -> tuple[int, Any]:
    """Send a request and decode a bounded JSON body. Never echoes headers."""
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            status, raw = response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, http.client.HTTPException, ValueError) as error:
        raise BriefError(f"Could not reach {service} ({type(error).__name__}).") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise BriefError(f"{service} response exceeded the size limit.")
    try:
        return status, json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise BriefError(f"{service} returned HTTP {status} with a non-JSON body.") from None


def api_message(body: dict[str, Any]) -> str:
    for field in ("detail", "message", "error"):
        value = body.get(field)
        if isinstance(value, str) and value:
            return value[:300]
    return "request failed"


class FxMacroData:
    def __init__(self, key: Secret | None, opener: Opener, base_url: str = FXMD_BASE_URL) -> None:
        parts = urllib.parse.urlsplit(base_url)
        if parts.scheme != "https" or not parts.hostname:
            raise BriefError("FXMacroData base URL must be https:// with a host.")
        self.key = key
        self.opener = opener
        self.base_url = base_url.rstrip("/")
        self.notices: list[str] = []

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(params)}"
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if self.key is not None:
            headers["X-API-Key"] = self.key.reveal()
        status, body = http_json(self.opener, urllib.request.Request(url, headers=headers), "FXMacroData")
        if not isinstance(body, dict):
            raise BriefError(f"FXMacroData returned HTTP {status} with an unexpected body.")
        if status != 200 or "error" in body or "detail" in body:
            raise BriefError(redact(f"FXMacroData HTTP {status}: {api_message(body)}", self.key))
        if not isinstance(body.get("data"), list):
            raise BriefError("FXMacroData response has no data list.")
        self._collect_notices(body)
        return body

    def _collect_notices(self, body: dict[str, Any]) -> None:
        for field in ("freemium_delay", "freemium_window"):
            item = body.get(field)
            message = item.get("message") if isinstance(item, dict) and item.get("applied") else None
            if isinstance(message, str) and message not in self.notices:
                self.notices.append(message)

    def calendar(self, currency: str, start: date, end: date) -> list[dict[str, Any]]:
        params = {"start_date": start.isoformat(), "end_date": end.isoformat()}
        return self.get(f"/calendar/{currency}", params)["data"]

    def latest(self, currency: str, indicator: str) -> dict[str, Any] | None:
        rows = self.get(f"/announcements/{currency}/{indicator}", {"limit": 1})["data"]
        return rows[0] if rows and isinstance(rows[0], dict) else None


def upcoming_events(rows: list[Any], max_tier: int) -> list[dict[str, Any]]:
    """Scheduled releases at or above the requested tier, soonest first."""
    events = []
    for row in rows:
        if not isinstance(row, dict) or not SLUG_RE.match(str(row.get("release", ""))):
            continue
        tier = row.get("market_tier")
        if isinstance(tier, int) and tier <= max_tier and isinstance(row.get("announcement_datetime"), int):
            events.append(row)
    events.sort(key=lambda row: row["announcement_datetime"])
    return events[:MAX_EVENTS]


def build_evidence(client: FxMacroData, currency: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One record per upcoming release, with the last published value beside it."""
    evidence, latest_cache = [], {}
    for index, event in enumerate(events, start=1):
        slug = event["release"]
        if slug not in latest_cache:
            try:
                latest_cache[slug] = client.latest(currency, slug)
            except BriefError as error:
                latest_cache[slug] = {"error": str(error)}
        last = latest_cache[slug] or {}
        evidence.append({
            "id": f"E{index}",
            "release": slug,
            "name": event.get("name") or slug,
            "importance": event.get("event_importance"),
            "scheduled_utc": event.get("announcement_datetime_utc"),
            "scheduled_local": event.get("announcement_datetime_local"),
            "reference_period": event.get("reference_period") or event.get("date"),
            "last_value": last.get("val"),
            "last_reference_date": last.get("date"),
            "last_published_local": last.get("announcement_datetime_local"),
            "previous_value": last.get("previous_value"),
            "source_url": last.get("source_url") or event.get("source_url"),
            "unavailable": last.get("error"),
        })
    return evidence


def synthesis_messages(currency: str, evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    system = (
        "You write short pre-trade macro briefs for FX traders. Use only the evidence records "
        "provided. Every point must cite one or more evidence IDs such as E1. Do not invent "
        "forecasts, consensus figures or values that are not in the evidence. Reply with JSON "
        'only: {"summary": str, "points": [{"text": str, "evidence": [str]}], "caveats": [str]}.'
    )
    user = json.dumps({"currency": currency.upper(), "evidence": evidence}, ensure_ascii=False)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_model_json(content: str) -> Any:
    text = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except ValueError:
        raise BriefError("The model did not return valid JSON.") from None


def check_point(point: Any, evidence_ids: set[str]) -> dict[str, Any]:
    """A point must have text and cite only evidence IDs that exist."""
    if not isinstance(point, dict) or not isinstance(point.get("text"), str):
        raise BriefError("The model returned a point without text.")
    cites = point.get("evidence")
    if not isinstance(cites, list) or not cites:
        raise BriefError("The model returned a point without evidence.")
    for cite in cites:
        if not isinstance(cite, str) or not EVIDENCE_ID_RE.match(cite) or cite not in evidence_ids:
            raise BriefError("The model cited evidence that does not exist.")
    return {"text": point["text"].strip(), "evidence": cites}


def validate_synthesis(payload: Any, evidence_ids: set[str]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("summary"), str):
        raise BriefError("The model returned an invalid summary.")
    points = payload.get("points")
    caveats = payload.get("caveats", [])
    if not isinstance(points, list) or not isinstance(caveats, list):
        raise BriefError("The model returned invalid points or caveats.")
    checked = [check_point(point, evidence_ids) for point in points]
    return {
        "summary": payload["summary"].strip(),
        "points": checked,
        "caveats": [c.strip() for c in caveats if isinstance(c, str)],
        "verification": "unverified model output; check each cited record",
    }


def synthesize(
    key: Secret | None, model: str, currency: str, evidence: list[dict[str, Any]], opener: Opener
) -> dict[str, Any]:
    if key is None:
        raise BriefError("NEBIUS_API_KEY is not set; use --no-synthesis for an evidence-only brief.")
    body = json.dumps({"model": model, "temperature": 0, "messages": synthesis_messages(currency, evidence)})
    request = urllib.request.Request(
        NEBIUS_CHAT_URL,
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key.reveal()}", "User-Agent": USER_AGENT},
        method="POST",
    )
    status, payload = http_json(opener, request, "Nebius")
    if status != 200 or not isinstance(payload, dict):
        raise BriefError(f"Nebius rejected the request (HTTP {status}).")
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise BriefError("Nebius returned an unexpected response shape.") from None
    if not isinstance(content, str):
        raise BriefError("Nebius returned an unexpected response shape.")
    return validate_synthesis(parse_model_json(content), {item["id"] for item in evidence})


def fmt(value: Any) -> str:
    return "n/a" if value is None else str(value)


def render_markdown(currency: str, evidence: list[dict[str, Any]], notices: list[str], brief: dict[str, Any] | None) -> str:
    lines = [f"# {currency.upper()} macro event brief", ""]
    if brief:
        lines += ["## Brief (model output, unverified)", "", brief["summary"], ""]
        lines += [f"- {p['text']} [{', '.join(p['evidence'])}]" for p in brief["points"]]
        lines += [f"- Caveat: {c}" for c in brief["caveats"]] + [""]
    lines += ["## Scheduled releases", ""]
    if not evidence:
        lines.append("No scheduled releases at this tier in the window.")
    else:
        lines += ["| ID | Release | Due (local) | Period | Last value | Last published | Source |", "|---|---|---|---|---|---|---|"]
        for item in evidence:
            last = fmt(item["last_value"]) if not item["unavailable"] else "unavailable"
            lines.append(
                f"| {item['id']} | {item['name']} | {fmt(item['scheduled_local'])} | {fmt(item['reference_period'])} "
                f"| {last} | {fmt(item['last_published_local'])} | {fmt(item['source_url'])} |"
            )
    if notices:
        lines += ["", "## Data notices", ""] + [f"- {n}" for n in notices]
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pre-trade brief of scheduled macro releases.")
    parser.add_argument("--currency", default="usd", help="3-letter code; USD works without an FXMacroData key")
    parser.add_argument("--days", type=int, default=7, help="look-ahead window, 1-31 days")
    parser.add_argument("--max-tier", type=int, default=2, choices=(1, 2, 3), help="1 = only the biggest releases")
    parser.add_argument("--model", default=os.environ.get("NEBIUS_MODEL", DEFAULT_NEBIUS_MODEL))
    parser.add_argument("--no-synthesis", action="store_true", help="skip the model and print the evidence only")
    parser.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    return parser.parse_args(argv)


def run(args: argparse.Namespace, environ: dict[str, str], opener: Opener, today: date) -> tuple[dict[str, Any], tuple]:
    if not CURRENCY_RE.match(args.currency.strip()):
        raise BriefError("--currency must be a 3-letter code such as usd.")
    if not 1 <= args.days <= 31:
        raise BriefError("--days must be between 1 and 31.")
    currency = args.currency.strip().lower()
    fxmd_key = read_key("FXMACRODATA_API_KEY", environ)
    nebius_key = None if args.no_synthesis else read_key("NEBIUS_API_KEY", environ)
    client = FxMacroData(fxmd_key, opener)
    events = upcoming_events(client.calendar(currency, today, today + timedelta(days=args.days)), args.max_tier)
    evidence = build_evidence(client, currency, events)
    brief = None
    if not args.no_synthesis and evidence:
        brief = synthesize(nebius_key, args.model, currency, evidence, opener)
    result = {"currency": currency, "evidence": evidence, "notices": client.notices, "brief": brief}
    return result, (fxmd_key, nebius_key)


def main(
    argv: list[str] | None = None,
    environ: dict[str, str] | None = None,
    opener: Opener | None = None,
    today: date | None = None,
    out: Callable[[str], Any] | None = None,
) -> int:
    args = parse_args(argv)
    write = out or sys.stdout.write
    try:
        result, keys = run(args, dict(os.environ if environ is None else environ),
                     opener or urllib.request.build_opener(NoRedirect),
                     today or datetime.now(timezone.utc).date())
        if args.json:
            text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        else:
            text = render_markdown(result["currency"], result["evidence"], result["notices"], result["brief"])
        write(redact(text, *keys))
        return 0
    except BriefError as error:
        sys.stderr.write(f"error: {error}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
