#!/usr/bin/env bash
# Convenience wrapper — same as ./scripts/cloudflare_tunnel.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/cloudflare_tunnel.sh" "$@"
