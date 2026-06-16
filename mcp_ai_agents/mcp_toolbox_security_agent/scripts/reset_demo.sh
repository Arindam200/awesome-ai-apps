#!/usr/bin/env bash
# DESTRUCTIVE: wipe carts/orders/catalog and reseed clean demo state
# (alice's cart + bob's order). Use this when you WANT a fresh demo.
#
# Normal `scripts/bootstrap_local.sh` is safe and idempotent — it never touches
# existing carts/orders. Only this script (RESET=1) wipes transactional data.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "⚠️  This will DELETE all carts and orders and reseed demo state."
read -r -p "Continue? [y/N] " ans
[ "$ans" = "y" ] || [ "$ans" = "Y" ] || { echo "aborted"; exit 0; }
RESET=1 docker compose -f deploy/compose/docker-compose.yaml --env-file deploy/compose/.env \
  run --rm catalog
echo "✅ demo state reset."
