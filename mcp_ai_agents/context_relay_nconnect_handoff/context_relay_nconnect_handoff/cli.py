"""Inspect Context Relay's real stdio MCP server without sending data to an LLM."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError

PROCESS_TIMEOUT_SECONDS = 60
MCP_TIMEOUT = timedelta(seconds=30)
HANDLED_ERRORS = (
    OSError,
    KeyError,
    ValueError,
    TypeError,
    RuntimeError,
    subprocess.TimeoutExpired,
    McpError,
)

REQUIRED_TOOLS = {
    "relay_handoff_inspect",
    "relay_handoff_accept",
    "relay_packet",
}


def _relay_args(command: list[str], data_dir: Path | None) -> list[str]:
    """Keep every Relay command in the selected local profile."""
    return [*command, *(["--data-dir", str(data_dir)] if data_dir else [])]


def _run_relay(relay_bin: str, command: list[str], data_dir: Path) -> dict[str, Any]:
    """Run a bounded Relay command and require a JSON object response."""
    completed = subprocess.run(
        [shutil.which(relay_bin) or relay_bin, *_relay_args(command, data_dir)],
        capture_output=True,
        text=True,
        check=False,
        timeout=PROCESS_TIMEOUT_SECONDS,
    )
    if completed.returncode:
        raise RuntimeError(f"Context Relay {command[0]} failed (exit {completed.returncode})")
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise TypeError(f"Context Relay {command[0]} returned an unexpected response")
    return value


def _tool_json(result: Any, name: str) -> dict[str, Any]:
    """Reject tool errors and malformed responses before using their contents."""
    if result.isError:
        raise RuntimeError(f"MCP tool {name} failed")
    blocks = [block.text for block in result.content if block.type == "text"]
    if len(blocks) != 1:
        raise RuntimeError(f"MCP tool {name} did not return one JSON text block")
    value = json.loads(blocks[0])
    if not isinstance(value, dict):
        raise TypeError(f"MCP tool {name} returned an unexpected response")
    return value


def _stop_relay(relay_bin: str, data_dir: Path) -> None:
    """Stop an owned temporary profile and wait for its database to close."""
    lock = data_dir / "service.lock"
    if not lock.exists():
        return
    _run_relay(relay_bin, ["stop"], data_dir)
    deadline = time.monotonic() + 10
    while lock.exists():
        if time.monotonic() >= deadline:
            raise RuntimeError("Temporary Relay service did not stop within 10 seconds")
        time.sleep(0.05)


@contextmanager
def _temporary_profile(relay_bin: str):
    """Release the temporary service before removing its files, including on failure."""
    with tempfile.TemporaryDirectory(prefix="relay-nconnect-") as directory:
        data_dir = Path(directory)
        try:
            yield data_dir
        finally:
            _stop_relay(relay_bin, data_dir)


async def probe_handoff(
    project_id: str,
    handoff_id: str,
    *,
    relay_bin: str = "relay",
    data_dir: Path | None = None,
    accept_synthetic: bool = False,
) -> dict[str, Any]:
    """Read a Codex-addressed handoff; acknowledge only a disposable demo fixture."""
    params = StdioServerParameters(
        command=shutil.which(relay_bin) or relay_bin,
        args=_relay_args(
            ["mcp", "--project", project_id, "--harness", "codex"],
            data_dir,
        ),
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write, read_timeout_seconds=MCP_TIMEOUT) as session,
    ):
        await session.initialize()
        names = {tool.name for tool in (await session.list_tools()).tools}
        missing = REQUIRED_TOOLS - names
        if missing:
            raise RuntimeError(f"Context Relay MCP tools missing: {', '.join(sorted(missing))}")

        handoff = _tool_json(
            await session.call_tool("relay_handoff_inspect", {"handoffId": handoff_id}),
            "relay_handoff_inspect",
        )
        packet = handoff.get("packet", {})
        if handoff.get("recipient") != "codex" or packet.get("project", {}).get("id") != project_id:
            raise RuntimeError("Handoff recipient or project does not match the MCP connection")
        if packet.get("version") != "relay.packet/v1":
            raise RuntimeError("Unsupported Context Relay packet version")

        packet_result = _tool_json(
            await session.call_tool("relay_packet", {"checkpointId": handoff["checkpointId"]}),
            "relay_packet",
        )
        if packet_result.get("packet", {}).get("checkpointId") != handoff["checkpointId"]:
            raise RuntimeError("MCP packet does not match the inspected handoff")

        summary = {
            "projectId": project_id,
            "handoffId": handoff_id,
            "recipient": "codex",
            "goal": packet.get("goal"),
            "status": handoff.get("status"),
            "packetVersion": packet["version"],
            "mcpToolsVerified": sorted(REQUIRED_TOOLS),
            "freshness": packet_result.get("freshness"),
        }
        if accept_synthetic:
            if handoff.get("status") != "offered":
                raise RuntimeError("Synthetic handoff is not offered")
            accepted = _tool_json(
                await session.call_tool("relay_handoff_accept", {"handoffId": handoff_id}),
                "relay_handoff_accept",
            )
            if accepted.get("status") != "accepted":
                raise RuntimeError("Synthetic handoff was not acknowledged")
            summary["status"] = "accepted"
            summary["synthetic"] = True
        return summary


def _demo(relay_bin: str, data_dir: Path) -> dict[str, Any]:
    """Create and accept only the fixture identified by Relay as synthetic."""
    fixture = _run_relay(relay_bin, ["demo"], data_dir)
    if fixture.get("synthetic") is not True:
        raise RuntimeError("The demo did not create synthetic data")
    return asyncio.run(
        probe_handoff(
            fixture["projectId"],
            fixture["handoffId"],
            relay_bin=relay_bin,
            data_dir=data_dir,
            accept_synthetic=True,
        )
    )


def _option_values(args: list[str], option: str) -> list[str]:
    """Read both --option value and --option=value, retaining duplicate flags."""
    return [
        args[index + 1] if arg == option and index + 1 < len(args) else arg[len(option) + 1 :]
        for index, arg in enumerate(args)
        if arg == option or arg.startswith(option + "=")
    ]


def check_nconnect(model: str, nconnect_bin: str, project_id: str) -> dict[str, Any]:
    """Check the enabled server's configured project and harness, without starting MCP."""
    completed = subprocess.run(
        [
            shutil.which(nconnect_bin) or nconnect_bin,
            "--model",
            model,
            "codex",
            "mcp",
            "list",
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=PROCESS_TIMEOUT_SECONDS,
        check=False,
        env={**os.environ, "NCONNECT_DISABLE_AUTOUPDATE": "1"},
    )
    if completed.returncode:
        raise RuntimeError(
            "NConnect could not start Codex MCP listing; check NConnect, Codex and Nebius setup"
        )
    servers = json.loads(completed.stdout)
    if not isinstance(servers, list) or not all(isinstance(server, dict) for server in servers):
        raise ValueError("Codex MCP listing must be a JSON array of server objects")
    matches = [server for server in servers if server.get("name") == "context_relay"]
    if len(matches) != 1 or matches[0].get("enabled") is not True:
        raise RuntimeError(
            "Codex did not list an enabled context_relay MCP server; connect Relay and trust this project"
        )
    transport = matches[0].get("transport") or {}
    if not isinstance(transport, dict):
        raise TypeError("context_relay transport must be a JSON object")
    args = transport.get("args", [])
    if (
        transport.get("type") != "stdio"
        or not isinstance(args, list)
        or not all(isinstance(arg, str) for arg in args)
        or "mcp" not in args
        or _option_values(args, "--project") != [project_id]
        or _option_values(args, "--harness") != ["codex"]
    ):
        raise RuntimeError("context_relay is not configured for this project and the codex harness")
    return {
        "harness": "codex",
        "mcpServer": "context_relay",
        "status": "enabled",
        "projectId": project_id,
        "configurationOnly": True,
        "nconnectModelSelection": model,
        "modelRequestSent": False,
    }


def _handled_leaves(exc: BaseException) -> list[BaseException]:
    """Flatten known errors; preserve a whole group if any leaf is unexpected.

    Accessing .exceptions works with both Python 3.11's exception groups and
    AnyIO's Python 3.10 backport, without using the 3.11-only except* syntax.
    """
    children = getattr(exc, "exceptions", None)
    if children is None:
        return [exc] if isinstance(exc, HANDLED_ERRORS) else []
    leaves = []
    for child in children:
        handled = _handled_leaves(child)
        if not handled:
            return []
        leaves.extend(handled)
    return leaves


def main(argv: list[str] | None = None) -> int:
    """Print JSON on success and concise expected errors on stderr."""
    parser = argparse.ArgumentParser(
        description="Verify a Context Relay handoff through its stdio MCP tools."
    )
    parser.add_argument(
        "--relay-bin",
        default=os.environ.get("CONTEXT_RELAY_BIN", "relay"),
        help="Context Relay executable (default: relay)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Create and acknowledge a disposable synthetic handoff")
    demo.add_argument(
        "--data-dir", type=Path, help="Keep the synthetic profile here for inspection"
    )
    inspect = commands.add_parser(
        "inspect", help="Read a real offered handoff without accepting it"
    )
    inspect.add_argument("--project-id", required=True)
    inspect.add_argument("--handoff-id", required=True)
    inspect.add_argument("--data-dir", type=Path, help="Context Relay profile, if not the default")
    check = commands.add_parser(
        "check", help="Verify NConnect-launched Codex sees Relay's MCP entry"
    )
    check.add_argument("--model", default="zai-org/GLM-5.3-Flash")
    check.add_argument("--project-id", required=True, help="Expected Relay project ID")
    check.add_argument("--nconnect-bin", default=os.environ.get("NCONNECT_BIN", "nconnect"))
    args = parser.parse_args(argv)

    try:
        if args.command == "demo":
            if args.data_dir:
                args.data_dir.mkdir(parents=True, exist_ok=True)
                result = _demo(args.relay_bin, args.data_dir)
            else:
                with _temporary_profile(args.relay_bin) as data_dir:
                    result = _demo(args.relay_bin, data_dir)
        elif args.command == "inspect":
            result = asyncio.run(
                probe_handoff(
                    args.project_id,
                    args.handoff_id,
                    relay_bin=args.relay_bin,
                    data_dir=args.data_dir,
                )
            )
        else:
            result = check_nconnect(args.model, args.nconnect_bin, args.project_id)
    except Exception as exc:
        errors = _handled_leaves(exc)
        if not errors:
            raise
        for message in dict.fromkeys(str(error) for error in errors):
            print(f"relay-nconnect-demo: {message}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
