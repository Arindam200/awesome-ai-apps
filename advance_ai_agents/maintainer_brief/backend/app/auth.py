"""GitHub OAuth + stateless session tokens.

Auth is token-based (Bearer), not cookie-based, to sidestep cross-domain
cookie/third-party-cookie problems between the frontend (…-web.fly.dev) and API
(…-api.fly.dev). Flow:

  1. Frontend sends the browser to  GET /auth/login
  2. We redirect to GitHub's consent screen (with a signed `state`).
  3. GitHub redirects back to  GET /auth/callback?code=…&state=…
  4. We exchange the code, fetch the GitHub user, upsert a User row, mint an
     HMAC-signed session token, and redirect to
     {APP_URL}/auth/callback#token=<token>  (fragment → never logged/sent to server)
  5. The frontend stores the token in localStorage and sends it as
     Authorization: Bearer <token> on every API call.

`current_user` validates that Bearer token on protected routes.
"""

import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import httpx
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_USER = "https://api.github.com/user"

_SEP = "|"


# ── signing (shared shape for session tokens and oauth state) ───────────────

def _sig(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]


def _pack(payload: str, secret: str) -> str:
    raw = payload + _SEP + _sig(payload, secret)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _unpack(token: str, secret: str) -> str | None:
    try:
        pad = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + pad).decode()
        payload, _, sig = raw.rpartition(_SEP)
        if not hmac.compare_digest(sig, _sig(payload, secret)):
            return None
        return payload
    except Exception:
        return None


def mint_session(user_id: int) -> str:
    exp = int(time.time()) + settings.session_ttl_days * 86400
    return _pack(f"{user_id}{_SEP}{exp}", settings.session_secret)


def _read_session(token: str) -> int | None:
    payload = _unpack(token, settings.session_secret)
    if not payload:
        return None
    try:
        uid, exp = payload.split(_SEP)
        if int(exp) < time.time():
            return None
        return int(uid)
    except Exception:
        return None


def make_state() -> str:
    return _pack(str(int(time.time())), settings.session_secret)


def check_state(state: str) -> bool:
    payload = _unpack(state, settings.session_secret)
    if not payload:
        return False
    try:
        return int(payload) > time.time() - 600  # 10 min window
    except Exception:
        return False


# ── OAuth flow ──────────────────────────────────────────────────────────────

def login_url() -> str:
    params = {
        "client_id": settings.github_oauth_client_id,
        "redirect_uri": f"{settings.api_public_url.rstrip('/')}/auth/callback",
        "scope": "read:user user:email",
        "state": make_state(),
        "allow_signup": "true",
    }
    return f"{GITHUB_AUTHORIZE}?{urlencode(params)}"


def exchange_and_upsert(db: Session, code: str) -> User:
    with httpx.Client(timeout=20.0) as client:
        tok = client.post(
            GITHUB_TOKEN,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "code": code,
                "redirect_uri": f"{settings.api_public_url.rstrip('/')}/auth/callback",
            },
        ).json()
        access = tok.get("access_token")
        if not access:
            raise HTTPException(400, f"github token exchange failed: {tok.get('error_description') or tok}")
        gh = client.get(
            GITHUB_USER,
            headers={"Authorization": f"Bearer {access}", "Accept": "application/vnd.github+json"},
        ).json()

    gid = gh.get("id")
    if not gid:
        raise HTTPException(400, "could not read GitHub user")
    user = db.scalar(select(User).where(User.github_id == gid))
    if not user:
        user = User(github_id=gid)
        db.add(user)
    user.login = gh.get("login")
    user.name = gh.get("name")
    user.avatar_url = gh.get("avatar_url")
    user.email = gh.get("email")
    db.commit()
    db.refresh(user)
    return user


def frontend_redirect(token: str) -> str:
    return f"{settings.app_url.rstrip('/')}/auth/callback#token={token}"


# ── dependency ──────────────────────────────────────────────────────────────

def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "not authenticated")
    uid = _read_session(authorization[7:].strip())
    if uid is None:
        raise HTTPException(401, "invalid or expired session")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "user not found")
    return user


def user_public(u: User) -> dict:
    return {"id": u.id, "login": u.login, "name": u.name, "avatar_url": u.avatar_url}
