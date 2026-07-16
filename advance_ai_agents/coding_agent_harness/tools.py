"""Workspace tools for the Coding Agent Harness.

`read_file` and `list_dir` are ordinary read-only tools. `propose_edit`
is special: the coder node intercepts its tool calls and collects the
resulting FileDiff dicts into graph state (the review queue) instead of
writing anything to disk. Nothing in this module mutates the workspace —
only the graph's apply_diffs node does, and only after human approval.
"""
from __future__ import annotations

import difflib
import uuid
from pathlib import Path

from langchain_core.tools import tool

WORKSPACE_ROOT = Path(__file__).resolve().parent / "workspace"

IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".git"}


def _resolve_safe(path: str) -> Path:
    """Resolve `path` under WORKSPACE_ROOT, rejecting path traversal."""
    resolved = (WORKSPACE_ROOT / path).resolve()
    if not resolved.is_relative_to(WORKSPACE_ROOT.resolve()):
        raise ValueError(f"Path {path!r} escapes the workspace.")
    return resolved


@tool
def list_dir(path: str = ".") -> str:
    """List files and subdirectories under `path`, relative to the workspace root.

    Use this first to understand the project layout before reading files.
    Directories are suffixed with '/'.
    """
    try:
        target = _resolve_safe(path)
    except ValueError as exc:
        return f"ERROR: {exc}"
    if not target.is_dir():
        return f"ERROR: {path!r} is not a directory."
    entries = [
        f"{e.name}/" if e.is_dir() else e.name
        for e in sorted(target.iterdir())
        if e.name not in IGNORED_PARTS
    ]
    return "\n".join(entries) or "(empty directory)"


@tool
def read_file(path: str) -> str:
    """Read a file relative to the workspace root.

    Returns the content with 1-indexed line numbers prefixed (e.g.
    '12: def foo():'). Errors are returned as strings starting with
    'ERROR:' so you can recover.
    """
    try:
        target = _resolve_safe(path)
    except ValueError as exc:
        return f"ERROR: {exc}"
    if not target.is_file():
        return f"ERROR: {path!r} is not a file or does not exist."
    lines = target.read_text().splitlines()
    return "\n".join(f"{i}: {line}" for i, line in enumerate(lines, start=1))


def build_file_diff(
    file_path: str, new_content: str, rationale: str, iteration: int
) -> dict:
    """Compute a FileDiff dict for the pending review queue. No disk writes."""
    target = _resolve_safe(file_path)
    old_content = target.read_text() if target.is_file() else ""
    diff_lines = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    unified = "".join(diff_lines)
    return {
        "diff_id": uuid.uuid4().hex[:8],
        "file_path": file_path,
        "unified_diff": unified or "(no changes — file already matches proposal)",
        "rationale": rationale,
        "new_content": new_content,
        "proposed_at_iteration": iteration,
    }


@tool
def propose_edit(file_path: str, new_content: str, rationale: str) -> str:
    """Propose replacing `file_path`'s full contents, as a human-reviewable diff.

    This does NOT write to disk. Pass the COMPLETE new file content (not a
    patch or a fragment); a unified diff against the current file is
    computed for you and queued for human review.
    `rationale` is a one-sentence explanation shown to the reviewer, e.g.
    'Fix double-discount bug by setting discount instead of adding to it'.
    Call this once per file you want to change. If a previous proposal for
    the same file was rejected, read the reviewer feedback in your
    instructions and propose revised content.
    """
    # Schema/fallback implementation. During a graph run the coder node
    # intercepts this tool's calls so it can capture the FileDiff into state.
    diff = build_file_diff(file_path, new_content, rationale, iteration=0)
    return f"Diff {diff['diff_id']} for {file_path} queued for human review."


def list_workspace_tree() -> str:
    """Indented file tree of the workspace, for the planner prompt."""
    lines: list[str] = []
    for path in sorted(WORKSPACE_ROOT.rglob("*")):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        rel = path.relative_to(WORKSPACE_ROOT)
        indent = "  " * (len(rel.parts) - 1)
        lines.append(f"{indent}{rel.name}{'/' if path.is_dir() else ''}")
    return "\n".join(lines) or "(empty workspace)"
