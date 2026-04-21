#!/usr/bin/env bash
# =============================================================================
# Fine-tune Gemma on a legal JSONL dataset on a fresh H100 VM.
#
# Usage:
#   chmod +x setup_and_train.sh
#   ./setup_and_train.sh
#
# What this does:
#   1. Installs system packages (build tools, git, python)
#   2. Verifies NVIDIA driver + CUDA is visible
#   3. Creates a Python venv and installs PyTorch (cu121) + HF stack
#   4. (Optional) installs flash-attn for speed on H100
#   5. Logs in to Hugging Face via `hf` (Gemma is gated - you need a token)
#   6. Runs the training script on legislation_qa_clean.jsonl (curated Q&A chat)
#
# Expected layout in the working dir:
#   setup_and_train.sh          (this file)
#   train_gemma.py
#   legislation_qa_clean.jsonl  # curated chat messages: {"messages":[{user},{assistant}]}
# =============================================================================

set -euo pipefail

# ---- user-configurable ------------------------------------------------------
# NOTE: Unsloth's notebook calls it "gemma-4-E4B" but on HF the real model id
# for the E4B checkpoint is google/gemma-3n-E4B (Gemma 3n family). Swap to
# whichever id you have access to.
MODEL_ID="${MODEL_ID:-google/gemma-4-E4B}"
DATA_PATH="${DATA_PATH:-$(pwd)/legislation_qa_clean.jsonl}"
OUTPUT_DIR="${OUTPUT_DIR:-$(pwd)/gemma-legal-qa-clean-lora}"
VENV_DIR="${VENV_DIR:-$(pwd)/.venv}"
HF_TOKEN="${HF_TOKEN:-}"   # export HF_TOKEN=hf_xxx before running, or paste below

# Training hyperparameters (tuned for small, curated Q&A set ~160 rows, ≤~300 tokens each)
NUM_TRAIN_EPOCHS="${NUM_TRAIN_EPOCHS:-5}"
LEARNING_RATE="${LEARNING_RATE:-1e-4}"
MAX_SEQ_LENGTH="${MAX_SEQ_LENGTH:-1024}"
GRAD_ACCUM_STEPS="${GRAD_ACCUM_STEPS:-4}"
# -----------------------------------------------------------------------------

echo "==> 1/6  System packages"
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
    build-essential git curl ca-certificates \
    python3 python3-venv python3-pip python3-dev \
    ninja-build pkg-config

echo "==> 2/6  GPU check"
if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "!! nvidia-smi not found. This script assumes the VM image already"
    echo "   ships with NVIDIA drivers (most H100 cloud images do)."
    echo "   If not, install drivers first (e.g. 'sudo ubuntu-drivers install')"
    echo "   and reboot before rerunning."
    exit 1
fi
nvidia-smi | head -20

echo "==> 3/6  Python venv + PyTorch (CUDA 12.4)"
python3 -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip wheel setuptools

# Torch built against CUDA 12.4 — works on H100 (compute cap 9.0)
pip install --index-url https://download.pytorch.org/whl/cu124 \
    torch==2.6.0 torchvision==0.21.0

pip install \
    "transformers==5.5.0" \
    "accelerate>=0.34" \
    "peft>=0.13" \
    "trl>=0.11" \
    "datasets>=3.0" \
    "bitsandbytes>=0.44" \
    "sentencepiece" "protobuf" "einops" "safetensors" \
    "huggingface_hub[cli]>=0.25"

echo "==> 4/6  (optional) flash-attn 2 for H100 speedup"
# Skipping flash-attn if it fails to build is fine; training still works.
pip install --no-build-isolation "flash-attn>=2.7" || \
    echo "   flash-attn build skipped — training will fall back to SDPA"

echo "==> 5/6  Hugging Face login (Gemma is a gated model)"
if [[ -n "$HF_TOKEN" ]]; then
    hf auth login --token "$HF_TOKEN" --add-to-git-credential
else
    echo "   HF_TOKEN not set. Launching interactive login — paste your token:"
    hf auth login
fi

echo "==> 6/6  Sanity checks"
[[ -f "$DATA_PATH" ]] || { echo "!! dataset not found at $DATA_PATH"; exit 1; }
[[ -f "$(pwd)/train_gemma.py" ]] || { echo "!! train_gemma.py missing in cwd"; exit 1; }
[[ -f "$(pwd)/chat_template.jinja" ]] || { echo "!! chat_template.jinja missing (needed for base Gemma)"; exit 1; }
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
N_ROWS=$(wc -l < "$DATA_PATH")
echo "   dataset rows : $N_ROWS"

echo
echo "==> Starting fine-tune"
echo "    model       : $MODEL_ID"
echo "    data        : $DATA_PATH"
echo "    out         : $OUTPUT_DIR"
echo "    epochs      : $NUM_TRAIN_EPOCHS"
echo "    lr          : $LEARNING_RATE"
echo "    max_seq_len : $MAX_SEQ_LENGTH"
echo "    grad_accum  : $GRAD_ACCUM_STEPS"
echo
echo "    Stop other GPU jobs first (e.g. vLLM: pkill -f 'vllm serve') or training may OOM."
echo

# Single-GPU H100. For multi-GPU, prefix with:
#   accelerate launch --num_processes <N>
python train_gemma.py \
    --model_id "$MODEL_ID" \
    --dataset_path "$DATA_PATH" \
    --output_dir "$OUTPUT_DIR" \
    --num_train_epochs "$NUM_TRAIN_EPOCHS" \
    --learning_rate "$LEARNING_RATE" \
    --max_seq_length "$MAX_SEQ_LENGTH" \
    --gradient_accumulation_steps "$GRAD_ACCUM_STEPS"

echo
echo "==> Done. LoRA adapters saved to $OUTPUT_DIR"
