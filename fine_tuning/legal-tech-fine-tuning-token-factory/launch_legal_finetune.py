from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

PROJECT_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = PROJECT_DIR / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
DEFAULT_SUFFIX = "legislation-qa-lora"
DEFAULT_OUTPUT_PATH = ARTIFACT_DIR / "legislation_qa_clean.nebius.jsonl"
STATE_PATH = ARTIFACT_DIR / "legal_finetune_state.json"
VALID_ROLES = {"system", "user", "assistant"}
ROLE_ALIASES = {
    "human": "user",
    "question": "user",
    "prompt": "user",
    "answer": "assistant",
    "response": "assistant",
    "bot": "assistant",
    "model": "assistant",
}
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text())


def save_state(state: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [extract_text(item) for item in value]
        return "\n".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"].strip()
        for key in ("content", "message"):
            text = extract_text(value.get(key))
            if text:
                return text
    return ""


def normalize_message(message: Any, message_index: int) -> tuple[dict[str, str] | None, str | None]:
    if not isinstance(message, dict):
        return None, "non_dict_message"

    raw_role = str(message.get("role") or "").strip()
    role = raw_role.lower()
    content = extract_text(message.get("content"))

    if role in VALID_ROLES and content:
        return {"role": role, "content": content}, None

    aliased_role = ROLE_ALIASES.get(role)
    if aliased_role and content:
        return {"role": aliased_role, "content": content}, f"aliased_role:{raw_role}"

    # The first record in the supplied dataset stores the user question in the
    # role field. Recover that text instead of dropping the sample.
    if raw_role and not content and message_index == 0:
        return {"role": "user", "content": raw_role}, "promoted_invalid_role_to_user_content"

    if content and message_index == 0:
        label = raw_role or "missing"
        return {"role": "user", "content": content}, f"defaulted_first_message_to_user:{label}"

    label = raw_role or "missing"
    return None, f"dropped_message:{label}"


def normalize_record(record: dict[str, Any]) -> tuple[dict[str, list[dict[str, str]]] | None, list[str]]:
    messages = record.get("messages")
    if not isinstance(messages, list) or not messages:
        return None, ["missing_messages"]

    cleaned: list[dict[str, str]] = []
    repairs: list[str] = []

    for idx, message in enumerate(messages):
        normalized, repair = normalize_message(message, idx)
        if repair:
            repairs.append(repair)
        if normalized:
            cleaned.append(normalized)

    roles = {message["role"] for message in cleaned}
    if "user" not in roles or "assistant" not in roles:
        repairs.append("dropped_record_missing_user_or_assistant")
        return None, repairs

    return {"messages": cleaned}, repairs


def sanitize_dataset(input_path: str | Path, output_path: str | Path = DEFAULT_OUTPUT_PATH) -> dict[str, Any]:
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_records = 0
    kept_records = 0
    dropped_records = 0
    repaired_records = 0
    repair_counts: dict[str, int] = {}

    with input_path.open() as src, output_path.open("w") as dst:
        for line in src:
            if not line.strip():
                continue
            total_records += 1
            record = json.loads(line)
            normalized, repairs = normalize_record(record)
            for repair in repairs:
                repair_counts[repair] = repair_counts.get(repair, 0) + 1
            if repairs:
                repaired_records += 1
            if not normalized:
                dropped_records += 1
                continue
            dst.write(json.dumps(normalized, ensure_ascii=True) + "\n")
            kept_records += 1

    return {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "total_records": total_records,
        "kept_records": kept_records,
        "dropped_records": dropped_records,
        "repaired_records": repaired_records,
        "repair_counts": repair_counts,
    }


def build_client(*, api_key: str | None = None, base_url: str = DEFAULT_BASE_URL) -> OpenAI:
    resolved_key = api_key or os.environ.get("NEBIUS_API_KEY")
    if not resolved_key:
        raise RuntimeError("Set NEBIUS_API_KEY before calling Nebius Token Factory.")
    return OpenAI(base_url=base_url, api_key=resolved_key)


def upload_training_file(client: OpenAI, dataset_path: str | Path):
    dataset_path = Path(dataset_path)
    with dataset_path.open("rb") as handle:
        return client.files.create(file=handle, purpose="fine-tune")


def create_finetune_job(
    client: OpenAI,
    *,
    training_file_id: str,
    model: str = DEFAULT_MODEL,
    suffix: str = DEFAULT_SUFFIX,
    hyperparameters: dict[str, Any] | None = None,
    seed: int | None = 42,
):
    resolved_hparams = {
        "n_epochs": 4,
        "learning_rate": 1e-5,
        "lora": True,
        "lora_r": 16,
        "lora_alpha": 16,
        "lora_dropout": 0.05,
        "packing": True,
    }
    if hyperparameters:
        resolved_hparams.update(hyperparameters)

    return client.fine_tuning.jobs.create(
        model=model,
        training_file=training_file_id,
        suffix=suffix,
        hyperparameters=resolved_hparams,
        seed=seed,
    )


def wait_for_job(client: OpenAI, job_id: str, *, poll_seconds: int = 30):
    seen_events: set[tuple[Any, Any, Any]] = set()

    while True:
        job = client.fine_tuning.jobs.retrieve(job_id)
        events = client.fine_tuning.jobs.list_events(fine_tuning_job_id=job_id, limit=20).data
        for event in reversed(events):
            marker = (
                getattr(event, "id", None),
                getattr(event, "created_at", None),
                getattr(event, "message", None),
            )
            if marker in seen_events:
                continue
            seen_events.add(marker)
            created_at = getattr(event, "created_at", "?")
            message = getattr(event, "message", "")
            print(f"[{created_at}] {message}")

        print(f"status={job.status} trained_tokens={getattr(job, 'trained_tokens', None)}")
        if job.status in TERMINAL_STATUSES:
            return job
        time.sleep(poll_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sanitize a legal chat dataset and launch a Nebius fine-tuning job."
    )
    parser.add_argument("--dataset", default="legislation_qa_clean.jsonl", help="Source JSONL dataset path.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Output path for the sanitized JSONL dataset.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Nebius API base URL.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Base model to fine-tune.")
    parser.add_argument("--suffix", default=DEFAULT_SUFFIX, help="Suffix for the fine-tuning job.")
    parser.add_argument("--epochs", type=int, default=4, help="Number of epochs.")
    parser.add_argument("--learning-rate", type=float, default=1e-5, help="Training learning rate.")
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank.")
    parser.add_argument("--lora-alpha", type=int, default=16, help="LoRA alpha.")
    parser.add_argument("--lora-dropout", type=float, default=0.05, help="LoRA dropout.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--poll-seconds", type=int, default=30, help="Polling interval in seconds.")
    parser.add_argument("--wait", action="store_true", help="Poll until the job reaches a terminal state.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = build_client(base_url=args.base_url)

    report = sanitize_dataset(args.dataset, args.output)
    print(json.dumps({"sanitization_report": report}, indent=2))

    training_file = upload_training_file(client, args.output)
    print(
        json.dumps(
            {
                "training_file_id": training_file.id,
                "filename": training_file.filename,
                "bytes": getattr(training_file, "bytes", None),
            },
            indent=2,
        )
    )

    job = create_finetune_job(
        client,
        training_file_id=training_file.id,
        model=args.model,
        suffix=args.suffix,
        hyperparameters={
            "n_epochs": args.epochs,
            "learning_rate": args.learning_rate,
            "lora": True,
            "lora_r": args.lora_r,
            "lora_alpha": args.lora_alpha,
            "lora_dropout": args.lora_dropout,
            "packing": True,
        },
        seed=args.seed,
    )

    state = {
        "dataset_path": str(Path(args.dataset).resolve()),
        "clean_dataset_path": str(Path(args.output).resolve()),
        "sanitization_report": report,
        "training_file_id": training_file.id,
        "fine_tuning_job_id": job.id,
        "fine_tuning_status": job.status,
        "model": args.model,
        "suffix": args.suffix,
    }
    save_state(state)

    print(
        json.dumps(
            {
                "job_id": job.id,
                "status": job.status,
                "model": job.model,
                "training_file": job.training_file,
            },
            indent=2,
        )
    )

    if args.wait:
        final_job = wait_for_job(client, job.id, poll_seconds=args.poll_seconds)
        state = load_state()
        state["fine_tuning_status"] = final_job.status
        state["fine_tuned_model"] = getattr(final_job, "fine_tuned_model", None)
        state["trained_tokens"] = getattr(final_job, "trained_tokens", None)
        save_state(state)


if __name__ == "__main__":
    main()
