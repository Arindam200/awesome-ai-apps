from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from launch_legal_finetune import DEFAULT_BASE_URL, build_client, load_state, save_state

CONTROL_URL = "https://api.tokenfactory.nebius.com"
PROJECT_DIR = Path(__file__).resolve().parent
HEADERS_TEMPLATE = {"Content-Type": "application/json"}
ACTIVE_STATUSES = {"active", "error"}
DEPLOYABLE_BASE_MODEL_ALIASES = {
    "meta-llama/Llama-3.1-8B-Instruct": "meta-llama/Meta-Llama-3.1-8B-Instruct",
}


def auth_headers(api_key: str) -> dict[str, str]:
    headers = dict(HEADERS_TEMPLATE)
    headers["Authorization"] = f"Bearer {api_key}"
    return headers


def resolve_deployable_base_model(base_model: str) -> str:
    return DEPLOYABLE_BASE_MODEL_ALIASES.get(base_model, base_model)


def get_latest_checkpoint(job_id: str, *, api_key: str):
    client = build_client(api_key=api_key, base_url=DEFAULT_BASE_URL)
    checkpoints = client.fine_tuning.jobs.checkpoints.list(fine_tuning_job_id=job_id).data
    if not checkpoints:
        raise RuntimeError(f"No checkpoints found for {job_id}.")
    return checkpoints[-1]


def create_custom_model(
    *,
    api_key: str,
    job_id: str,
    checkpoint_id: str,
    base_model: str,
    name: str,
    description: str | None = None,
) -> dict[str, Any]:
    resolved_base_model = resolve_deployable_base_model(base_model)
    payload = {
        "source": f"{job_id}:{checkpoint_id}",
        "base_model": resolved_base_model,
        "name": name,
    }
    if description:
        payload["description"] = description

    response = requests.post(
        f"{CONTROL_URL}/v0/models",
        json=payload,
        headers=auth_headers(api_key),
        timeout=120,
    )
    if not response.ok:
        raise RuntimeError(f"Deployment request failed: {response.status_code} {response.text}")
    return response.json()


def get_custom_model(name: str, *, api_key: str) -> dict[str, Any]:
    encoded_name = quote(name, safe="")
    response = requests.get(
        f"{CONTROL_URL}/v0/models/{encoded_name}",
        headers=auth_headers(api_key),
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def wait_for_model(name: str, *, api_key: str, poll_seconds: int = 10) -> dict[str, Any]:
    while True:
        info = get_custom_model(name, api_key=api_key)
        status = info.get("status")
        print(json.dumps({"name": name, "status": status, "status_reason": info.get("status_reason")}, indent=2))
        if status in ACTIVE_STATUSES:
            return info
        time.sleep(poll_seconds)


def smoke_test(model_name: str, *, api_key: str) -> str:
    client = build_client(api_key=api_key, base_url=DEFAULT_BASE_URL)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": "Summarize in one sentence what this model was fine-tuned to do.",
            }
        ],
    )
    return response.choices[0].message.content or ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy the latest legal fine-tuning checkpoint as a private Nebius custom model.")
    parser.add_argument("--job-id", help="Fine-tuning job id. Defaults to the saved state value.")
    parser.add_argument("--base-model", help="Base model name. Defaults to the saved state value.")
    parser.add_argument("--name", default="legislation-qa-private", help="Adapter deployment name.")
    parser.add_argument("--description", default="Private legal QA LoRA adapter deployed from Nebius fine-tuning job.", help="Deployment description.")
    parser.add_argument("--poll-seconds", type=int, default=10, help="Polling interval while the model validates.")
    parser.add_argument("--skip-smoke-test", action="store_true", help="Skip chat completion verification after activation.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = os.environ.get("NEBIUS_API_KEY")
    if not api_key:
        raise RuntimeError("Set NEBIUS_API_KEY before deploying the model.")

    state = load_state()
    job_id = args.job_id or state.get("fine_tuning_job_id")
    base_model = args.base_model or state.get("model")
    if not job_id or not base_model:
        raise RuntimeError("Missing fine-tuning job or base model in arguments/state.")
    resolved_base_model = resolve_deployable_base_model(base_model)

    checkpoint = get_latest_checkpoint(job_id, api_key=api_key)
    model_info = create_custom_model(
        api_key=api_key,
        job_id=job_id,
        checkpoint_id=checkpoint.id,
        base_model=resolved_base_model,
        name=args.name,
        description=args.description,
    )

    deployed_name = model_info["name"]
    final_info = wait_for_model(deployed_name, api_key=api_key, poll_seconds=args.poll_seconds)

    smoke_test_output = None
    if final_info.get("status") == "active" and not args.skip_smoke_test:
        smoke_test_output = smoke_test(deployed_name, api_key=api_key)

    state.update(
        {
            "deployment_job_id": job_id,
            "deployment_checkpoint_id": checkpoint.id,
            "deployment_checkpoint_step": getattr(checkpoint, "step_number", None),
            "deployment_name": args.name,
            "deployment_base_model": resolved_base_model,
            "deployment_model_name": deployed_name,
            "deployment_status": final_info.get("status"),
            "deployment_status_reason": final_info.get("status_reason"),
            "deployment_info": final_info,
        }
    )
    if smoke_test_output is not None:
        state["deployment_smoke_test_output"] = smoke_test_output
    save_state(state)

    print(
        json.dumps(
            {
                "requested_name": args.name,
                "deployment_model_name": deployed_name,
                "status": final_info.get("status"),
                "checkpoint_id": checkpoint.id,
                "checkpoint_step": getattr(checkpoint, "step_number", None),
                "smoke_test_output": smoke_test_output,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
