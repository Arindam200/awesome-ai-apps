"""Inspect Context Relay's real stdio MCP server without sending data to an LLM."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REQUIRED_TOOLS = {
    "relay_handoff_inspect",
    "relay_handoff_accept",
    "relay_packet",
}


def _relay_args(command: list[str], data_dir: Path | None) -> list[str]:
    return [*command, *(["--data-dir", str(data_dir)] if data_dir else [])]


def _run_relay(relay_bin: str, command: list[str], data_dir: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [relay_bin, *_relay_args(command, data_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"Context Relay {command[0]} failed (exit {completed.returncode})")
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise TypeError(f"Context Relay {command[0]} returned an unexpected response")
    return value


def _tool_json(result: Any, name: str) -> dict[str, Any]:
    if result.isError:
        raise RuntimeError(f"MCP tool {name} failed")
    blocks = [block.text for block in result.content if block.type == "text"]
    if len(blocks) != 1:
        raise RuntimeError(f"MCP tool {name} did not return one JSON text block")
    value = json.loads(blocks[0])
    if not isinstance(value, dict):
        raise TypeError(f"MCP tool {name} returned an unexpected response")
    return value


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
        command=relay_bin,
        args=_relay_args(
            ["mcp", "--project", project_id, "--harness", "codex"],
            data_dir,
        ),
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
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


def check_nconnect(model: str, nconnect_bin: str) -> dict[str, Any]:
    """Check that NConnect-launched Codex can see this project's Relay MCP entry."""
    completed = subprocess.run(
        [nconnect_bin, "--model", model, "codex", "mcp", "list"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, "NCONNECT_DISABLE_AUTOUPDATE": "1"},
    )
    if completed.returncode:
        raise RuntimeError(
            "NConnect could not start Codex MCP listing; check NConnect, Codex and Nebius setup"
        )
    line = next(
        (
            line
            for line in completed.stdout.splitlines()
            if line.strip().startswith("context_relay ")
        ),
        "",
    )
    if "enabled" not in line.split():
        raise RuntimeError(
            "Codex did not list an enabled context_relay MCP server; connect Relay and trust this project"
        )
    return {
        "harness": "codex",
        "mcpServer": "context_relay",
        "status": "enabled",
        "nconnectModelSelection": model,
        "modelRequestSent": False,
    }


def main(argv: list[str] | None = None) -> int:
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
    check.add_argument("--nconnect-bin", default=os.environ.get("NCONNECT_BIN", "nconnect"))
    args = parser.parse_args(argv)

    try:
        if args.command == "demo":
            if args.data_dir:
                args.data_dir.mkdir(parents=True, exist_ok=True)
                result = _demo(args.relay_bin, args.data_dir)
            else:
                with tempfile.TemporaryDirectory(prefix="relay-nconnect-") as directory:
                    result = _demo(args.relay_bin, Path(directory))
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
            result = check_nconnect(args.model, args.nconnect_bin)
    except (
        OSError,
        KeyError,
        ValueError,
        TypeError,
        RuntimeError,
        subprocess.TimeoutExpired,
    ) as exc:
        print(f"relay-nconnect-demo: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
