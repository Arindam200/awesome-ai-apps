#!/usr/bin/env bash
# Fetch an OIDC access token for a demo user (alice|bob|carol) from Keycloak.
#
#   scripts/get_token.sh alice
#   TOKEN=$(scripts/get_token.sh carol)
#
# NOTE: a token minted here (via the host, http://localhost:8081) carries
# iss=http://localhost:8081/... which Toolbox (configured for http://keycloak:8080)
# will REJECT. This script is for inspecting claims, not for calling Toolbox from
# the host. To call Toolbox, mint the token inside the compose network (see
# scripts/verify_security.sh, which runs inside the agent-web container).
set -euo pipefail
USER="${1:-alice}"
PW="${2:-${USER}123}"
KC="${KEYCLOAK_URL:-http://localhost:8085}"
REALM="${KEYCLOAK_REALM:-grocery}"
CLIENT="${KEYCLOAK_CLIENT_ID:-grocery-agent}"

curl -s \
  -d "client_id=${CLIENT}" -d "grant_type=password" \
  -d "username=${USER}" -d "password=${PW}" \
  "${KC}/realms/${REALM}/protocol/openid-connect/token" \
| python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token') or 'ERROR: '+json.dumps(d))"
