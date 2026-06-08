#!/usr/bin/env bash
set -euo pipefail

# FlowSentinel — Tailscale Funnel Setup
# Exposes your local Next.js dev server to the internet via Tailscale Funnel.
# Requires: Tailscale v1.52+ installed and logged in.

PORT="${1:-3000}"

echo "=== FlowSentinel — Tailscale Funnel Setup ==="
echo ""

if ! command -v tailscale &> /dev/null; then
  echo "ERROR: Tailscale CLI not found."
  echo ""
  echo "Install Tailscale:"
  echo "  macOS:   brew install tailscale"
  echo "  Linux:   curl -fsSL https://tailscale.com/install.sh | sh"
  echo "  Windows: https://tailscale.com/download/windows"
  echo ""
  exit 1
fi

STATUS=$(tailscale status --json 2>/dev/null | grep -o '"BackendState":"[^"]*"' | cut -d'"' -f4)
if [ "$STATUS" != "Running" ]; then
  echo "ERROR: Tailscale is not running. Start it with:"
  echo "  sudo tailscale up"
  exit 1
fi

HOSTNAME=$(tailscale status --json 2>/dev/null | grep -o '"Self":{"ID":"[^"]*","HostName":"[^"]*"' | grep -o '"HostName":"[^"]*"' | cut -d'"' -f4)
DOMAIN=$(tailscale status --json 2>/dev/null | grep -o '"MagicDNSSuffix":"[^"]*"' | cut -d'"' -f4)

echo "  Tailscale node:  $HOSTNAME"
echo "  Tailnet domain:  $DOMAIN"
echo "  Local port:      $PORT"
echo ""
echo "Starting Tailscale Funnel on port $PORT..."
echo "Your FlowSentinel dashboard will be available at:"
echo ""
echo "  https://${HOSTNAME}.${DOMAIN}/"
echo ""
echo "Share this URL with your team — no VPN, no port forwarding needed."
echo "Press Ctrl+C to stop."
echo ""

tailscale funnel "$PORT"
#!/usr/bin/env bash
set -euo pipefail

# FlowSentinel — Tailscale Funnel Setup
# Exposes your local Next.js dev server to the internet via Tailscale Funnel.
# Requires: Tailscale v1.52+ installed and logged in.

PORT="${1:-3000}"

echo "=== FlowSentinel — Tailscale Funnel Setup ==="
echo ""

if ! command -v tailscale &> /dev/null; then
  echo "ERROR: Tailscale CLI not found."
  echo ""
  echo "Install Tailscale:"
  echo "  macOS:   brew install tailscale"
  echo "  Linux:   curl -fsSL https://tailscale.com/install.sh | sh"
  echo "  Windows: https://tailscale.com/download/windows"
  echo ""
  exit 1
fi

STATUS=$(tailscale status --json 2>/dev/null | grep -o '"BackendState":"[^"]*"' | cut -d'"' -f4)
if [ "$STATUS" != "Running" ]; then
  echo "ERROR: Tailscale is not running. Start it with:"
  echo "  sudo tailscale up"
  exit 1
fi

HOSTNAME=$(tailscale status --json 2>/dev/null | grep -o '"Self":{"ID":"[^"]*","HostName":"[^"]*"' | grep -o '"HostName":"[^"]*"' | cut -d'"' -f4)
DOMAIN=$(tailscale status --json 2>/dev/null | grep -o '"MagicDNSSuffix":"[^"]*"' | cut -d'"' -f4)

echo "  Tailscale node:  $HOSTNAME"
echo "  Tailnet domain:  $DOMAIN"
echo "  Local port:      $PORT"
echo ""
echo "Starting Tailscale Funnel on port $PORT..."
echo "Your FlowSentinel dashboard will be available at:"
echo ""
echo "  https://${HOSTNAME}.${DOMAIN}/"
echo ""
echo "Share this URL with your team — no VPN, no port forwarding needed."
echo "Press Ctrl+C to stop."
echo ""

tailscale funnel "$PORT"
