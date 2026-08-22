"""Review an AgentTrace JSON report with Nebius Token Factory."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B"
API_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"

load_dotenv()


def load_report(path: Path) -> object:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_prompt(report: object) -> str:
    report_json = json.dumps(report, ensure_ascii=False, indent=2)
    return f"""Review this local AI coding-agent session report.

Return:
1. A one-sentence verdict.
2. The three highest-risk findings, with evidence from the report.
3. Two concrete next actions.

Do not invent missing metrics. Say \"unavailable\" when the report does not contain evidence.
The report is local operational data; do not suggest uploading the original session logs.

REPORT:
{report_json}
"""


def review_with_nebius(prompt: str, api_key: str, model: str) -> str:
    response = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a precise AI operations reviewer."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 800,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("sample_report.json"))
    parser.add_argument("--model", default=os.getenv("NEBIUS_MODEL", DEFAULT_MODEL))
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt without calling Nebius")
    args = parser.parse_args()

    prompt = build_prompt(load_report(args.input))
    if args.dry_run:
        print(prompt)
        return

    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        parser.error("set NEBIUS_API_KEY or use --dry-run")
    print(review_with_nebius(prompt, api_key, args.model))


if __name__ == "__main__":
    main()
