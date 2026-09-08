"""Structured data exchanged by the coding harness."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FileChange(BaseModel):
    """A complete replacement proposed for one workspace file."""

    path: str = Field(description="Path relative to the configured workspace root")
    new_content: str = Field(description="Complete new contents for the file")
    reason: str = Field(description="Short explanation of why the change is needed")


class ChangeProposal(BaseModel):
    """The agent's human-reviewable plan and proposed changes."""

    plan: list[str] = Field(min_length=1, max_length=6)
    changes: list[FileChange] = Field(min_length=1, max_length=5)
    summary: str


class TestResult(BaseModel):
    """Result of the one allowlisted test command."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        """Return whether pytest exited successfully."""
        return self.returncode == 0


class RunSummary(BaseModel):
    """Final machine-readable harness result."""

    status: str
    changed_files: list[str] = Field(default_factory=list)
    tests: TestResult | None = None
    error: str | None = None
