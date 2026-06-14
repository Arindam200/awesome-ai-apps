"""Central configuration for the grocery agent + web app (env-driven)."""
import os

# Where the MCP Toolbox server is reachable. The agent talks ONLY to Toolbox;
# it never holds a database connection string.
TOOLBOX_URL = os.environ.get("TOOLBOX_URL", "http://127.0.0.1:5000")

# Keycloak (OIDC) — used by the web layer to obtain user tokens via the
# Resource Owner Password grant (demo only; real deployments use the auth-code
# flow / Google Sign-In).
KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://127.0.0.1:8080")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "grocery")
KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "grocery-agent")

# The Toolbox authService names (must match toolbox/tools.yaml). The token header
# Toolbox expects is "<authService>_token".
AUTH_SERVICE = os.environ.get("TOOLBOX_AUTH_SERVICE", "keycloak")
ADMIN_AUTH_SERVICE = os.environ.get("TOOLBOX_ADMIN_AUTH_SERVICE", "keycloak_admin")

# Application-bound parameter (mechanism #4): the store/tenant region. Fixed by
# the application, never chosen by the model.
STORE_REGION = os.environ.get("STORE_REGION", "us-west")

# --- Agent LLM ---------------------------------------------------------------
# The reasoning/tool-calling model. Two providers are supported:
#   nebius  -> any OpenAI-compatible model on Nebius Token Factory (default: Kimi)
#   gemini  -> Google Gemini directly
# The DATABASE security model is identical either way — the LLM is outside the
# trust boundary, so the choice of provider does not affect any guarantee.
AGENT_PROVIDER = os.environ.get("AGENT_PROVIDER", "nebius")   # nebius | gemini
AGENT_MODEL = os.environ.get("AGENT_MODEL", "moonshotai/Kimi-K2.6")
NEBIUS_API_KEY = os.environ.get("NEBIUS_API_KEY", "")
NEBIUS_BASE_URL = os.environ.get(
    "NEBIUS_BASE_URL", "https://api.tokenfactory.us-central1.nebius.com/v1/"
)

# --- Embeddings (semantic search) --------------------------------------------
# Nebius Token Factory has no embedding models, and the inventory vectors are
# Gemini embeddings, so query embedding stays on Gemini regardless of AGENT_PROVIDER.
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "3072"))

# Toolsets defined in tools.yaml.
CUSTOMER_TOOLSET = "customer-toolset"
ADMIN_TOOLSET = "admin-toolset"
