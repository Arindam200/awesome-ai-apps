"""Thin, transparent client for the Toolbox HTTP API + Keycloak token endpoint.

The deterministic demo endpoints use this (rather than the SDK) so the talk can
show the exact wire-level security: the user's OIDC token travels in the
`keycloak_token` header, and Toolbox — not the caller — decides identity.
"""
import base64
import json
import os

import httpx

TOOLBOX_URL = os.environ.get("TOOLBOX_URL", "http://127.0.0.1:5000")
KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://127.0.0.1:8080")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "grocery")
KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "grocery-agent")

CUSTOMER_HEADER = "keycloak_token"
ADMIN_HEADER = "keycloak_admin_token"


def login(username: str, password: str) -> str:
    """Resource-owner password grant (demo only). Returns an access token."""
    url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    resp = httpx.post(
        url,
        data={
            "client_id": KEYCLOAK_CLIENT_ID,
            "grant_type": "password",
            "username": username,
            "password": password,
        },
        timeout=15.0,
    )
    if resp.status_code != 200:
        raise ValueError(f"login failed: {resp.json().get('error_description', resp.text)}")
    return resp.json()["access_token"]


def decode_claims(token: str) -> dict:
    """Decode (without verifying) a JWT payload — for displaying who is logged in."""
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def invoke(tool: str, params: dict | None = None, token: str | None = None, admin: bool = False):
    """Call a Toolbox tool over HTTP. Returns (http_status, parsed_result_or_error).

    The token (if any) is sent in the header Toolbox expects for that authService:
    `keycloak_token` for customer tools, `keycloak_admin_token` for admin tools.
    """
    headers = {}
    if token:
        headers[ADMIN_HEADER if admin else CUSTOMER_HEADER] = token
    resp = httpx.post(
        f"{TOOLBOX_URL}/api/tool/{tool}/invoke",
        json=params or {},
        headers=headers,
        timeout=30.0,
    )
    body = resp.json()
    if resp.status_code != 200:
        return resp.status_code, {"error": body.get("error", body)}
    # success body is {"result": "<json-encoded string>"}
    result = body.get("result")
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            # tool-level SQL errors come back as {"error": "..."} inside result
            if isinstance(parsed, dict) and "error" in parsed:
                return 200, {"error": parsed["error"]}
            return 200, parsed
        except json.JSONDecodeError:
            return 200, result
    return 200, result
