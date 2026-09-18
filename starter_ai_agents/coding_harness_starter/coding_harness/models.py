"""Structured, untrusted model output used by the local harness."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImplementationPlan(BaseModel):
    """A deliberately short, reviewable implementation plan."""

    model_config = ConfigDict(extra="forbid")

    task_understanding: str = Field(min_length=1)
    files_to_modify: list[str] = Field(default_factory=list)
    steps: list[str] = Field(min_length=1)
    tests: list[str] = Field(default_factory=list)
    risks_and_assumptions: list[str] = Field(default_factory=list)


class FileOperation(BaseModel):
    """One proposed file mutation.

    This is data only.  It intentionally contains no command or executable
    expression; :mod:`patching` validates it before the filesystem is touched.
    """

    model_config = ConfigDict(extra="forbid")

    operation: Literal["create", "update"]
    path: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    content: str | None = None
    expected_old_text: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "FileOperation":
        if self.operation == "create":
            if self.content is None:
                raise ValueError("create operations require content")
            if self.expected_old_text is not None:
                raise ValueError(
                    "create operations must not include an expected current value"
                )
        elif self.operation == "update":
            if self.content is None or self.expected_old_text is None:
                raise ValueError(
                    "update operations require content and expected_old_text"
                )
            if not self.expected_old_text:
                raise ValueError("update expected_old_text cannot be empty")
        return self


class PatchProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: ImplementationPlan
    operations: list[FileOperation] = Field(min_length=1)

    @model_validator(mode="after")
    def paths_are_unique(self) -> "PatchProposal":
        paths = [operation.path for operation in self.operations]
        if len(paths) != len(set(paths)):
            raise ValueError("a patch proposal cannot contain duplicate file paths")
        return self


class TestRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    argv: list[str]
    exit_code: int | None
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""


class TokenUsage(BaseModel):
    """Nebius token totals accumulated across one harness run."""

    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)

    def plus(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class RunSummary(BaseModel):
    """Stable end-of-run data for the CLI, rather than presentation text."""

    model_config = ConfigDict(extra="forbid")

    task: str
    status: Literal["success", "cancelled", "test_failed", "apply_failed", "no_patch"]
    attempts: int = Field(ge=0, le=3)
    created_files: list[str] = Field(default_factory=list)
    updated_files: list[str] = Field(default_factory=list)
    test_runs: list[TestRunRecord] = Field(default_factory=list)
    token_usage: TokenUsage | None = None
    message: str = ""
