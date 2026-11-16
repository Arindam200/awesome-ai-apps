"""Keyless research tools the workers can call.

Both tools return plain text, and errors come back as text too, so a failed
lookup never crashes a worker. Tool output is untrusted web content; the worker
prompt tells the model to treat it as data, not instructions.
"""

from __future__ import annotations

import html
import ipaddress
import re
import socket
from urllib.parse import quote, urlparse

import httpx
from langchain_core.tools import tool

USER_AGENT = "awesome-ai-apps-agent-swarm/0.1 (https://github.com/Arindam200/awesome-ai-apps)"
WIKI_API = "https://en.wikipedia.org/w/api.php"
MAX_PAGE_CHARS = 6000


@tool
def wikipedia_search(query: str) -> str:
    """Search English Wikipedia. Returns the intro of the top 3 matching articles with their URLs.
    Use it to check facts, dates, definitions, names and numbers."""
    try:
        with httpx.Client(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
            hits = client.get(
                WIKI_API,
                params={"action": "query", "list": "search", "srsearch": query, "srlimit": 3, "format": "json"},
            ).json()["query"]["search"]
            if not hits:
                return f"No Wikipedia articles found for {query!r}."
            titles = [h["title"] for h in hits]
            pages = client.get(
                WIKI_API,
                params={
                    "action": "query",
                    "prop": "extracts",
                    "exintro": 1,
                    "explaintext": 1,
                    "exlimit": "max",
                    "redirects": 1,
                    "titles": "|".join(titles),
                    "format": "json",
                },
            ).json()["query"]["pages"]
    except Exception as e:
        return f"Wikipedia search failed: {e}"

    extracts = {p.get("title"): (p.get("extract") or "").strip() for p in pages.values()}
    blocks = []
    for title in titles:
        text = extracts.get(title) or "(no summary available)"
        url = "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"))
        blocks.append(f"## {title}\n{url}\n{text[:1500]}")
    return "\n\n".join(blocks)


def _ensure_public(url: str) -> None:
    """Refuse non-HTTP schemes and hosts that resolve to private, loopback or link-local addresses."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("only public http(s) URLs are allowed")
    for info in socket.getaddrinfo(parsed.hostname, None):
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError(f"{parsed.hostname} resolves to a non-public address")


def _html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|svg|head|nav|footer)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr)\s*/?>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


@tool
def fetch_url(url: str) -> str:
    """Fetch a public web page and return its readable text (first ~6000 characters).
    Use it for a specific page you already know the URL of, such as official docs or a Wikipedia article."""
    try:
        _ensure_public(url)
        with httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            event_hooks={"request": [lambda req: _ensure_public(str(req.url))]},
        ) as client:
            r = client.get(url)
        r.raise_for_status()
    except Exception as e:
        return f"Could not fetch {url}: {e}"

    ctype = r.headers.get("content-type", "")
    if "html" in ctype:
        text = _html_to_text(r.text)
    elif ctype.startswith("text/") or "json" in ctype or "xml" in ctype:
        text = r.text
    else:
        return f"{url} returned {ctype or 'unknown content'}, which this tool can't read."
    if len(text) > MAX_PAGE_CHARS:
        text = text[:MAX_PAGE_CHARS] + "\n\n[truncated]"
    return f"Source: {r.url}\n\n{text}"


TOOLS = [wikipedia_search, fetch_url]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
