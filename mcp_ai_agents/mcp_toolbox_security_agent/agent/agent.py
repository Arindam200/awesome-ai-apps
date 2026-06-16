"""The grocery shopping agent (Google ADK + Gemini), wired to MCP Toolbox.

Security-relevant design:
  * The agent connects ONLY to Toolbox (config.TOOLBOX_URL). It never holds a DB
    connection string and never sees raw SQL.
  * Per-user identity flows as an OIDC token via a token-getter that reads a
    ContextVar set per request by the web layer. Toolbox binds `username` from
    the token's `preferred_username` claim — so the tool signatures the model
    sees do NOT contain `username` (verified: `view_cart() -> str`,
    `add_to_cart(quantity, sku)`). The model cannot request another user's data.
  * `store_region` is an SDK BOUND parameter (mechanism #4): fixed by the app,
    absent from the model-facing signature.
  * `semantic_product_search` takes a raw 3072-d embedding (not model-suppliable),
    so it is wrapped by `find_similar_products(query)` which embeds server-side
    and calls Toolbox over HTTP.
"""
import contextvars
import json

import httpx
from google.adk.agents import Agent
from toolbox_core import ToolboxSyncClient

from agent import config
from agent.embeddings import generate_embeddings

# Per-request OIDC access token. The web layer sets this before invoking the
# agent; the Toolbox token-getter reads it at tool-call time.
current_token: contextvars.ContextVar[str] = contextvars.ContextVar("oidc_token", default="")


def _token_getter() -> str:
    """Return the current request's OIDC token (sent by Toolbox as the
    `keycloak_token` header to resolve the authenticated `username` parameter)."""
    return current_token.get()


_toolbox = ToolboxSyncClient(config.TOOLBOX_URL)


def find_similar_products(query: str) -> list[dict]:
    """Search the catalog for products matching a free-text query.

    Use this FIRST whenever the user is looking for something. Returns a list of
    products with their `sku`, name, category, brand and price. Pass the returned
    `sku` to other tools (e.g. add_to_cart).

    Args:
        query: What the user is looking for, e.g. "dark chocolate" or "something sweet".
    """
    embedding = generate_embeddings(query)
    # semantic_product_search is public (no auth) and takes a raw embedding, so
    # we call Toolbox directly rather than exposing it as a model tool.
    resp = httpx.post(
        f"{config.TOOLBOX_URL}/api/tool/semantic_product_search/invoke",
        json={"embedding": embedding},
        timeout=30.0,
    )
    resp.raise_for_status()
    result = resp.json().get("result", "[]")
    try:
        return json.loads(result) if isinstance(result, str) else result
    except (json.JSONDecodeError, TypeError):
        return []


def _load_customer_tools() -> list:
    """Load the model-facing customer tools from Toolbox with per-tool auth.

    Each tool is loaded with exactly the auth/bound params it declares — the SDK
    rejects an auth getter a tool does not use, which is itself a nice guardrail.
    """
    auth = {config.AUTH_SERVICE: _token_getter}
    region = {"store_region": config.STORE_REGION}
    tools = [
        # no auth; store_region is application-bound (mechanism #4)
        _toolbox.load_tool("get_product_details", bound_params=region),
        # authenticated username + bound store_region
        _toolbox.load_tool("add_to_cart", auth_token_getters=auth, bound_params=region),
    ]
    # authenticated username only
    for name in ("view_cart", "remove_from_cart", "checkout", "list_my_orders", "get_order_details"):
        tools.append(_toolbox.load_tool(name, auth_token_getters=auth))
    # the semantic-search wrapper (python)
    tools.append(find_similar_products)
    return tools


SYSTEM_PROMPT = """\
You are the Online Groceries Agent, a friendly assistant for an e-commerce grocery store.
Greet the user, introduce yourself, and help them shop.

What you can do:
- Discover products with `find_similar_products` (ALWAYS search before adding to a cart).
- Check authoritative price/stock with `get_product_details` using a product's `sku`.
- Manage the signed-in user's cart: `add_to_cart`, `remove_from_cart`, `view_cart`.
- Place an order with `checkout`, and review orders with `list_my_orders` / `get_order_details`.

Important:
- You operate on behalf of the CURRENTLY SIGNED-IN user. You do not know and cannot
  set their identity — the platform binds it securely. Never ask for a username, and
  never claim you can access another person's cart or orders.
- Always pass the exact `sku` returned by `find_similar_products` to other tools.
- Prices come from the store, never invent one.
- If a search returns nothing, apologise and suggest a different query.
- Stay on the topic of grocery shopping; politely decline unrelated requests.
"""


def _build_model():
    """Resolve the agent LLM. For Nebius (or any OpenAI-compatible endpoint) we
    use ADK's LiteLLM adapter; for Gemini we pass the model id directly."""
    if config.AGENT_PROVIDER == "gemini":
        return config.AGENT_MODEL
    from google.adk.models.lite_llm import LiteLlm

    # The "openai/" prefix routes LiteLLM to the OpenAI-compatible handler and
    # sends the remainder ("moonshotai/Kimi-K2.6") as the model to api_base.
    return LiteLlm(
        model=f"openai/{config.AGENT_MODEL}",
        api_base=config.NEBIUS_BASE_URL,
        api_key=config.NEBIUS_API_KEY,
    )


def build_root_agent() -> Agent:
    return Agent(
        model=_build_model(),
        name="grocery_shopping_agent",
        instruction=SYSTEM_PROMPT,
        tools=_load_customer_tools(),
    )


# ADK entry point (e.g. `adk web`).
root_agent = build_root_agent()
