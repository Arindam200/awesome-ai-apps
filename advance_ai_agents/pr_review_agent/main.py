"""Preview a review by default. Publishing requires the explicit --post option."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from review import Review, Snapshot, analyze, fetch_snapshot, inline_comments, publish


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", help="Public GitHub PR URL")
    parser.add_argument("--post", action="store_true", help="Publish one COMMENT review to GitHub")
    parser.add_argument(
        "--demo", action="store_true", help="Offline fixture preview; no model or GitHub"
    )
    args = parser.parse_args(argv)
    if args.demo and args.post:
        parser.error("--demo cannot be combined with --post")
    if not args.demo and not args.url:
        parser.error("Provide a PR URL or use --demo")

    load_dotenv(Path(__file__).with_name(".env"))
    if args.demo:
        demo = json.loads(Path(__file__).with_name("demo.json").read_text(encoding="utf-8"))
        snapshot = Snapshot(**demo["snapshot"])
        review = Review.model_validate(demo["review"])
        preview = {"mode": "offline fixture (not model inference)", "head": snapshot.head_sha}
        preview["comments"] = inline_comments(snapshot, review)
        preview["summary"] = review.summary
        print(json.dumps(preview, indent=2, ensure_ascii=False))
        return 0

    token = os.getenv("GITHUB_TOKEN")
    api_key = os.getenv("NEBIUS_API_KEY")
    model = os.getenv("NEBIUS_MODEL")
    if not all([token, api_key, model]):
        parser.error(
            "Set GITHUB_TOKEN, NEBIUS_API_KEY and NEBIUS_MODEL in your environment or .env"
        )
    from github import Auth, Github

    try:
        with Github(auth=Auth.Token(token), timeout=30, retry=1) as client:
            snapshot, pull = fetch_snapshot(client, args.url)
            review = analyze(snapshot, api_key, model)
            comments = inline_comments(snapshot, review)
            print(json.dumps({"head": snapshot.head_sha, **review.model_dump()}, indent=2))
            if args.post:
                print(publish(client, pull, snapshot, review))
            else:
                print(f"Preview only: {len(comments)} inline comments. No GitHub writes performed.")
    except Exception as error:
        # Provider/HTTP exceptions may include credentials or private request context.
        print(
            f"Review failed ({type(error).__name__}); check configuration and PR state, then rerun."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
