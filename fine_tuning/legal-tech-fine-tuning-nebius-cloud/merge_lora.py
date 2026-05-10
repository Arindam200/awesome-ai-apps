"""
Merge the LoRA adapter into the base model and save a standalone checkpoint.

Usage:
    python merge_lora.py \
        --base_model google/gemma-4-E4B \
        --adapter_path ./gemma-legal-lora \
        --output_path ./gemma-legal-merged
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge LoRA adapter into base model")
    parser.add_argument(
        "--base_model",
        default="google/gemma-4-E4B",
        help="HuggingFace model id or local path for the base model",
    )
    parser.add_argument(
        "--adapter_path",
        default="./gemma-legal-qa-clean-lora",
        help="Path to the LoRA adapter directory",
    )
    parser.add_argument(
        "--output_path",
        default="./gemma-legal-qa-clean-merged",
        help="Where to save the merged model",
    )
    parser.add_argument(
        "--chat_template_file",
        default="",
        help="Path to chat_template.jinja (defaults to next to this script). "
        "Embedded in tokenizer_config so HF/vLLM see a non-empty chat_template.",
    )
    args = parser.parse_args()

    if not args.chat_template_file:
        tpl_path = Path(__file__).resolve().parent / "chat_template.jinja"
    else:
        tpl_path = Path(args.chat_template_file)

    log.info("Loading tokenizer from %s …", args.base_model)
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)

    if tpl_path.is_file():
        tokenizer.chat_template = tpl_path.read_text(encoding="utf-8")
        log.info("Set tokenizer.chat_template from %s", tpl_path)
    else:
        log.warning(
            "Chat template file not found (%s); merged tokenizer may omit chat_template in config.",
            tpl_path,
        )

    log.info("Loading base model %s in bfloat16 …", args.base_model)
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )

    log.info("Loading LoRA adapter from %s …", args.adapter_path)
    # autocast_adapter_dtype=False avoids PEFT iterating over all torch dtypes
    # (which fails on older torch lacking torch.float8_e8m0fnu).
    model = PeftModel.from_pretrained(
        model, args.adapter_path, autocast_adapter_dtype=False
    )

    log.info("Merging LoRA weights into base model …")
    model = model.merge_and_unload()

    log.info("Saving merged model to %s …", args.output_path)
    model.save_pretrained(args.output_path, safe_serialization=True)
    tokenizer.save_pretrained(args.output_path)

    log.info("Done. Merged model saved to %s", args.output_path)


if __name__ == "__main__":
    main()
