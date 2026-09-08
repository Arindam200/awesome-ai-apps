"""Read-only PydanticAI tools for repository inspection."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import RunContext

from workspace import Workspace, WorkspaceViolation


@dataclass
class AgentDependencies:
    """Runtime dependencies available to the agent's tools."""

    workspace: Workspace


def list_files(ctx: RunContext[AgentDependencies]) -> list[str]:
    """List all files under the configured workspace."""
    return ctx.deps.workspace.list_files()


def read_file(ctx: RunContext[AgentDependencies], path: str) -> str:
    """Read one file using a path relative to the configured workspace."""
    try:
        return ctx.deps.workspace.read_file(path)
    except WorkspaceViolation as exc:
        return f"ERROR: {exc}"
