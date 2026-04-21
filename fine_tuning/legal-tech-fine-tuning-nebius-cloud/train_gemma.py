"""
Fine-tune google/gemma-4-E4B on a local VM using legislation JSONL.
Default dataset is legislation_qa_clean.jsonl (curated chat Q&A, ~160 rows).

Dataset format (one JSON object per line):
  {"text": "..."}                          # pre-formatted plain text
  OR
  {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
  OR
  {"prompt": "...", "completion": "..."}   # prompt/completion pairs

Requirements:
  pip install "torch>=2.3" torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
  pip install "transformers[chat_template]>=5.5.0" "trl>=1.0.0" "datasets>=3.0" accelerate peft bitsandbytes
"""

import json
import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    HfArgumentParser,
)
from peft import LoraConfig, get_peft_model
from trl import SFTConfig, SFTTrainer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

@dataclass
class ScriptArguments:
    model_id: str = field(
        default="google/gemma-4-E4B",
        metadata={"help": "HuggingFace model id or local path"},
    )
    dataset_path: str = field(
        default="legislation_qa_clean.jsonl",
        metadata={
            "help": "Path to the JSONL dataset file",
            "aliases": ["--data_path"],
        },
    )
    output_dir: str = field(
        default="./gemma-legal-qa-clean-lora",
        metadata={"help": "Directory to save checkpoints and final model"},
    )
    hf_token: Optional[str] = field(
        default=None,
        metadata={"help": "HuggingFace token (or set HF_TOKEN env var)"},
    )

    # LoRA
    use_lora: bool = field(default=True, metadata={"help": "Use LoRA (recommended for limited VRAM)"})
    lora_r: int = field(default=16, metadata={"help": "LoRA rank"})
    lora_alpha: int = field(default=32, metadata={"help": "LoRA alpha"})
    lora_dropout: float = field(default=0.05, metadata={"help": "LoRA dropout"})

    # Quantisation
    load_in_4bit: bool = field(default=False, metadata={"help": "Load model in 4-bit (QLoRA)"})
    load_in_8bit: bool = field(default=False, metadata={"help": "Load model in 8-bit"})

    # Training — defaults tuned for a small curated Q&A set (~160 rows, short answers)
    num_train_epochs: int = field(default=5)
    per_device_train_batch_size: int = field(
        default=1,
        metadata={"help": "Use 1 if you share the GPU or hit OOM at long sequence lengths."},
    )
    gradient_accumulation_steps: int = field(
        default=4,
        metadata={"help": "Effective batch = per_device_train_batch_size * this (default 1×4=4)."},
    )
    learning_rate: float = field(
        default=1e-4,
        metadata={"help": "LoRA-friendly default; bump up for even smaller datasets."},
    )
    max_seq_length: int = field(
        default=1024,
        metadata={
            "help": "Rows in legislation_qa_clean.jsonl are short; 1024 fits all of them with headroom.",
        },
    )
    logging_steps: int = field(default=5)
    save_steps: int = field(default=50)
    warmup_ratio: float = field(default=0.03)
    bf16: bool = field(default=True, metadata={"help": "Use bfloat16 (requires Ampere+ GPU)"})
    fp16: bool = field(default=False, metadata={"help": "Use fp16 (fallback for older GPUs)"})
    freeze_vision_audio: bool = field(
        default=True,
        metadata={"help": "Freeze vision/audio towers (text-only fine-tuning)"},
    )


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_jsonl(path: str) -> Dataset:
    """Load a JSONL file and normalise it to a single 'text' column."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Skipping line {line_no}: {e}")
                continue
            records.append(obj)

    logger.info(f"Loaded {len(records)} records from {path}")

    if not records:
        raise ValueError(f"No valid records found in {path}")

    # Detect format from first record
    sample = records[0]
    keys = set(sample.keys())

    if "text" in keys:
        # Already formatted
        texts = [r["text"] for r in records if "text" in r]
    elif "messages" in keys:
        # Chat-format — will be handled by apply_chat_template in SFTTrainer
        return Dataset.from_list(records)
    elif "prompt" in keys and "completion" in keys:
        texts = [r["prompt"] + r["completion"] for r in records]
    elif "instruction" in keys and "output" in keys:
        # Alpaca-style
        context = lambda r: f"\n\n### Input:\n{r['input']}" if r.get("input") else ""
        texts = [
            f"### Instruction:\n{r['instruction']}{context(r)}\n\n### Response:\n{r['output']}"
            for r in records
        ]
    else:
        # Best-effort: concatenate all string values
        logger.warning(
            f"Unrecognised schema (keys: {keys}). "
            "Concatenating all string values — check your JSONL format."
        )
        texts = [" ".join(str(v) for v in r.values() if isinstance(v, str)) for r in records]

    return Dataset.from_dict({"text": texts})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = HfArgumentParser(ScriptArguments)
    args: ScriptArguments = parser.parse_args_into_dataclasses()[0]

    # HF token
    token = args.hf_token or os.environ.get("HF_TOKEN")
    if token:
        os.environ["HF_TOKEN"] = token
        logger.info("HuggingFace token set.")
    else:
        logger.warning(
            "No HF_TOKEN provided. If google/gemma-4-E4B-it is gated you will need one. "
            "Pass --hf_token <TOKEN> or set the HF_TOKEN env var."
        )

    # ------------------------------------------------------------------ #
    # Dataset
    # ------------------------------------------------------------------ #
    logger.info(f"Loading dataset from {args.dataset_path} …")
    dataset = load_jsonl(args.dataset_path)
    logger.info(f"Dataset: {dataset}")

    # ------------------------------------------------------------------ #
    # Tokenizer
    # ------------------------------------------------------------------ #
    logger.info(f"Loading tokenizer for {args.model_id} …")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_id,
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    # Conversational JSONL (e.g. legislation_qa.jsonl) needs a Jinja chat template; base Gemma checkpoints
    # often ship without tokenizer.chat_template.
    if "messages" in dataset.column_names and not tokenizer.chat_template:
        template_path = Path(__file__).resolve().parent / "chat_template.jinja"
        if template_path.is_file():
            tokenizer.chat_template = template_path.read_text(encoding="utf-8")
            logger.info("Set tokenizer.chat_template from %s", template_path)
        else:
            raise ValueError(
                f"Dataset has `messages` but tokenizer has no chat_template and {template_path} is missing. "
                "Add chat_template.jinja (same file used for vLLM serving) or use an instruct model_id."
            )

    # Render chat to a single text column here so TRL does not re-apply the template in dataset workers
    # (workers do not see tokenizer.chat_template set in-process).
    if "messages" in dataset.column_names:

        def _messages_to_text(batch: dict) -> dict:
            texts = [
                tokenizer.apply_chat_template(msgs, tokenize=False)
                for msgs in batch["messages"]
            ]
            return {"text": texts}

        dataset = dataset.map(
            _messages_to_text,
            batched=True,
            batch_size=32,
            remove_columns=["messages"],
            desc="messages → text (chat template)",
        )
        logger.info("Dataset after rendering: %s", dataset)

    # ------------------------------------------------------------------ #
    # Model
    # ------------------------------------------------------------------ #
    logger.info(f"Loading model {args.model_id} …")

    quant_kwargs = {}
    if args.load_in_4bit:
        from transformers import BitsAndBytesConfig
        quant_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        logger.info("Using 4-bit quantisation (QLoRA).")
    elif args.load_in_8bit:
        from transformers import BitsAndBytesConfig
        quant_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        logger.info("Using 8-bit quantisation.")

    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        torch_dtype=torch.bfloat16 if args.bf16 else torch.float16,
        device_map="auto",
        trust_remote_code=True,
        attn_implementation="sdpa",
        **quant_kwargs,
    )

    # Freeze vision / audio towers so we only update text weights
    if args.freeze_vision_audio:
        frozen = 0
        for name, param in model.named_parameters():
            if not name.startswith("model.language_model"):
                param.requires_grad = False
                frozen += 1
        logger.info(f"Froze {frozen} non-language parameter tensors (vision/audio towers).")

    # ------------------------------------------------------------------ #
    # LoRA
    # ------------------------------------------------------------------ #
    if args.use_lora:
        lora_config = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            bias="none",
            task_type="CAUSAL_LM",
            # Target only language-model projection modules (skip vision/audio wrappers).
            target_modules=(
                r"^model\.language_model\.layers\.\d+\."
                r"(self_attn\.(q_proj|k_proj|v_proj|o_proj)|"
                r"mlp\.(gate_proj|up_proj|down_proj))$"
            ),
        )
        model = get_peft_model(model, lora_config, autocast_adapter_dtype=False)
        model.print_trainable_parameters()

    # ------------------------------------------------------------------ #
    # Training config
    # ------------------------------------------------------------------ #
    sft_config = SFTConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.num_train_epochs,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=args.warmup_ratio,
        bf16=args.bf16,
        fp16=args.fp16,
        optim="adamw_torch_fused",
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=2,
        max_seq_length=args.max_seq_length,
        packing=False,
        use_liger_kernel=False,   # Disabled — can cause CUDA illegal access on Gemma 4
        # After conversational prep, TRL stores tokenized strings in column "text"
        dataset_text_field="text",
        report_to="none",
    )

    # ------------------------------------------------------------------ #
    # Trainer
    # ------------------------------------------------------------------ #
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    logger.info("Starting training …")
    train_result = trainer.train()

    logger.info(f"Training complete. Metrics: {train_result.metrics}")

    # Save final model + tokenizer
    logger.info(f"Saving model to {args.output_dir} …")
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    logger.info("Done! Fine-tuned model saved to: %s", args.output_dir)


if __name__ == "__main__":
    main()
