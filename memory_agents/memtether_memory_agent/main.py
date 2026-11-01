from __future__ import annotations

"""memtether_memory_agent — write → correct (supersede) → as_of → Memory Court audit.

Requires:
  pip install memtether openai python-dotenv rich
  .env with NEBIUS_API_KEY (or any OpenAI-compatible endpoint via OPENAI_BASE_URL)

Steps 1-4 are all real MemTether operations (Python API + court CLI). Step 5 uses
Nebius chat completion to draft the *next* memory from the audit trail, showing
how an LLM naturally feeds a governed store.
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

# ------------------------------------------------------------------ LLM setup
MODEL = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3-0324")


def _llm_client():
    """Build the OpenAI-compatible client lazily so that importing this
    module (or running the memory-only steps 1-4) never requires an API key.
    """
    return OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.tokenfactory.nebius.com/v1"),
        api_key=os.getenv("NEBIUS_API_KEY", ""),
    )


def llm(system: str, user: str) -> str:
    """Call the LLM once and return the assistant reply."""
    if not os.getenv("NEBIUS_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        console.print(
            "[yellow]LLM step skipped: set NEBIUS_API_KEY (or OPENAI_BASE_URL/"
            "OPENAI_API_KEY) in .env to enable step 5. Steps 1-4 (memory governance)"
            "already ran successfully.[/yellow]"
        )
        return ""
    client = _llm_client()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=300,
    )
    return resp.choices[0].message.content or ""


def _court_cli(uid: str) -> str:
    """Run `memtether court <uid>` and return the printable case file.

    Uses `sys.executable -m memtether` when the `memtether` script is not on
    PATH (common when the package is installed inside a venv that is not
    activated in the parent shell).
    """
    import shutil
    exe = shutil.which("memtether")
    cmd = [exe, "court", uid] if exe else [sys.executable, "-m", "memtether", "court", uid]
    r = subprocess.run(
        cmd,
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


def step5_llm_draft() -> None:
    console.print(Panel("Step 5 — LLM drafts the next memory (Nebius chat)", style="cyan"))
    system = (
        "You are a memory assistant. Given an audit trail excerpt, propose ONE short "
        "fact worth remembering next. Reply with the fact sentence only, no preamble."
    )
    user = (
        "Audit trail: remember 'User prefers Clash proxy on port 7897' → corrected to "
        "'User switched Clash proxy to port 7890'. What is the most likely next useful "
        "fact to remember about this user's proxy setup?"
    )
    try:
        reply = llm(system, user)
    except Exception as exc:
        console.print(f"  [yellow]step 5 skipped: LLM call failed ({type(exc).__name__}: {str(exc)[:120]})[/yellow]")
        console.print("  [yellow]Memory governance steps 1-4 already completed and are fully functional without it.[/yellow]")
        return
    if not reply:
        console.print("  [yellow]step 5 skipped (no LLM key) - memory governance steps 1-4 already completed[/yellow]")
        return
    draft = reply.strip().splitlines()[0][:120]
    console.print(f"  LLM draft: [bold]{draft}[/bold]")
    import memtether
    r = memtether.remember(draft, type="fact", source="demo-agent-llm")
    if r.get("ok"):
        console.print(f"  stored as: {r['uid']}  (source=demo-agent-llm)")


def main() -> None:
    # MemTether setup lives inside main() so importing this module never
    # mutates the process environment (CodeRabbit round-4 finding).
    global MEMTETHER_DB
    MEMTETHER_DB = Path(tempfile.mkdtemp(prefix="memtether_demo_")) / "demo.db"
    os.environ["MEM_DB"] = str(MEMTETHER_DB)
    os.environ.setdefault("MEMTETHER_HOME", str(MEMTETHER_DB.parent))

    console.print(Panel(
        "[bold]MemTether Governed Memory Agent[/bold]\n"
        "Write → Correct (supersede) → as_of query → Memory Court audit → LLM draft",
        style="green",
    ))
    console.print(f"  DB: {MEMTETHER_DB}\n")

    uid1 = step1_write()
    uid2 = step2_correct(uid1)
    step3_as_of()
    step4_court(uid2)
    step5_llm_draft()

    console.print(Panel(
        "[bold]Done.[/bold] Every write is hash-chained. Corrections supersede, never delete.\n"
        "Run `memtether court <uid>` to audit any memory.",
        style="green",
    ))


if __name__ == "__main__":
    main()
