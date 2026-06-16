# Architecture

## Components

| Component | Role |
|---|---|
| **agent-web** (FastAPI + Google ADK) | The user-facing app + shopping agent. The LLM is **pluggable** — Nebius Token Factory (Kimi-K2.6) by default via ADK's LiteLLM adapter, or Gemini (`AGENT_PROVIDER=gemini`). Loads Toolbox tools via the `toolbox-core` SDK. Lives **outside** the trust boundary, so the provider choice changes no security property. Gemini is still used for query embeddings (semantic search). |
| **MCP Toolbox** | The security control plane. Serves curated tools over HTTP/MCP; binds identity from tokens; holds the DB credentials; emits OpenTelemetry. |
| **PostgreSQL** | System of record: users, product catalog (price/stock), carts, orders. Accessed only via least-privilege roles. |
| **MongoDB (Atlas Local)** | Vector/semantic product search over pre-computed Gemini embeddings (`$vectorSearch`). |
| **Keycloak** | OIDC identity provider (local). Issues the JWTs Toolbox validates. Swapped for Google Sign-In in production. |
| **OTel Collector + Jaeger** | Traces/metrics pipeline. |

## The trust boundary

```
        ┌─────────────────────────────────────┐
 login  │  agent-web (FastAPI)                 │
 alice  │  ├─ Google ADK + Gemini agent        │   tool calls (HTTP/MCP)
 bob    │  └─ deterministic demo endpoints     │──────────────┐
 carol  └──────────────┬──────────────────────┘   keycloak_token (JWT)
                       │ embeddings (Gemini)                   │
                       ▼                                       ▼
                 google-genai                       ╔════════════════════╗
                                                     ║   MCP  TOOLBOX     ║  ◀── TRUST BOUNDARY
   Keycloak (OIDC) ──issues JWT──────────────────▶  ║  • custom tools     ║
        ▲                                            ║  • authN params     ║
        └── agent-web logs users in (server-side)    ║  • authRequired     ║
                                                     ║  • parameterized    ║
                                                     ║  • least-priv roles ║
                                                     ╚═══╤═══════════╤═════╝
                                  parameterized SQL ($1) │           │ $vectorSearch
                                   role: toolbox_app/admin▼           ▼
                                              ┌───────────┐     ┌──────────┐
                                              │ PostgreSQL│     │ MongoDB  │
                                              └───────────┘     └──────────┘
```

Everything to the left of the double line is **untrusted** with respect to the
data: the LLM, its prompt, and the tool arguments it produces. All enforcement
happens at Toolbox and in the database.

## Request lifecycle (e.g. "show my orders")

1. The browser calls agent-web; the server attaches the signed-in user's JWT.
2. The agent (or a deterministic endpoint) calls the Toolbox tool `list_my_orders`.
   The token travels in the `keycloak_token` header. **No `username` is sent** —
   the tool's schema doesn't have one.
3. Toolbox validates the JWT against the OIDC issuer (signature, issuer,
   audience), extracts `preferred_username`, and binds it into the SQL parameter.
4. Toolbox runs `... WHERE u.username = $1` as the least-privilege `toolbox_app`
   role, returns rows, and records a trace span.
5. A different user's data is unreachable: the model can't pass `username`, and
   even a forged body value is ignored (the claim wins).

## Why polyglot (Postgres + Mongo)

Transactional integrity (orders, carts, prices, least-privilege roles, IAM) lives
in PostgreSQL; semantic search lives in MongoDB vector search. Toolbox presents
**one** secure gateway over both, joined by `sku`. This shows the control plane
generalizing across very different datastores — a realistic production shape.

## Local vs. GKE

| Concern | Local (compose) | GKE (`deploy/k8s/`) |
|---|---|---|
| Postgres source | `kind: postgres` + password | `kind: cloud-sql-postgres`, **no password** (IAM) |
| DB auth | role password in `.env` | Workload Identity KSA→GSA, IAM DB users |
| `tools.yaml` | bind-mounted file | mounted from a Secret |
| Secrets | `.env` | Secret Manager (CSI / External Secrets) |
| Network | compose bridge | NetworkPolicy: agent→Toolbox→DB only |
| Telemetry | `--telemetry-otlp` → collector | `--telemetry-gcp` → Cloud Trace/Monitoring |
| Identity | local Keycloak | Google Sign-In (`authService: kind: google`) |
| Scaling | single container | HPA 2–10, built-in connection pooling |

The **tools, authenticated parameters, and roles are identical** across both —
only the `sources:` block changes (`deploy/k8s/tools.yaml` is generated from
`toolbox/tools.yaml`).

## Catalog data flow

`scripts/build_catalog.py` streams `grocery_store.inventory.json` (70 MB of
products with Gemini embeddings), assigns SKUs, and loads an **aligned** catalog
into Postgres (price/stock) and Mongo (embeddings + `sku`), then builds the
`vector_index`. This guarantees a product returned by vector search exists, with
an authoritative price, in Postgres.
