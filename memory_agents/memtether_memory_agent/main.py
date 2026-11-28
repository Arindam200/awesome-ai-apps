"""MemTether memory agent: Nebius extracts and answers, MemTether governs.

The model sits on the critical path. Without NEBIUS_API_KEY this script exits
non-zero, because the point of the example is the loop between a model and a
governed store, not the store on its own.

  1. Nebius reads a short conversation and extracts facts as JSON.
  2. Each fact is written with memtether.remember() under a named source.
  3. A correction arrives later. Nebius picks which stored fact it supersedes.
  4. memtether.correct() supersedes it. The old row is kept, never deleted.
  5. The same question is answered twice from as_of(): at the timestamp of the
     first write and at the current time. That is what keeps a superseded fact
     auditable instead of silently overwritten.
  6. memtether court prints the hash-chained dossier for the corrected entry.

Run it with:

    pip install -e .
    cp .env.example .env      # then put a real NEBIUS_API_KEY in it
    python main.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel

load_dotenv()

console = Console()

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3-235B-A22B-Instruct-2507")
SOURCE = "memtether-demo-agent"

# Generous on purpose: a reasoning model returns an empty string when the
# budget is too small for it to finish thinking, and an empty answer looks
# like a bug in the memory layer.
MAX_TOKENS = 1500

TRANSCRIPT = """
Alex: I finally moved my whole setup off the cloud. Everything runs locally now.
Alex: My local proxy listens on port 7897 these days. 7890 kept timing out.
Alex: I keep 14 days of logs and delete anything older.
Alex: The box is a refurbished mini PC with 32 GB of RAM.
""".strip()

CORRECTION = (
    "Alex: small correction, I moved the proxy back to 7890. "
    "7897 had packet loss on large downloads."
)

QUESTION = "Which local proxy port does Alex use, and what changed about it?"


# --------------------------------------------------------------------- LLM
def require_key() -> str:
    """Return the API key or exit non-zero.

    There is no memory-only mode on purpose: an agent that quietly does
    nothing without a model teaches nothing about governed memory.
    """
    key = os.getenv("NEBIUS_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        console.print(
            Panel(
                "[red]NEBIUS_API_KEY is not set.[/red]\n\n"
                "This example extracts, corrects and answers with a Nebius model, so a key\n"
                "is required. Put one in .env (copy .env.example) and run it again.\n"
                "A free key is available through the Nebius Token Factory console.",
                title="missing API key",
                style="red",
            )
        )
        sys.exit(1)
    return key


def llm(system: str, user: str) -> str:
    """One chat completion against Nebius Token Factory."""
    client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL),
        api_key=require_key(),
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=MAX_TOKENS,
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        console.print(
            f"[red]The model returned an empty reply with max_tokens={MAX_TOKENS}. "
            "Raise MAX_TOKENS or set LLM_MODEL to a non-reasoning model.[/red]"
        )
        sys.exit(1)
    return text


def parse_json(text: str) -> Any:
    """Pull a JSON value out of a model reply, fences and prose included.

    Walks to the first brace or bracket and lets the decoder consume exactly one
    value, so a bracket that happens to sit inside a string cannot confuse it.
    """
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    decoder = json.JSONDecoder()
    for i, ch in enumerate(candidate):
        if ch in "[{":
            try:
                value, _ = decoder.raw_decode(candidate[i:])
                return value
            except json.JSONDecodeError:
                continue
    raise ValueError(f"no JSON found in model reply:\n{text[:400]}")


# ------------------------------------------------------------------- steps
def step1_extract() -> list[dict[str, str]]:
    console.print(Panel("Step 1: Nebius extracts facts from a conversation", style="cyan"))
    system = (
        "You extract durable facts about a user from a conversation.\n"
        "Reply with a JSON array of at most 4 objects. Each object has exactly two keys:\n"
        '  "content": one short third-person sentence that stands on its own\n'
        '  "type": "fact" or "preference"\n'
        "Only include things worth remembering across sessions. No commentary, JSON only."
    )
    raw = llm(system, f"Conversation:\n{TRANSCRIPT}")
    facts = parse_json(raw)
    if not isinstance(facts, list) or not facts:
        raise ValueError(f"expected a non-empty JSON array, got: {raw[:300]}")
    console.print(f"  model extracted [bold]{len(facts)}[/bold] facts:")
    for f in facts:
        console.print(f"    - {f['content']}  [dim]({f.get('type', 'fact')})[/dim]")
    return facts


def step2_store(facts: list[dict[str, str]]) -> list[dict[str, str]]:
    console.print(Panel("Step 2: writing each fact with memtether.remember()", style="cyan"))
    import memtether

    stored: list[dict[str, str]] = []
    for f in facts:
        r = memtether.remember(f["content"], type=f.get("type", "fact"), source=SOURCE)
        if not r.get("ok"):
            console.print(f"[red]remember failed: {r}[/red]")
            sys.exit(1)
        stored.append({"uid": r["uid"], "content": f["content"]})
        console.print(f"  {r['uid']}  (source={SOURCE})  {f['content']}")
    return stored


def step3_correct(stored: list[dict[str, str]]) -> tuple[str, str]:
    console.print(Panel("Step 3: a correction arrives, Nebius picks the entry", style="cyan"))
    import memtether

    listing = "\n".join(f'{s["uid"]}: {s["content"]}' for s in stored)
    system = (
        "You maintain a governed memory store. You are given the stored facts with their uids\n"
        "and one new user message. Decide which single stored fact, if any, the message\n"
        "contradicts or updates.\n"
        'Reply with JSON only: {"uid": "<one of the given uids, or null>", '
        '"content": "<the corrected fact as one sentence>", "reason": "<short reason>"}'
    )
    raw = llm(system, f"Stored facts:\n{listing}\n\nNew message:\n{CORRECTION}")
    decision = parse_json(raw)
    old_uid = decision.get("uid")
    if old_uid not in {s["uid"] for s in stored}:
        raise ValueError(f"model returned an unknown uid: {old_uid!r}")
    new_content = (decision.get("content") or "").strip()
    if not new_content:
        raise ValueError("model returned an empty corrected fact")

    console.print(f"  supersedes: [dim]{old_uid}[/dim]")
    console.print(f"  reason: {decision.get('reason', '')}")
    r = memtether.correct(old_uid, new_content, reason=decision.get("reason", ""), by_agent=SOURCE)
    if not r.get("ok"):
        console.print(f"[red]correct failed: {r}[/red]")
        sys.exit(1)
    console.print(f"  new entry: [bold]{r['new_uid']}[/bold]  op={r.get('op')}")
    console.print("  the superseded row still exists, with a closed valid_to")
    return old_uid, r["new_uid"]


def step4_answer(at: str) -> None:
    console.print(Panel(f"Step 4: Nebius answers the same question twice ({at} vs now)", style="cyan"))
    from gateway import as_of

    past = as_of(at, kind="valid")
    now = as_of("2100-01-01 00:00:00", kind="valid")

    def brief(snapshot: dict[str, Any]) -> str:
        rows = [
            {
                "uid": r["uid"],
                "content": r["content"],
                "status": r["status"],
                "valid_from": r["valid_from"],
                "valid_to": r["valid_to"],
            }
            for r in snapshot["rows"]
        ]
        return json.dumps({"at": snapshot["at"], "facts": rows}, ensure_ascii=False, indent=2)

    system = (
        "You answer questions about a user using only the memory snapshots you are given.\n"
        "Each snapshot is a bi-temporal as_of query. If the snapshots disagree, say what\n"
        "changed, when it changed, and which snapshot is current. Two or three sentences."
    )
    user = (
        f"Question: {QUESTION}\n\n"
        f"Snapshot A, what was valid at {past['at']}:\n{brief(past)}\n\n"
        f"Snapshot B, what is valid now:\n{brief(now)}"
    )
    answer = llm(system, user)
    console.print(f"  question: {QUESTION}")
    console.print(f"  snapshot A at {past['at']}: {past['count']} rows")
    console.print(f"  snapshot B now: {now['count']} rows")
    console.print(Panel(answer, title="model answer", style="green"))


def step5_court(uid: str) -> None:
    console.print(Panel("Step 5: memtether court, the hash-chained dossier", style="cyan"))
    import shutil

    exe = shutil.which("memtether")
    cmd = [exe, "court", uid] if exe else [sys.executable, "-m", "memtether", "court", uid]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        console.print(f"[red]memtether court failed (rc={r.returncode})[/red]")
        console.print(r.stderr or r.stdout)
        sys.exit(1)
    console.print(r.stdout)


def main() -> None:
    require_key()

    # A throwaway database per run. MEM_DB is read by MemTether at import time,
    # so it has to be set before memtether is first imported, which is why the
    # heavy imports live inside the step functions.
    db = Path(tempfile.mkdtemp(prefix="memtether_demo_")) / "demo.db"
    os.environ["MEM_DB"] = str(db)
    os.environ.setdefault("MEMTETHER_HOME", str(db.parent))

    console.print(
        Panel(
            "[bold]MemTether governed memory agent[/bold]\n"
            "extract with Nebius, store, correct, answer from as_of, audit with court",
            style="green",
        )
    )
    console.print(f"  model: {MODEL}")
    console.print(f"  db:    {db}\n")

    facts = step1_extract()
    stored = step2_store(facts)

    # The timestamp of the first write is what makes as_of meaningful: we will
    # ask again for the world as it looked right then.
    from gateway import as_of as _as_of

    at_first_write = _as_of("2100-01-01 00:00:00", kind="valid")["rows"][0]["valid_from"]
    time.sleep(1.2)  # so the correction lands in a later second than the write

    old_uid, new_uid = step3_correct(stored)
    step4_answer(at_first_write)
    step5_court(old_uid)

    console.print(
        Panel(
            "[bold]Done.[/bold]\n"
            "Every write is hash chained, corrections supersede instead of deleting, and\n"
            "as_of still returns the old value for the window it was true.\n"
            f"Audit any entry later with: memtether court {old_uid}",
            style="green",
        )
    )


if __name__ == "__main__":
    main()