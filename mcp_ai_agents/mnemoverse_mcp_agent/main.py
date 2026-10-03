"""Mnemoverse MCP Agent: memory over the Model Context Protocol, end to end.

The agent never imports a memory SDK. It starts the Mnemoverse memory server as
a subprocess, speaks MCP to it over stdio, and does four things through the
protocol:

    1. discovery  - list_tools(), so you see the ten tools and their arguments
    2. write      - memory_write, to record decisions
    3. read       - memory_read, to recall them in a later session
    4. feedback   - memory_feedback, to report how a recalled memory worked out

Step 4 is the point. Recall is ranked, and telling the service that a recalled
item helped changes where it lands next time. The run prints the order on both
sides of that call so you can see the move.

The model step in between is optional. Without a Nebius key the agent still
walks the protocol and prints every result.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import sys

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

load_dotenv()

console = Console()

# Keep the SDK's transport logger out of the walkthrough output, so the tables
# below are the only thing on screen.
logging.getLogger("mcp").setLevel(logging.CRITICAL)

# Pin the server version. An unpinned `npx -y <pkg>` can run an older copy that
# is already installed on the machine instead of the one on the registry.
MEMORY_SERVER = "@mnemoverse/mcp-memory-server@0.10.2"

# The example writes into its own namespace, so its notes stay separate from
# other notes on the key. Change it to start the story from scratch.
DOMAIN = os.getenv("MNEMOVERSE_DEMO_DOMAIN", "project:release-assistant-mcp")

QUESTION = "how do we ship a release?"

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
NEBIUS_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"

DECISIONS = [
    (
        (
            "Release checklist: run migrations, then deploy, then smoke test "
            "the health endpoint"
        ),
        ["deploy", "release", "checklist"],
    ),
    (
        "Database migrations run with Alembic before every release",
        ["deploy", "database", "migrations"],
    ),
    (
        "Hotfixes skip the release train and deploy from a patch branch",
        ["deploy", "hotfix", "release"],
    ),
]

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def text_of(result) -> str:
    """Join the text blocks of a tool result. Content can also be image or audio."""
    return "".join(getattr(block, "text", "") or "" for block in result.content)


def error_line(result) -> str:
    """The actionable half of a tool error, without the raw payload the server appends."""
    return text_of(result).split("Raw detail")[0].strip()


def failed(result) -> bool:
    """True when the server reported a tool error.

    The flag is is_error in mcp 2.x and isError in 1.x, so read whichever the
    installed version has. Reading only one of them makes every tool error look
    like a success.
    """
    flag = getattr(result, "is_error", None)
    if flag is None:
        flag = getattr(result, "isError", False)
    return bool(flag)


def parse_recall(body: str):
    """Turn memory_read's numbered output into (rank, content, atom_id) rows."""
    rows = []
    pending = None
    for line in body.split("\n"):
        numbered = re.match(r"\s*(\d+)\.\s*(.+)", line)
        if numbered:
            # Drop the trailing `@"domain" · date` marker, then the concept
            # list the server appends in parentheses. The concept list is only
            # stripped when it holds a comma-separated list, so a memory whose
            # own text ends in brackets keeps them.
            content = re.sub(r"\s+@\".*$", "", numbered.group(2)).strip()
            content = re.sub(r"\s*\([^()]*,[^()]*\)\s*$", "", content).strip()
            pending = (int(numbered.group(1)), content)
        elif "id:" in line and pending:
            found = UUID.findall(line)
            if found:
                rows.append((pending[0], pending[1], found[0]))
                pending = None
    return rows


def show(title: str, rows) -> None:
    table = Table(title=title, title_justify="left", header_style="bold")
    table.add_column("#", width=3)
    table.add_column("memory")
    for rank, content, _ in rows:
        table.add_row(str(rank), Text(content))
    console.print(table)


def _has(exc, kind) -> bool:
    """True when exc is `kind`, or a group anyio wrapped around one."""
    if isinstance(exc, kind):
        return True
    for inner in getattr(exc, "exceptions", []) or []:
        if _has(inner, kind):
            return True
    return False


def _root(exc):
    """The innermost exception, unwrapping the groups anyio nests around it."""
    inner = getattr(exc, "exceptions", None)
    return _root(inner[0]) if inner else exc


def require_key() -> None:
    key = os.getenv("MNEMOVERSE_API_KEY", "")
    if not key or key.startswith("your_"):
        console.print(
            "[red]MNEMOVERSE_API_KEY is not set.[/red] Copy .env.example to .env "
            "and put a free key from https://console.mnemoverse.com in it."
        )
        sys.exit(1)


def npx_path() -> str:
    found = shutil.which("npx") or shutil.which("npx.cmd")
    if not found:
        console.print(
            "[red]npx was not found.[/red] The memory server ships on npm, so "
            "Node.js 18 or newer has to be installed."
        )
        sys.exit(1)
    return found


def answer_from(recalled, question: str) -> None:
    """Answer the question from the recalled memories, if a Nebius key is set."""
    nebius_key = os.getenv("NEBIUS_API_KEY", "")
    if not nebius_key or nebius_key.startswith("your_"):
        console.print(
            "[yellow]NEBIUS_API_KEY is not set, so the model step is skipped."
            "[/yellow] The protocol walkthrough below still runs.\n"
        )
        return

    notes = "\n".join(f"- {content}" for _, content, _ in recalled)
    client = OpenAI(api_key=nebius_key, base_url=NEBIUS_BASE_URL)
    try:
        completion = client.chat.completions.create(
            model=NEBIUS_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a project assistant. Answer only from the "
                        "notes given to you. If the notes do not cover the "
                        "question, say so instead of guessing."
                    ),
                },
                {
                    "role": "user",
                    "content": "Notes:\n" + notes + "\n\nQuestion: " + question,
                },
            ],
        )
    except Exception as exc:  # noqa: BLE001 - the protocol walk must survive
        console.print(
            "[yellow]The model step failed (" + exc.__class__.__name__ + "), so "
            "it is skipped.[/yellow] The protocol walkthrough below still runs.\n"
        )
        return

    reply = (completion.choices[0].message.content or "").strip()
    console.print(Panel(Text(reply), title="Answer", border_style="blue"))
    console.print()


async def discover(session) -> None:
    listing = await session.list_tools()
    table = Table(
        title="Tools the memory server offers over MCP",
        title_justify="left",
        header_style="bold",
    )
    table.add_column("tool")
    table.add_column("required arguments")
    for tool in listing.tools:
        # The wire format calls it inputSchema; the Python SDK exposes it as
        # input_schema. Take whichever this version has.
        schema = (
            getattr(tool, "input_schema", None)
            or getattr(tool, "inputSchema", None)
            or {}
        )
        required = schema.get("required", []) if isinstance(schema, dict) else []
        table.add_row(tool.name, ", ".join(required) or "none")
    console.print(table)
    console.print(
        "[dim]Listing tools does not check the API key. The key is checked on "
        "the first tool call, so a wrong key shows up there, not here.[/dim]\n"
    )


async def seed(session) -> bool:
    existing = await session.call_tool(
        "memory_list_recent", {"domain": DOMAIN, "limit": 1}
    )
    if not failed(existing) and UUID.search(text_of(existing)):
        console.print(
            "[dim]Session 1 skipped: " + DOMAIN + " already holds notes from an "
            "earlier run.[/dim]\n"
        )
        return True

    stored = 0
    for content, concepts in DECISIONS:
        result = await session.call_tool(
            "memory_write",
            {"content": content, "concepts": concepts, "domain": DOMAIN},
        )
        if failed(result):
            console.print("[red]memory_write failed:[/red] " + error_line(result))
            return False
        stored += 1
    console.print(
        "[green]Session 1 (Monday):[/green] wrote " + str(stored) + " decisions "
        "through memory_write.\n"
    )
    return True


async def recall(session):
    result = await session.call_tool(
        "memory_read", {"query": QUESTION, "domain": DOMAIN, "top_k": 5}
    )
    if failed(result):
        console.print("[red]memory_read failed:[/red] " + error_line(result))
        return None
    return parse_recall(text_of(result))


async def walk(session) -> bool:
    await session.initialize()

    console.rule("Discovery")
    await discover(session)

    if not await seed(session):
        return False

    console.rule("Session 2 (Thursday)")
    console.print('Question: [bold]"' + QUESTION + '"[/bold]\n')
    before = await recall(session)
    if before is None:
        return False
    if not before:
        console.print("[red]Nothing was recalled, so there is nothing to rank.[/red]")
        return False
    show("Recall before feedback", before)
    console.print()
    answer_from(before, QUESTION)

    # The note that helped. In a real app this is a thumbs-up, an accepted
    # suggestion, or a task that ended up passing.
    helpful = next(
        (row for row in before if row[1].startswith("Release checklist")), None
    )
    if helpful is None:
        helpful = before[0]
        console.print(
            "[dim]The checklist note was not recalled this time, so the top "
            "result is marked instead.[/dim]"
        )

    console.rule("Reporting the outcome")
    console.print('Marking as helpful: [bold]"' + helpful[1] + '"[/bold]')
    rating = await session.call_tool(
        "memory_feedback", {"atom_ids": [helpful[2]], "outcome": 1.0}
    )
    if failed(rating):
        console.print("[red]memory_feedback failed:[/red] " + error_line(rating))
        return False
    console.print(text_of(rating).strip() + "\n")

    console.rule("Session 3 (Friday)")
    console.print('The same question again: [bold]"' + QUESTION + '"[/bold]\n')
    after = await recall(session)
    if after is None:
        return False
    show("Recall after feedback", after)

    was = {row[2]: row[0] for row in before}
    now = {row[2]: row[0] for row in after}
    moved = [
        (row[1], was[row[2]], row[0])
        for row in after
        if row[2] in was and was[row[2]] != row[0]
    ]
    console.print()
    if moved:
        table = Table(title="What moved", title_justify="left", header_style="bold")
        table.add_column("memory")
        table.add_column("was", width=5)
        table.add_column("now", width=5)
        for content, old, new in moved:
            table.add_row(Text(content), str(old), str(new))
        console.print(table)
    else:
        dropped = [c for c in was if c not in now]
        console.print(
            "[dim]No position changed"
            + (" and some memories left the result set" if dropped else "")
            + ". On a namespace that has already received this "
            "outcome the order is usually in place already. To watch the first "
            "move again, set MNEMOVERSE_DEMO_DOMAIN to a fresh value and run it "
            "once more.[/dim]"
        )

    return True


async def main() -> bool:
    require_key()
    server = StdioServerParameters(
        command=npx_path(),
        args=["-y", MEMORY_SERVER],
        # The model key stays in this process for answer_from; the MCP server
        # never needs it, so it is not passed to the child.
        env={k: v for k, v in os.environ.items() if k != "NEBIUS_API_KEY"},
    )
    try:
        async with (
            stdio_client(server) as (reader, writer),
            ClientSession(reader, writer) as session,
        ):
            return await walk(session)
    except BaseException as exc:  # noqa: BLE001 - one line beats a task-group traceback
        if _has(exc, KeyboardInterrupt):
            console.print("\n[dim]Stopped.[/dim]")
            return True
        console.print(
            "[red]The memory server did not finish the run.[/red] npx has to be "
            "able to fetch " + MEMORY_SERVER + " from the npm registry, and Node "
            "has to be 18 or newer. The underlying error was: "
            + _root(exc).__class__.__name__
            + ": "
            + str(_root(exc))[:200]
        )
        return False


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(main()) else 1)
