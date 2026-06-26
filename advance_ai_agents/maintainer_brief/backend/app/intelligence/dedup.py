"""Dedup keys. Cross-source convergence is deliberately NOT deduped —
the same feature on GitHub and in a deck is signal; Claude clusters it."""

import hashlib
import re


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def api_dedup_key(source_kind: str, canonical_url: str) -> str:
    return hashlib.sha256(f"{source_kind}|{canonical_url}".encode()).hexdigest()


def document_dedup_key(document_id: int, signal_type: str, title: str) -> str:
    return hashlib.sha256(f"doc:{document_id}|{signal_type}|{_norm(title)}".encode()).hexdigest()
