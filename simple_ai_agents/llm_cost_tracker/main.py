"""Make a live tracked call, or seed a clearly labeled offline dashboard demo."""

import argparse
import json
import os
import sqlite3
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from tracker import CostTracker, PricingConfigurationError, PricingFileNotFoundError, project_path


def demo_reply(request: httpx.Request) -> httpx.Response:
    """Return deterministic SDK-compatible fixtures without contacting a provider."""
    content = json.loads(request.content)
    payload = {
        "id": "demo",
        "object": "chat.completion",
        "created": 0,
        "model": content["model"],
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Offline fixture reply"},
            }
        ],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200},
    }
    if content["model"] == "unknown-usage":
        payload.pop("usage")
    return httpx.Response(200, json=payload)


def main() -> int:
    """Run a live tracked request or an isolated offline demo selected by CLI options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--prompt", default="Explain one benefit of deterministic agent tests.")
    parser.add_argument("--tag", default="example")
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    load_dotenv(project_path(".env"))
    try:
        database = project_path(
            args.database
            or (
                ".data/demo.sqlite3"
                if args.demo
                else os.getenv("LLM_COST_DB", ".data/usage.sqlite3")
            )
        )
    except (RuntimeError, ValueError, OSError):
        print("Database path could not be resolved; check --database or LLM_COST_DB.")
        return 1
    if args.demo:
        try:
            with httpx.Client(transport=httpx.MockTransport(demo_reply)) as transport:
                with OpenAI(api_key="offline-fixture", http_client=transport) as client:
                    tracker = CostTracker(
                        client, database, "demo", project_path("pricing.example.json")
                    )
                    for model, tag in [
                        ("fixture-model", "research"),
                        ("fixture-model", "review"),
                        ("unknown-usage", "research"),
                    ]:
                        tracker.create(
                            model=model, tag=tag, messages=[{"role": "user", "content": "demo"}]
                        )
        except Exception as error:
            print(
                f"Offline demo failed ({type(error).__name__}); "
                "check demo pricing and database configuration."
            )
            return 1
        print(f"Added 3 offline fixture requests to {database}. Prices and usage are synthetic.")
        return 0
    model, key = os.getenv("LLM_MODEL"), os.getenv("LLM_API_KEY")
    if not model or not key:
        parser.error("Set LLM_MODEL and LLM_API_KEY for live mode, or use --demo")
    try:
        try:
            pricing = project_path(os.getenv("LLM_PRICING_FILE", "pricing.json"))
        except (RuntimeError, ValueError, OSError):
            print(
                "Pricing configuration path could not be resolved; check LLM_PRICING_FILE. "
                "No request was sent."
            )
            return 1
        with OpenAI(
            api_key=key, base_url=os.getenv("LLM_BASE_URL"), timeout=60, max_retries=1
        ) as client:
            provider = os.getenv("LLM_PROVIDER", "compatible")
            try:
                tracker = CostTracker(client, database, provider, pricing)
            except PricingFileNotFoundError:
                print(
                    "Pricing file not found. Copy pricing.example.json to pricing.json, replace "
                    "the synthetic entries with your provider's current model rates, or set "
                    "LLM_PRICING_FILE to an existing pricing file. Relative paths use this "
                    "example's directory. No request was sent."
                )
                return 1
            except PricingConfigurationError:
                print(
                    "Pricing configuration could not be loaded; check LLM_PRICING_FILE, "
                    "file access and JSON rates. No request was sent."
                )
                return 1
            except (sqlite3.Error, OSError):
                print(
                    "Database initialization failed; check LLM_COST_DB or --database. "
                    "No request was sent."
                )
                return 1
            if (provider, model) not in tracker.prices:
                print("No configured rate for this provider/model; recorded costs will be unknown.")
            tracker.create(
                model=model, tag=args.tag, messages=[{"role": "user", "content": args.prompt}]
            )
    except Exception as error:
        # SDK exception bodies may contain sensitive request or provider context.
        print(f"Request failed ({type(error).__name__}); check provider and pricing configuration.")
        return 1
    print(f"Request completed; inspect metadata in {database}. Response text was not logged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
