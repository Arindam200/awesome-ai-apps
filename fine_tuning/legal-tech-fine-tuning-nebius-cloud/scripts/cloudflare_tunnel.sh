#!/usr/bin/env bash
# =============================================================================
# Cloudflare quick tunnel → FastAPI (default http://127.0.0.1:8000)
#
# Quick tunnel uses trycloudflare.com — no Cloudflare account required.
#
# Usage:
#   ./scripts/cloudflare_tunnel.sh              # install cloudflared to ~/.local/bin if missing
#   ./scripts/cloudflare_tunnel.sh --run        # foreground tunnel (Ctrl-C stops)
#   ./scripts/cloudflare_tunnel.sh --background  # daemon; prints public URL and PID
#
# Env:
#   TUNNEL_TARGET       default http://127.0.0.1:8000
#   CLOUDFLARED_INSTALL_DIR  where to put the binary (default ~/.local/bin)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET="${TUNNEL_TARGET:-http://127.0.0.1:8000}"
INSTALL_DIR="${CLOUDFLARED_INSTALL_DIR:-$HOME/.local/bin}"
TUNNEL_LOG="${TUNNEL_LOG:-/tmp/legaltech-cloudflared-tunnel.log}"

ensure_install_dir() {
    mkdir -p "$INSTALL_DIR"
}

install_cloudflared() {
    if command -v cloudflared >/dev/null 2>&1; then
        echo "==> cloudflared already installed: $(command -v cloudflared)"
        cloudflared --version
        return 0
    fi

    ensure_install_dir
    echo "==> Installing cloudflared to $INSTALL_DIR …"
    local tmp arch url
    tmp="$(mktemp)"
    arch="$(uname -m)"
    case "$arch" in
        x86_64)  arch=amd64 ;;
        aarch64) arch=arm64 ;;
        *) echo "Unsupported arch: $arch"; exit 1 ;;
    esac
    url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch}"
    curl -fsSL "$url" -o "$tmp"
    chmod +x "$tmp"
    mv "$tmp" "$INSTALL_DIR/cloudflared"
    echo "==> Installed: $($INSTALL_DIR/cloudflared --version)"
    echo "    Add to PATH if needed: export PATH=\"$INSTALL_DIR:\$PATH\""
}

cloudflared_bin() {
    if command -v cloudflared >/dev/null 2>&1; then
        command -v cloudflared
    elif [[ -x "$INSTALL_DIR/cloudflared" ]]; then
        echo "$INSTALL_DIR/cloudflared"
    else
        return 1
    fi
}

wait_for_target() {
    local host port
    # crude parse http://host:port
    if [[ "$TARGET" =~ http://([^:/]+):([0-9]+) ]]; then
        host="${BASH_REMATCH[1]}"
        port="${BASH_REMATCH[2]}"
    else
        echo "WARN: could not parse TUNNEL_TARGET=$TARGET ; skipping health wait"
        return 0
    fi
    echo "==> Waiting for $TARGET to respond …"
    local i
    for i in $(seq 1 90); do
        if curl -sf "http://${host}:${port}/health" >/dev/null 2>&1; then
            echo "==> Backend is up."
            return 0
        fi
        sleep 1
    done
    echo "ERROR: $TARGET did not become ready within 90s."
    exit 1
}

run_quick_tunnel() {
    local cf
    cf="$(cloudflared_bin)" || {
        echo "Run without --run first to install, or install cloudflared manually."
        exit 1
    }
    echo "==> Starting quick tunnel → $TARGET"
    echo "    (HTTPS URL will appear below; Ctrl-C to stop)"
    echo "    Ensure FastAPI is up: curl -sf ${TARGET}/health"
    echo
    exec "$cf" tunnel --url "$TARGET"
}

run_tunnel_background() {
    local cf
    cf="$(cloudflared_bin)" || {
        echo "Run $0 first to install cloudflared."
        exit 1
    }
    wait_for_target
    : >"$TUNNEL_LOG"
    echo "==> Starting cloudflared in background (log: $TUNNEL_LOG)"
    nohup "$cf" tunnel --url "$TARGET" >>"$TUNNEL_LOG" 2>&1 &
    local pid=$!
    echo "$pid" >"${TUNNEL_LOG}.pid"
    echo "    pid: $pid"
    local i url=""
    for i in $(seq 1 45); do
        url="$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)"
        if [[ -n "$url" ]]; then
            break
        fi
        sleep 1
    done
    if [[ -n "$url" ]]; then
        echo "==> Public URL: $url"
        echo "    (Share this HTTPS URL; it may take a few seconds to become reachable.)"
    else
        echo "==> URL not detected yet; check: tail -f $TUNNEL_LOG"
    fi
}

case "${1:-}" in
    --run)
        run_quick_tunnel
        ;;
    --background|-b)
        run_tunnel_background
        ;;
    --help|-h)
        echo "Usage: $0                 # install cloudflared if needed (~/.local/bin)"
        echo "       $0 --run           # quick tunnel (foreground)"
        echo "       $0 --background   # quick tunnel (background + print URL)"
        echo "       TUNNEL_TARGET=http://127.0.0.1:9000 $0 --run"
        ;;
    *)
        install_cloudflared
        echo
        echo "Next: start vLLM + FastAPI, then:"
        echo "  $0 --run"
        echo "  # or background:"
        echo "  $0 --background"
        ;;
esac
