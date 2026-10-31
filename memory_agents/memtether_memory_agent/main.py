from __future__ import annotations

"""memtether_memory_agent — write → correct (supersede) → as_of → Memory Court audit.

Requires:
  pip install memtether openai python-dotenv rich
  .env with NEBIUS_API_KEY (or any OpenAI-compatible endpoint via OPENAI_BASE_URL)

All memory operations use the MemTether Python API (memtether.remember / gateway.correct /
gateway.as_of) and the `memtether court <uid>` CLI for the printable case file.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel

load_dotenv()

console = Console()

# ------------------------------------------------------------------ MemTether setup
# Use a temp DB so the demo is self-contained and doesn't touch any real memory hub.
MEMTETHER_DB = Path(tempfile.mkdtemp(prefix="memtether_demo_")) / "demo.db"
os.environ["MEM_DB"] = str(MEMTETHER_DB)
os.environ.setdefault("MEMTETHER_HOME", str(MEMTETHER_DB.parent))

# LLM is optional for the demo flow (steps 1-4 are all real API calls to MemTether);
# it is used to demonstrate a natural-language "what should I remember?" turn.
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


def _court_cli(uid: str) -> str:
    """Run `memtether court <uid>` and return the printable case file."""
    r = subprocess.run(
        ["memtether", "court", uid],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        console.print(f"[red]memtether court failed (rc={r.returncode})[/red]")
        console.print(r.stderr or r.stdout)
        sys.exit(1)
    return r.stdout


# ------------------------------------------------------------------ Demo steps
def step1_write() -> str:
    console.print(Panel("Step 1 — Writing a memory via MemTether Python API", style="cyan"))
    import memtether
    fact = "User prefers Clash proxy on port 7897"
    r = memtether.remember(fact, type="fact", source="demo-agent")
    if not r.get("ok"):
        console.print(f"[red]remember failed: {r}[/red]")
        sys.exit(1)
    uid = r["uid"]
    console.print(f"  uid: [bold]{uid}[/bold]")
    console.print(f"  fact: {fact}")
    console.print("  source: demo-agent  (hash-chained, tamper-evident)")
    return uid


def step2_correct(old_uid: str) -> str:
    console.print(Panel("Step 2 — Correcting the memory (supersede, not delete)", style="cyan"))
    from gateway import correct
    new_fact = "User switched Clash proxy to port 7890"
    r = correct(old_uid, new_fact, reason="user corrected the port", by_agent="demo-agent")
    if not r.get("ok"):
        console.print(f"[red]correct failed: {r}[/red]")
        sys.exit(1)
    new_uid = r["new_uid"]
    console.print(f"  old: [dim]{old_uid}[/dim] → [yellow]superseded[/yellow]")
    console.print(f"  new: [bold]{new_uid}[/bold]  op: {r.get('op', 'supersede')}")
    console.print("  (old version is NOT deleted — query it with as_of)")
    return new_uid


def step3_as_of() -> None:
    console.print(Panel("Step 3 — Querying memory as of a past date (bi-temporal)", style="cyan"))
    from gateway import as_of
    r = as_of("2026-01-01 00:00:00", kind="valid")
    console.print("  query: all facts valid at 2026-01-01 (before this demo ran)")
    console.print(f"  count: {r['count']} (correct — demo DB was created just now)")
    r2 = as_of("2100-01-01 00:00:00", kind="valid")
    active = [row for row in r2["rows"] if row["status"] == "active"]
    if active:
        row = active[-1]
        console.print(f"  latest active fact: [bold]{row['content'][:60]}[/bold]")
        console.print(f"    valid_from={row['valid_from']}  status={row['status']}")


def step4_court(uid: str) -> None:
    console.print(Panel("Step 4 — Memory Court audit (hash chain + provenance)", style="cyan"))
    out = _court_cli(uid)
    console.print(out)


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
