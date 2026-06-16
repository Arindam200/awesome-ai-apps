from __future__ import annotations

import re


REQUIRED_PLAYABILITY_TERMS = (
    "score",
    "objective",
    "timer",
    "win",
    "lose",
    "restart",
    "reset",
)

BLOCKED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("external script tags are not allowed", re.compile(r"<script[^>]+src\s*=", re.IGNORECASE)),
    ("network calls are not allowed", re.compile(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource)\b", re.IGNORECASE)),
    ("page navigation is not allowed", re.compile(r"\b(window|document)\.location\b|\blocation\.href\b", re.IGNORECASE)),
    ("browser storage is not allowed", re.compile(r"\b(localStorage|sessionStorage|indexedDB)\b", re.IGNORECASE)),
    ("embedded frames or plugins are not allowed", re.compile(r"<\s*(iframe|object|embed)\b", re.IGNORECASE)),
)


def strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    fence_match = re.fullmatch(r"```(?:html)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    return stripped


def validate_generated_html(html: str) -> list[str]:
    issues: list[str] = []
    normalized = html.strip()
    lower = normalized.lower()

    if "<!doctype html" not in lower and "<html" not in lower:
        issues.append("game must be a complete HTML document")

    if "<script" in lower and "</script>" not in lower:
        issues.append("HTML appears truncated: missing closing script tag")

    if "<body" in lower and "</body>" not in lower:
        issues.append("HTML appears truncated: missing closing body tag")

    if "<html" in lower and "</html>" not in lower:
        issues.append("HTML appears truncated: missing closing html tag")

    if "<style" not in lower:
        issues.append("game should include embedded CSS")

    if "<script" not in lower:
        issues.append("game should include embedded JavaScript")

    for message, pattern in BLOCKED_PATTERNS:
        if pattern.search(normalized):
            issues.append(message)

    if not re.search(r"\b(keydown|keyup|pointerdown|pointermove|click|mousemove|touchstart)\b", normalized, re.IGNORECASE):
        issues.append("game must define keyboard, mouse, pointer, or touch controls")

    if not any(term in lower for term in REQUIRED_PLAYABILITY_TERMS):
        issues.append("game must include an objective, score, timer, win/loss state, or restart/reset behavior")

    return issues


def is_safe_generated_html(html: str) -> bool:
    return not validate_generated_html(html)
