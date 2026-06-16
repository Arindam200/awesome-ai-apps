"""Grocery demo web app — the visible surface for the MCP Toolbox security story.

Routes:
  GET  /                     single-page UI
  POST /api/login            Keycloak password grant -> server session (alice/bob/carol)
  POST /api/logout
  GET  /api/me               who is signed in (from token claims)
  POST /api/chat             talk to the ADK + Gemini agent (uses the Toolbox SDK)
  GET  /api/cart             view_cart           (scoped to the session user by Toolbox)
  GET  /api/orders           list_my_orders
  POST /api/order            get_order_details    (the cross-user demo calls this)
  GET  /api/demo/schema      proves `username` is bound, not model-supplied
  POST /api/admin/all-orders view_all_orders      (admin-only; needs grocery-admin aud)
"""
import os
import secrets
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from web import toolbox_http as tb

HERE = os.path.dirname(__file__)
app = FastAPI(title="Online Groceries — MCP Toolbox security demo")

# Tiny in-memory session store: sid -> {token, username, is_admin}. Demo-only.
_SESSIONS: dict[str, dict] = {}


def _session(request: Request) -> dict | None:
    return _SESSIONS.get(request.cookies.get("sid", ""))


def _require(request: Request):
    s = _session(request)
    if not s:
        return None, JSONResponse({"error": "not signed in"}, status_code=401)
    return s, None


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@app.post("/api/login")
async def login(request: Request, response: Response):
    body = await request.json()
    username, password = body.get("username", ""), body.get("password", "")
    try:
        token = tb.login(username, password)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=401)
    claims = tb.decode_claims(token)
    aud = claims.get("aud", [])
    is_admin = "grocery-admin" in (aud if isinstance(aud, list) else [aud])
    sid = secrets.token_urlsafe(16)
    _SESSIONS[sid] = {
        "token": token,
        "username": claims.get("preferred_username", username),
        "is_admin": is_admin,
    }
    response.set_cookie("sid", sid, httponly=True, samesite="lax")
    return {"username": _SESSIONS[sid]["username"], "is_admin": is_admin}


@app.post("/api/logout")
async def logout(request: Request, response: Response):
    _SESSIONS.pop(request.cookies.get("sid", ""), None)
    response.delete_cookie("sid")
    return {"ok": True}


@app.get("/api/me")
async def me(request: Request):
    s = _session(request)
    if not s:
        return {"signed_in": False}
    return {"signed_in": True, "username": s["username"], "is_admin": s["is_admin"]}


# --------------------------------------------------------------------------- #
# Customer data — every call is scoped to the session user BY TOOLBOX, not by us.
# We never send a username; Toolbox derives it from the token.
# --------------------------------------------------------------------------- #
@app.get("/api/cart")
async def cart(request: Request):
    s, err = _require(request)
    if err:
        return err
    _, data = tb.invoke("view_cart", {}, token=s["token"])
    return {"items": data}


@app.get("/api/orders")
async def orders(request: Request):
    s, err = _require(request)
    if err:
        return err
    _, data = tb.invoke("list_my_orders", {}, token=s["token"])
    return {"orders": data}


@app.post("/api/checkout")
async def checkout(request: Request):
    """Place an order from the current user's cart (deterministic — no LLM)."""
    s, err = _require(request)
    if err:
        return err
    status, data = tb.invoke("checkout", {}, token=s["token"])
    return {"result": data}


@app.post("/api/order")
async def order_details(request: Request):
    """get_order_details. The cross-user demo posts another user's order_id here;
    Toolbox scopes the query to the signed-in user, so it comes back empty."""
    s, err = _require(request)
    if err:
        return err
    body = await request.json()
    order_id = int(body.get("order_id", 0))
    status, data = tb.invoke("get_order_details", {"order_id": order_id}, token=s["token"])
    blocked = isinstance(data, list) and len(data) == 0
    return {
        "order_id": order_id,
        "items": data,
        "blocked": blocked,
        "explanation": (
            "Blocked: `username` is an authenticated parameter bound from your token. "
            "The query ran as YOU, so another user's order returns zero rows — the "
            "agent cannot request it."
        ) if blocked else "",
    }


# --------------------------------------------------------------------------- #
# Admin — requires a token carrying the grocery-admin audience (carol only).
# --------------------------------------------------------------------------- #
@app.post("/api/admin/all-orders")
async def all_orders(request: Request):
    s, err = _require(request)
    if err:
        return err
    status, data = tb.invoke("view_all_orders", {}, token=s["token"], admin=True)
    if status != 200:
        return JSONResponse(
            {"error": data.get("error", "denied"),
             "note": "Your token lacks the grocery-admin audience. Only admins can call this."},
            status_code=status,
        )
    return {"orders": data}


# --------------------------------------------------------------------------- #
# The schema proof: the model NEVER sees `username` / `store_region`.
# --------------------------------------------------------------------------- #
@app.get("/api/demo/schema")
async def demo_schema():
    """Contrast the raw Toolbox manifest (username present, annotated as an
    authenticated parameter) with the function signature the LLM actually sees
    (username absent)."""
    import inspect

    import httpx

    # Raw manifest from Toolbox: username is listed but annotated authServices.
    manifest = {}
    try:
        r = httpx.get(f"{tb.TOOLBOX_URL}/api/toolset/customer-toolset", timeout=10.0)
        for name, spec in r.json().get("tools", {}).items():
            manifest[name] = [
                {"name": p["name"], "authServices": p.get("authServices")}
                for p in spec.get("parameters", [])
            ]
    except Exception as e:  # noqa: BLE001
        manifest = {"error": str(e)}

    # Model-facing signatures from the SDK-loaded agent tools.
    signatures = {}
    try:
        from agent.agent import _load_customer_tools

        for t in _load_customer_tools():
            name = getattr(t, "__name__", repr(t))
            try:
                signatures[name] = str(inspect.signature(t))
            except (TypeError, ValueError):
                signatures[name] = "(callable)"
    except Exception as e:  # noqa: BLE001
        signatures = {"error": str(e)}

    return {
        "toolbox_manifest_parameters": manifest,
        "model_facing_signatures": signatures,
        "takeaway": "Toolbox knows `username` (bound from the OIDC token); the model's "
                    "function signature does not contain it. The agent cannot pass it.",
    }


# --------------------------------------------------------------------------- #
# Chat — the ADK + Gemini agent (uses the Toolbox SDK + authenticated params).
# Lazily initialised so the app boots even without GOOGLE_API_KEY.
# --------------------------------------------------------------------------- #
_runner = None
_session_service = None


def _get_runner():
    global _runner, _session_service
    if _runner is None:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        from agent.agent import root_agent

        _session_service = InMemorySessionService()
        _runner = Runner(agent=root_agent, app_name="grocery", session_service=_session_service)
    return _runner


@app.post("/api/chat")
async def chat(request: Request):
    s, err = _require(request)
    if err:
        return err
    from agent import config as agent_config

    # The agent LLM key (Nebius by default). The security demo endpoints don't
    # need any LLM; only chat does.
    if agent_config.AGENT_PROVIDER == "nebius" and not agent_config.NEBIUS_API_KEY:
        return JSONResponse(
            {"error": "NEBIUS_API_KEY is not set, so the LLM chat is unavailable. The "
                      "security demo endpoints (cart, orders, cross-user, schema, admin) "
                      "work without it."},
            status_code=503,
        )
    if agent_config.AGENT_PROVIDER == "gemini" and not os.environ.get("GOOGLE_API_KEY") \
            and not os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"):
        return JSONResponse(
            {"error": "GOOGLE_API_KEY is not set, so the LLM chat is unavailable."},
            status_code=503,
        )
    body = await request.json()
    message = body.get("message", "")

    from google.genai import types

    from agent.agent import current_token

    # Bind THIS user's token for the duration of the agent run. Toolbox uses it to
    # resolve `username` for every authenticated tool the agent calls.
    token_ctx = current_token.set(s["token"])
    try:
        runner = _get_runner()
        user_id = s["username"]
        session_id = request.cookies.get("sid", "default")
        try:
            await _session_service.create_session(
                app_name="grocery", user_id=user_id, session_id=session_id
            )
        except Exception:  # session already exists
            pass
        content = types.Content(role="user", parts=[types.Part(text=message)])
        reply = ""
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content
        ):
            if event.is_final_response() and event.content and event.content.parts:
                reply = event.content.parts[0].text or reply
        return {"reply": reply}
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"agent error: {e}"}, status_code=500)
    finally:
        current_token.reset(token_ctx)


# --------------------------------------------------------------------------- #
# Static UI
# --------------------------------------------------------------------------- #
@app.get("/")
async def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
