#!/usr/bin/env bash
# Verify every MCP Toolbox security control against the running local stack.
# Read-only (except a harmless admin update_inventory that sets stock back).
#
# Probes run INSIDE the agent-web container so OIDC tokens are minted via
# keycloak:8080 (matching the issuer Toolbox validates) and Toolbox is reached
# at toolbox:5000. The least-privilege check runs inside the postgres container.
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f deploy/compose/docker-compose.yaml --env-file deploy/compose/.env"

echo "==================================================================="
echo " MCP Toolbox — security control verification"
echo "==================================================================="

# --- #2/#3 authenticated params, cross-user, admin gating, no-token, injection
${COMPOSE} exec -T agent-web python3 - <<'PY'
import urllib.request, urllib.parse, json
KC="http://keycloak:8080/realms/grocery/protocol/openid-connect/token"
TB="http://toolbox:5000"
def tok(u,pw):
    d=urllib.parse.urlencode({"client_id":"grocery-agent","grant_type":"password","username":u,"password":pw}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(KC,data=d)))["access_token"]
def call(tool, params, header=None):
    req=urllib.request.Request(f"{TB}/api/tool/{tool}/invoke", data=json.dumps(params).encode(), headers={"Content-Type":"application/json"})
    if header: req.add_header(*header)
    try:
        r=urllib.request.urlopen(req); b=json.loads(r.read());
        res=b.get("result");
        try: res=json.loads(res)
        except: pass
        return r.status, res
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()).get("error")
P=0; F=0
def check(name, cond):
    global P,F
    ok="PASS" if cond else "FAIL"
    P+= cond; F+= (not cond)
    print(f"  [{ok}] {name}")

alice=tok("alice","alice123"); bob=tok("bob","bob123"); carol=tok("carol","carol123")

s,a_cart = call("view_cart", {}, ("keycloak_token",alice))
s,b_cart = call("view_cart", {}, ("keycloak_token",bob))
check("#2 view_cart scopes to caller (alice has items, bob empty)", isinstance(a_cart,list) and len(a_cart)>0 and b_cart==[])

# identity cannot be forged via the request body
s,forge = call("view_cart", {"username":"bob"}, ("keycloak_token",alice))
check("#2 body username=bob is IGNORED; still alice's cart", forge==a_cart)

# no token -> rejected
s,_ = call("view_cart", {})
check("#2 view_cart with NO token -> 401", s==401)

# cross-user order read blocked
s,orders=call("list_my_orders", {}, ("keycloak_token",bob))
boid=orders[0]["id"] if orders else None
s,cross=call("get_order_details", {"order_id":boid}, ("keycloak_token",alice))
s,own=call("get_order_details", {"order_id":boid}, ("keycloak_token",bob))
check(f"#2 alice CANNOT read bob's order {boid} (empty)", cross==[])
check(f"#2 bob CAN read his own order {boid}", isinstance(own,list) and len(own)>0)

# admin gating
s,_=call("view_all_orders", {}, ("keycloak_admin_token",alice))
check("#3 alice DENIED admin view_all_orders (401)", s==401)
s,allo=call("view_all_orders", {}, ("keycloak_admin_token",carol))
check("#3 carol ALLOWED admin view_all_orders", s==200 and isinstance(allo,list))

# injection: SQL payload treated as a literal
s,inj=call("get_product_details", {"sku":"x'; DROP TABLE products;--","store_region":"us-west"}, None)
check("#5 SQL-injection SKU returns 0 rows (treated as literal)", inj==[])

print(f"\n  app-layer checks: {P} passed, {F} failed")
import sys; sys.exit(1 if F else 0)
PY

echo "-------------------------------------------------------------------"
echo " #6 least-privilege role (toolbox_app cannot mutate catalog/orders)"
# NB: SQL below avoids string literals so the single-quoted bash here-string
# can't misexpand $-sequences (an earlier `$$` literal expanded to the shell PID).
${COMPOSE} exec -T postgres bash -lc '
run() { PGPASSWORD=app_demo_pw_change_me psql -h localhost -U toolbox_app -d grocery -tAc "$1" 2>&1; }
run "UPDATE products SET stock_qty = stock_qty;"   | grep -q "permission denied" && echo "  [PASS] UPDATE products denied" || echo "  [FAIL] UPDATE products NOT denied"
run "DELETE FROM orders;"                          | grep -q "permission denied" && echo "  [PASS] DELETE orders denied"   || echo "  [FAIL] DELETE orders NOT denied"
run "DROP TABLE orders;"                            | grep -qiE "denied|must be owner" && echo "  [PASS] DROP TABLE denied"  || echo "  [FAIL] DROP TABLE NOT denied"
'

echo "-------------------------------------------------------------------"
echo " #5 parameterized queries: products table still intact"
${COMPOSE} exec -T postgres bash -lc 'PGPASSWORD='"'"'app_demo_pw_change_me'"'"' psql -h localhost -U toolbox_app -d grocery -tAc "SELECT count(*) FROM products;"' | sed 's/^/  products rows = /'

echo "==================================================================="
echo " Done. (Traces for these calls are visible in Jaeger: http://localhost:16686)"
