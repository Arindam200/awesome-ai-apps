#!/usr/bin/env bash
# Bring up the full local stack and seed the catalog. Idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."

CF=deploy/compose/docker-compose.yaml
ENVF=deploy/compose/.env
COMPOSE="docker compose -f ${CF} --env-file ${ENVF}"

if [ ! -f "${ENVF}" ]; then
  echo "• creating ${ENVF} from .env.example"
  cp deploy/compose/.env.example "${ENVF}"
fi

echo "• building + starting services (postgres, mongo, keycloak, toolbox, otel, jaeger, agent-web)"
${COMPOSE} up -d --build

echo -n "• waiting for Toolbox API "
for i in $(seq 1 90); do
  if curl -sf http://localhost:5055/ >/dev/null 2>&1; then echo " ready"; break; fi
  echo -n "."; sleep 2
done

echo "• seeding catalog from grocery_store.inventory.json (this loads Postgres + Mongo + vector index)"
${COMPOSE} run --rm catalog

echo -n "• waiting for web app "
for i in $(seq 1 45); do
  if curl -sf http://localhost:8080/ >/dev/null 2>&1; then echo " ready"; break; fi
  echo -n "."; sleep 2
done

cat <<'EOF'

============================================================
  Online Groceries demo is up.

  Web UI    : http://localhost:8080      (sign in: alice / bob / carol)
  Passwords : alice123 / bob123 / carol123  (carol is admin)
  Toolbox   : http://localhost:5055
  Keycloak  : http://localhost:8085       (admin / admin)
  Jaeger    : http://localhost:16687      (traces)

  Verify all security controls:  scripts/verify_security.sh
  (Set GOOGLE_API_KEY in deploy/compose/.env to enable the LLM chat.)
============================================================
EOF
