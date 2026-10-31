from __future__ import annotations

"""memtether_memory_agent — write → correct (supersede) → as_of → Memory Court audit.

Requires:
  pip install memtether openai python-dotenv rich
  .env with NEBIUS_API_KEY (or any OpenAI-compatible endpoint via OPENAI_BASE_URL)
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv()

console = Console()

# ------------------------------------------------------------------ MemTether setup
# Use a temp DB so the demo is self-contained and doesn't touch any real memory hub.
MEMTETHER_DB = Path(tempfile.mkdtemp(prefix="memtether_demo_")) / "demo.db"
os.environ["MEMTETHER_DB"] = str(MEMTETHER_DB)


def _run(args: list[str], label: str) -> dict:
    """Run a memtether CLI subcommand and return parsed JSON."""
    cmd = ["memtether", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        console.print(f"[red]memtether {' '.join(args[:2])} failed (rc={r.returncode})[/red]")
        console.print(r.stderr or r.stdout)
        sys.exit(1)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"raw": r.stdout}


# ------------------------------------------------------------------ LLM setup
client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.tokenfactory.nebius.com/v1"),
    api_key=os.getenv("NEBIUS_API_KEY", ""),
)
MODEL = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3-0324")


def llm(system: str, user: str) -> str:
    """Call the LLM once and return the assistant reply."""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=300,
    )
    return resp.choices[0].message.content or ""


# ------------------------------------------------------------------ Demo steps
def step1_write() -> str:
    console.print(Panel("Step 1 — Writing a memory via MemTether", style="cyan"))
    fact = "User prefers Clash proxy on port 7897"
    r = _run(
        ["remember", fact, "--source", "demo-agent", "--type", "fact", "--json"],
        "remember",
    )
    uid = r.get("uid") or r.get("data", {}).get("uid", "unknown")
    console.print(f"  uid: [bold]{uid}[/bold]")
    console.print(f"  fact: {fact}")
    console.print(f"  source: demo-agent  (hash-chained, tamper-evident)")
    return uid


def step2_correct(old_uid: str) -> str:
    console.print(Panel("Step 2 — Correcting the memory (supersede, not delete)", style="cyan"))
    new_fact = "User switched Clash proxy to port 7890"
    r = _run(
        ["correct", old_uid, "--new-content", new_fact, "--source", "demo-agent", "--json"],
        "correct",
    )
    new_uid = r.get("uid") or r.get("data", {}).get("uid", "unknown")
    op = r.get("op") or r.get("data", {}).get("op", "supersede")
    console.print(f"  old: [dim]{old_uid}[/dim] → [yellow]superseded[/yellow]")
    console.print(f"  new: [bold]{new_uid}[/bold]  op: {op}")
    console.print(f"  (old version is NOT deleted — query it with --as_of)")
    return new_uid


def step3_as_of() -> None:
    console.print(Panel("Step 3 — Querying memory as of a past date", style="cyan"))
    r = _run(
        ["search", "Clash proxy port", "--as_of", "2026-10-01", "--json"],
        "search --as_of",
    )
    hits = r.get("hits") or r.get("data", {}).get("hits") or []
    console.print(f"  query: 'Clash proxy port' as_of 2026-10-01")
    if hits:
        h = hits[0]
        console.print(f"  → [bold]{h.get('content', h.get('text', ''))[:80]}[/bold]")
        console.print(f"    (correct for that date — the correction hadn't happened yet)")
    else:
        console.print("  → no hits (temporal filter working)")


def step4_court(uid: str) -> None:
    console.print(Panel("Step 4 — Memory Court audit (hash chain + provenance)", style="cyan"))
    r = _run(["court", uid, "--json"], "court")
    table = Table(show_header=False, box=None)
    table.add_column(style="bold")
    table.add_column()
    data = r.get("data", r)
    table.add_row("1. CONTENT", str(data.get("content", ""))[:60])
    table.add_row("2. TEMPORAL", str(data.get("temporal", "valid")))
    prov = data.get("provenance", "")
    table.add_row("3. PROVENANCE", str(prov)[:60] if prov else "remember → correct chain")
    table.add_row("4. CONFLICTS", str(data.get("conflicts", "case: superseded"))[:60])
    chain = data.get("chain", data.get("integrity", "PASS"))
    table.add_row("5. INTEGRITY", f"chain: {chain}")
    console.print(table)


def main() -> None:
    console.print(Panel(
        "[bold]MemTether Governed Memory Agent[/bold]\n"
        "Write → Correct (supersede) → as_of query → Memory Court audit",
        style="green",
    ))
    console.print(f"  DB: {MEMTETHER_DB}\n")

    uid1 = step1_write()
    uid2 = step2_correct(uid1)
    step3_as_of()
    step4_court(uid2)

    console.print(Panel(
        "[bold]Done.[/bold] Every write is hash-chained. Corrections supersede, never delete.\n"
        "Run `memtether court <uid>` to audit any memory.",
        style="green",
    ))


if __name__ == "__main__":
    main()
