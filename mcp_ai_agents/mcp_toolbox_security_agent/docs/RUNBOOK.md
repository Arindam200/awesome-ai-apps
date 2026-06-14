# Live demo runbook

A ~6–8 minute talk demo. Every step has a UI action **and** a CLI fallback you
can run if a slide or click fails.

## Before you go on stage

```bash
scripts/bootstrap_local.sh          # ~3–5 min: build, start, seed catalog
scripts/verify_security.sh          # confirm all 11 checks pass
```

Open tabs: **http://localhost:8080** (UI) and **http://localhost:16687** (Jaeger).
For the live chat, set `NEBIUS_API_KEY` (Kimi-K2.6 agent) and `GOOGLE_API_KEY`
(Gemini embeddings for semantic search) in `deploy/compose/.env`, then
`docker compose ... up -d agent-web`. Otherwise use the deterministic buttons,
which need no API key.

Reset demo state any time:

```bash
docker compose -f deploy/compose/docker-compose.yaml --env-file deploy/compose/.env \
  run --rm catalog          # re-seeds alice's cart + bob's order
```

## The script

**1 — Frame it (30s).** "An agent that can touch a production database is a
security problem. The usual answer is an MCP server with `execute_sql` — the
agent can run anything. We did the opposite: MCP Toolbox gives the agent narrow
tools and becomes the trust boundary." Show `docs/ARCHITECTURE.md` diagram.

**2 — Shop as alice (1m).** Sign in as **alice**. In chat: *"find me some dark
chocolate"* → *"add two of the first one"* → *"check out"*. (No API key? Use the
cart/refresh buttons after running the CLI below.) Point out: the agent passed a
`sku`, never a price or a username.

**3 — Per-user scoping (1m).** Click **Refresh cart / Refresh orders** — alice
sees only her data. Sign in as **bob**: different cart, different orders. Nothing
in the agent or the request said "alice" or "bob" — Toolbox derived it from the
login token.

**4 — The block (1.5m, the centerpiece).** Back as **alice**, in *Cross-user
access test* enter bob's order id (**1**) → **Read order details**. Result: a red
**Blocked** banner, zero rows. "She asked for order 1. Toolbox ran the query as
*her*. `username` is bound from her token — she can't pass it, can't forge it."

CLI fallback / proof:
```bash
# inside the stack so the token issuer matches:
docker compose -f deploy/compose/docker-compose.yaml --env-file deploy/compose/.env \
  exec -T agent-web python3 - <<'PY'
import urllib.request,urllib.parse,json
def tok(u): 
    d=urllib.parse.urlencode({"client_id":"grocery-agent","grant_type":"password","username":u,"password":u+"123"}).encode()
    return json.load(urllib.request.urlopen("http://keycloak:8080/realms/grocery/protocol/openid-connect/token",d))["access_token"]
def call(t,p,h): 
    r=urllib.request.Request(f"http://toolbox:5000/api/tool/{t}/invoke",json.dumps(p).encode(),{"Content-Type":"application/json",h[0]:h[1]})
    return urllib.request.urlopen(r).read().decode()
print("alice -> bob's order:", call("get_order_details",{"order_id":1},("keycloak_token",tok("alice"))))
print("bob   -> bob's order:", call("get_order_details",{"order_id":1},("keycloak_token",tok("bob"))))
PY
```

**5 — Why it's impossible, not just unlikely (1m).** Click **Show tool schemas**.
Contrast: the Toolbox manifest lists `username` annotated `authServices:[keycloak]`,
but the model's function signature is `view_cart()` / `add_to_cart(quantity, sku)`
— **no username**. "The model can't pass what isn't in its schema."

**6 — Admin gating (1m).** As **alice**, click **view_all_orders** → denied. Sign
in as **carol** (admin) → it returns every order. "Same tool, different token.
Only carol's token carries the `grocery-admin` audience — and that's role-driven
in Keycloak, she can't self-grant it."

**7 — It's all audited (45s).** Open **Jaeger** (http://localhost:16687), service
`toolbox`. Show the spans for the calls you just made — including the blocked one
(a successful, audited tool call that returned zero rows, not a silent drop).

**8 — Land the plane (30s).** Recap with `docs/SECURITY.md`: authenticated
parameters, authorized invocations, parameterized queries, least-privilege roles,
IAM/Workload Identity, observability. "Toolbox is the control plane. The agent is
outside the trust boundary — by construction." Show `deploy/k8s/` for the GKE
shape (Workload Identity = no DB password at all).

## One-command proof (if you only have 60 seconds)

```bash
scripts/verify_security.sh
```

11 green checks: authenticated params, the cross-user block, no-token rejection,
admin allow/deny, SQL-injection-as-literal, and three least-privilege denials.

## Troubleshooting

- **Toolbox restarting** — it inits sources + OIDC eagerly; it converges once
  Keycloak's realm is imported (`restart: on-failure`). Give it ~60s after first
  boot. `docker compose ... logs toolbox`.
- **Chat returns 503** — `NEBIUS_API_KEY` isn't set (or `GOOGLE_API_KEY` if
  `AGENT_PROVIDER=gemini`); the security demo still works without it.
- **Chat works but search fails** — semantic search needs `GOOGLE_API_KEY`
  (Gemini query embeddings); cart/checkout/orders still work without it.
- **Token rejected by Toolbox** — only mint tokens *inside* the network
  (`keycloak:8080`); a host-minted token (`localhost:8085`) has a different
  issuer. `scripts/get_token.sh` is for inspecting claims, not calling Toolbox.
- **Port already in use** — published host ports are 8080/5055/8085/16687/8899/
  5544/27117; change them in `deploy/compose/docker-compose.yaml` if needed.
