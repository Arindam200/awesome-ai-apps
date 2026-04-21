#!/usr/bin/env bash
# =============================================================================
# One-command launcher: starts vLLM backend + FastAPI frontend.
#
# Usage:
#   chmod +x run.sh
#   ./run.sh
#
# Ctrl-C stops both processes.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv}"
VLLM_PORT="${VLLM_PORT:-8100}"
API_PORT="${API_PORT:-8000}"
# Set WITH_TUNNEL=1 to start a Cloudflare quick tunnel (trycloudflare.com) to FastAPI after /health is OK.
WITH_TUNNEL="${WITH_TUNNEL:-0}"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

VLLM_PID=""
API_PID=""
TUNNEL_PID=""

cleanup() {
    echo
    echo "==> Shutting down …"
    [[ -n "$TUNNEL_PID" ]] && kill "$TUNNEL_PID" 2>/dev/null && echo "    stopped Cloudflare tunnel (pid $TUNNEL_PID)"
    [[ -n "$API_PID"  ]] && kill "$API_PID"  2>/dev/null && echo "    stopped FastAPI (pid $API_PID)"
    [[ -n "$VLLM_PID" ]] && kill "$VLLM_PID" 2>/dev/null && echo "    stopped vLLM   (pid $VLLM_PID)"
    wait 2>/dev/null
    echo "==> Done."
}
trap cleanup EXIT INT TERM

# ---- 1. Start vLLM in the background ----------------------------------------
echo "==> Starting vLLM backend on port $VLLM_PORT …"
bash "$SCRIPT_DIR/serve.sh" &
VLLM_PID=$!

# ---- 2. Wait for vLLM to become healthy -------------------------------------
echo "==> Waiting for vLLM to be ready (this takes a few minutes on first load) …"
MAX_WAIT=600
ELAPSED=0
while (( ELAPSED < MAX_WAIT )); do
    if curl -sf "http://localhost:$VLLM_PORT/v1/models" >/dev/null 2>&1; then
        echo "==> vLLM is ready (took ${ELAPSED}s)"
        break
    fi
    # Check vLLM process is still alive
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "ERROR: vLLM process died unexpectedly. Check logs above."
        exit 1
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if (( ELAPSED >= MAX_WAIT )); then
    echo "ERROR: vLLM did not become healthy within ${MAX_WAIT}s."
    exit 1
fi

# ---- 3. Start FastAPI --------------------------------------------------------
echo "==> Starting FastAPI on port $API_PORT …"
export VLLM_BASE_URL="http://localhost:$VLLM_PORT/v1"
export API_PORT
python "$SCRIPT_DIR/api.py" &
API_PID=$!

echo "==> Waiting for FastAPI /health …"
ELAPSED=0
while (( ELAPSED < 120 )); do
    if curl -sf "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1; then
        echo "==> FastAPI is ready (took ${ELAPSED}s)"
        break
    fi
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "ERROR: FastAPI process exited before becoming healthy."
        exit 1
    fi
    sleep 1
    ELAPSED=$((ELAPSED + 1))
done
if (( ELAPSED >= 120 )); then
    echo "ERROR: FastAPI did not respond on :$API_PORT within 120s."
    exit 1
fi

PUBLIC_URL=""
if [[ "$WITH_TUNNEL" == "1" || "$WITH_TUNNEL" == "true" || "$WITH_TUNNEL" == "yes" ]]; then
    if ! command -v cloudflared >/dev/null 2>&1 && [[ ! -x "$HOME/.local/bin/cloudflared" ]]; then
        echo "==> Installing cloudflared for tunnel (one-time) …"
        bash "$SCRIPT_DIR/scripts/cloudflare_tunnel.sh" || true
    fi
    TUNNEL_LOG="/tmp/legaltech-cloudflared-tunnel.log"
    : >"$TUNNEL_LOG"
    echo "==> Starting Cloudflare quick tunnel → http://127.0.0.1:$API_PORT (log: $TUNNEL_LOG)"
    export TUNNEL_TARGET="http://127.0.0.1:$API_PORT"
    if command -v cloudflared >/dev/null 2>&1; then
        nohup cloudflared tunnel --url "$TUNNEL_TARGET" >>"$TUNNEL_LOG" 2>&1 &
    elif [[ -x "$HOME/.local/bin/cloudflared" ]]; then
        nohup "$HOME/.local/bin/cloudflared" tunnel --url "$TUNNEL_TARGET" >>"$TUNNEL_LOG" 2>&1 &
    else
        echo "ERROR: cloudflared not found. Run: bash scripts/cloudflare_tunnel.sh"
        exit 1
    fi
    TUNNEL_PID=$!
    echo "    tunnel pid: $TUNNEL_PID"
    for _ in $(seq 1 45); do
        PUBLIC_URL="$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)"
        if [[ -n "$PUBLIC_URL" ]]; then
            echo "==> Public HTTPS URL: $PUBLIC_URL"
            break
        fi
        sleep 1
    done
    if [[ -z "${PUBLIC_URL:-}" ]]; then
        echo "==> Public URL not ready yet — run: tail -f $TUNNEL_LOG"
    fi
fi

echo
echo "============================================="
echo "  Legal AI API is live!"
echo "  FastAPI : http://0.0.0.0:$API_PORT"
echo "  Docs    : http://0.0.0.0:$API_PORT/docs"
echo "  vLLM    : http://0.0.0.0:$VLLM_PORT/v1"
echo "  Health  : http://0.0.0.0:$API_PORT/health"
if [[ -n "${PUBLIC_URL:-}" ]]; then
    echo "  Tunnel  : $PUBLIC_URL"
fi
echo "============================================="
echo
echo "Press Ctrl-C to stop both services."

# Keep script alive until a child exits or signal received
wait
