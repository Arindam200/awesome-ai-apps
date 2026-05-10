#!/usr/bin/env bash
# =============================================================================
# Launch vLLM OpenAI-compatible server with the merged fine-tuned model.
#
# Prerequisites:
#   python merge_lora.py   # merge LoRA adapter into base model first
#
# Usage:
#   chmod +x serve.sh
#   ./serve.sh
#
# The server exposes an OpenAI-compatible API at http://0.0.0.0:8100/v1
# The model is served under the name "legal-lora".
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv}"
# Merged full weights (run: python merge_lora.py --adapter_path ./gemma-legal-qa-clean-lora --output_path ./gemma-legal-qa-clean-merged)
MODEL_PATH="${MODEL_PATH:-$SCRIPT_DIR/gemma-legal-qa-clean-merged}"
PORT="${VLLM_PORT:-8100}"

# Activate venv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Validate merged model exists
if [[ ! -f "$MODEL_PATH/config.json" ]]; then
    echo "ERROR: Merged model not found at $MODEL_PATH"
    echo "       Run: python merge_lora.py --adapter_path ./gemma-legal-qa-clean-lora --output_path ./gemma-legal-qa-clean-merged"
    exit 1
fi

echo "==> Starting vLLM server"
echo "    model : $MODEL_PATH"
echo "    port  : $PORT"
echo

# Gemma + OpenAI API: use "string" so user/system content is passed as plain strings into the
# Jinja template. "openai" / "auto" can mis-handle messages and leak system text into generation.
exec vllm serve "$MODEL_PATH" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --served-model-name legal-lora \
    --chat-template "$SCRIPT_DIR/chat_template.jinja" \
    --chat-template-content-format string \
    --dtype bfloat16 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.90 \
    --trust-remote-code
