# Security model — how MCP Toolbox constrains the agent

The agent is treated as **untrusted**. Ten mechanisms, layered, ensure that no
prompt, jailbreak, or malformed tool argument lets it exceed its authority. Each
is implemented in this repo and verified by `scripts/verify_security.sh`.

## Mechanism map

| # | Mechanism | Where | What it stops |
|---|---|---|---|
| 1 | **Custom tools, not `execute_sql`** | `toolbox/tools.yaml` — only 10 named tools; the Mongo vector index/path are hardcoded | The agent never has arbitrary query power; the attack surface is the tool list |
| 2 | **Authenticated parameters** | `tools.yaml` — `username` carries `authServices:[{name: keycloak, field: preferred_username}]` | The model can't request another user's data; `username` isn't even in its tool schema |
| 3 | **Authorized invocations** | `tools.yaml` — admin tools have `authRequired:[keycloak_admin]` | Non-admins can't call `view_all_orders` / `update_inventory` |
| 4 | **Bound parameters (SDK)** | `agent/agent.py` — `bound_params={"store_region": ...}` | The model can't choose the tenant/region; it's fixed by the app |
| 5 | **Parameterized queries** | `tools.yaml` — every statement uses `$1..$n` (no string interpolation) | SQL injection; tool args are values, never SQL |
| 6 | **Least-privilege DB roles** | `db/postgres/01_roles.sql` — `toolbox_app` / `toolbox_admin`, one per source | A compromised tool can't DROP/UPDATE-catalog/DELETE-orders |
| 7 | **IAM / Workload Identity** | `deploy/k8s/` — `cloud-sql-postgres` with no password; KSA→GSA | No DB password exists in the cluster at all |
| 8 | **Secrets handling** | `${ENV}` in `tools.yaml`; `.env` (local) / Secret Manager (GKE) | Credentials never reach the model and aren't hardcoded |
| 9 | **Observability** | `--telemetry-otlp` / `--telemetry-gcp`; `observability/` | Every tool call is an audited, traced event |
| 10 | **Network hardening** | `--allowed-hosts` / `--allowed-origins`; `deploy/k8s/networkpolicy.yaml` | Only agent→Toolbox→DB; the agent can't reach the DB directly |

## The headline: authenticated parameters (#2)

The `view_cart` tool is defined with a single parameter that the model never sees:

```yaml
parameters:
  - name: username
    type: string
    authServices:
      - name: keycloak
        field: preferred_username   # taken from the verified token, not the model
```

Verified behavior (from the running stack):

- The model-facing signature is `view_cart() -> str` — **no `username`**.
  (`add_to_cart(quantity, sku)`, `get_order_details(order_id)` — same story.)
- Calling `view_cart` with a body of `{"username":"bob"}` while presenting
  alice's token **still returns alice's cart**. The forged value is ignored; the
  claim wins.
- Calling it with **no token → HTTP 401** ("error parsing authenticated
  parameter"). Identity isn't optional.
- `get_order_details(order_id=<bob's>)` as alice → **zero rows**. Ownership is in
  the `WHERE` clause against the authenticated username; it can't be bypassed.

This is the difference between *asking the model nicely* and *making it
impossible*: identity is resolved deterministically by the server, below the
agent.

## Admin gating is role-driven, not request-driven (#3)

`view_all_orders` and `update_inventory` use `authRequired: [keycloak_admin]`,
whose audience is `grocery-admin`. In Keycloak, only **carol** holds the
`grocery-admin` client role, so the built-in *audience-resolve* mapper adds that
audience to her token automatically. alice/bob can't obtain it — even requesting
the scope explicitly is rejected ("Invalid scopes"). Verified: alice → 401,
carol → 200.

> **Honest caveat (the confused-deputy lesson):** bound parameters (#4) and the
> app's choice of *which* token/header to send are trusted to the application
> layer. Toolbox stops the *model*; your app process must still be trustworthy.
> Call this out — it's the same lesson the MCP Toolbox docs flag for bound params.

## Defense in depth below the tools (#6)

Even if a tool were subverted, the database role caps the blast radius. `toolbox_app`
holds `SELECT` on `products` and `SELECT/INSERT` on `orders` — and nothing more:

```
UPDATE products ...  → permission denied
DELETE FROM orders   → permission denied
DROP TABLE orders    → must be owner of table
```

## Verifying it yourself

```bash
scripts/verify_security.sh
```

Runs 11 checks inside the stack (tokens minted via `keycloak:8080` so the issuer
matches what Toolbox validates) covering #2, #3, #5, and #6. Traces for every
call appear in Jaeger (#9).

## Production hardening (#7, #8, #10)

On GKE (`deploy/k8s/`): Cloud SQL via Workload Identity means **no DB password in
the cluster**; `tools.yaml` and secrets come from Secret Manager; a NetworkPolicy
ensures only `app=agent-web` can reach Toolbox and only Toolbox can reach the
databases. Swap the `authService` to `kind: google` for Google Sign-In — no other
change.
