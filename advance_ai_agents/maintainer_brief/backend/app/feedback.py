"""Signed one-click feedback links for the email.

Each 👍/👎 in the email is a plain GET link carrying an HMAC-signed token, so a
maintainer can rate an item without logging in and nobody can forge a vote. The
recorded votes are the metric the dogfood launch gate reads (design doc §1).
"""

import base64
import hashlib
import hmac

from app.config import settings

_SEP = "|"


def _secret() -> bytes:
    return (settings.feedback_secret or "dev-insecure-change-me").encode()


def _sig(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()[:16]


def sign(brief_id: int, kind: str, ref: str | int, vote: str) -> str:
    payload = _SEP.join([str(brief_id), kind, str(ref), vote])
    raw = payload + _SEP + _sig(payload)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def verify(token: str) -> dict | None:
    try:
        pad = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + pad).decode()
        brief_id, kind, ref, vote, sig = raw.split(_SEP)
        payload = _SEP.join([brief_id, kind, ref, vote])
        if not hmac.compare_digest(sig, _sig(payload)):
            return None
        if vote not in ("up", "down"):
            return None
        return {"brief_id": int(brief_id), "kind": kind, "ref": ref, "vote": vote}
    except Exception:
        return None


def url(brief_id: int, kind: str, ref: str | int, vote: str) -> str:
    base = settings.api_public_url.rstrip("/")
    return f"{base}/feedback?t={sign(brief_id, kind, ref, vote)}"
