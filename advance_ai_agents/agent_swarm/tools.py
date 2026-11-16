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
from urllib.parse import quote, urljoin, urlparse

import httpx
from langchain_core.tools import tool

USER_AGENT = "awesome-ai-apps-agent-swarm/0.1 (https://github.com/Arindam200/awesome-ai-apps)"
WIKI_API = "https://en.wikipedia.org/w/api.php"
MAX_PAGE_CHARS = 6000
MAX_REDIRECTS = 5


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


def _pinned_request(url: str) -> tuple[str, dict, dict]:
    """Resolve the host once, refuse anything non-public, and target the checked IP directly.

    Workers pick URLs themselves and read untrusted pages, so a prompt-injected page
    could point them at local services. Checking DNS and then letting httpx resolve
    the name again would leave a DNS-rebinding gap, so the request connects to the
    exact address that was validated. The Host header and the TLS SNI and certificate
    check still use the original hostname.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("only public http(s) URLs are allowed")
    if parsed.username or parsed.password:
        raise ValueError("URLs with credentials are not allowed")
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addrs = sorted({str(info[4][0]) for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
    if not addrs or not all(ipaddress.ip_address(a).is_global for a in addrs):
        raise ValueError(f"{host} resolves to a non-public address")
    ip = next((a for a in addrs if ":" not in a), addrs[0])  # prefer IPv4
    ip_netloc = f"[{ip}]:{port}" if ":" in ip else f"{ip}:{port}"
    return parsed._replace(netloc=ip_netloc).geturl(), {"Host": parsed.netloc}, {"sni_hostname": host}


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
    current = url
    try:
        with httpx.Client(timeout=20, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
            for _ in range(MAX_REDIRECTS + 1):
                target, headers, extensions = _pinned_request(current)  # re-checked on every hop
                r = client.get(target, headers=headers, extensions=extensions)
                if not (r.is_redirect and r.headers.get("location")):
                    break
                current = urljoin(current, r.headers["location"])
            else:
                raise ValueError("too many redirects")
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
    return f"Source: {current}\n\n{text}"


TOOLS = [wikipedia_search, fetch_url]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
