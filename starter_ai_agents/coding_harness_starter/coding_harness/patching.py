"""Validate structured patch proposals, render diffs, then apply approved work."""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import os
from pathlib import Path
import stat
import tempfile
from typing import Iterable

from .models import FileOperation, PatchProposal
from .workspace import Workspace, WorkspaceError


class PatchValidationError(ValueError):
    """The complete patch is unsafe or cannot be applied to its current state."""


class PatchStateChangedError(PatchValidationError):
    """The workspace changed after preview and must be inspected again."""


class PatchApplyError(RuntimeError):
    """An error occurred after one or more deterministic operations completed."""

    def __init__(
        self,
        message: str,
        applied_paths: list[str],
        unapplied_paths: list[str],
    ) -> None:
        super().__init__(message)
        self.applied_paths = applied_paths
        self.unapplied_paths = unapplied_paths


@dataclass(frozen=True)
class PreparedOperation:
    operation: FileOperation
    path: Path
    relative_path: str
    before_text: str | None
    after_text: str | None


@dataclass(frozen=True)
class PreparedPatch:
    workspace: Workspace
    operations: tuple[PreparedOperation, ...]

    @property
    def diff(self) -> str:
        return render_unified_diff(self)

    @property
    def created_files(self) -> list[str]:
        return [
            item.relative_path
            for item in self.operations
            if item.operation.operation == "create"
        ]

    @property
    def updated_files(self) -> list[str]:
        return [
            item.relative_path
            for item in self.operations
            if item.operation.operation == "update"
        ]


def _operations_from(
    proposal_or_operations: PatchProposal | Iterable[FileOperation],
) -> list[FileOperation]:
    operations = list(
        proposal_or_operations.operations
        if isinstance(proposal_or_operations, PatchProposal)
        else proposal_or_operations
    )
    if not operations:
        raise PatchValidationError("a patch must contain at least one operation")
    if not all(isinstance(operation, FileOperation) for operation in operations):
        raise PatchValidationError("patch operations must be FileOperation instances")
    return operations


def _validated_operation(
    workspace: Workspace, operation: FileOperation
) -> PreparedOperation:
    try:
        if operation.operation == "create":
            path = workspace.validate_text_path(operation.path)
            if path.exists():
                raise PatchValidationError("create target already exists")
            if not path.parent.exists() or not path.parent.is_dir():
                parent = workspace.relative_path(path.parent)
                raise PatchValidationError(
                    f"cannot create {operation.path!r}: parent directory "
                    f"'{parent}' does not exist; this patch has not written any "
                    "files, and this MVP does not create directories"
                )
            workspace.validate_text_content(operation.content or "")
            return PreparedOperation(
                operation, path, workspace.relative_path(path), None, operation.content
            )

        path, current_text = workspace.read_text_path(operation.path)
        relative = workspace.relative_path(path)
        expected = operation.expected_old_text
        assert expected is not None  # model validation established this invariant
        if current_text.count(expected) != 1:
            raise PatchValidationError(
                "update expected_old_text must match exactly once"
            )
        replacement = current_text.replace(expected, operation.content or "", 1)
        workspace.validate_text_content(replacement)
        return PreparedOperation(operation, path, relative, current_text, replacement)
    except WorkspaceError as error:
        raise PatchValidationError(str(error)) from error


def prepare_patch(
    workspace: Workspace,
    proposal_or_operations: PatchProposal | Iterable[FileOperation],
) -> PreparedPatch:
    """Fully validate a proposal before it can be previewed or applied.

    No filesystem writes happen here.  Duplicate normalized paths are rejected
    so proposal ordering can never cause two operations to conflict.
    """

    operations = _operations_from(proposal_or_operations)
    prepared = [_validated_operation(workspace, operation) for operation in operations]
    # Reject case aliases portably so a prepared patch remains safe when the
    # workspace lives on a case-insensitive volume on any host OS.
    collision_keys = [item.relative_path.casefold() for item in prepared]
    if len(collision_keys) != len(set(collision_keys)):
        raise PatchValidationError(
            "a patch cannot contain duplicate or conflicting target paths"
        )
    return PreparedPatch(
        workspace, tuple(sorted(prepared, key=lambda item: item.relative_path))
    )


def _diff_lines(text: str | None) -> list[str]:
    return [] if text is None else text.splitlines()


def render_unified_diff(prepared_patch: PreparedPatch) -> str:
    """Render deterministic, local unified diffs for all proposed operations."""

    sections: list[str] = []
    for item in prepared_patch.operations:
        before_name, after_name = (
            ("/dev/null", f"b/{item.relative_path}")
            if item.operation.operation == "create"
            else (f"a/{item.relative_path}", f"b/{item.relative_path}")
        )
        lines = difflib.unified_diff(
            _diff_lines(item.before_text),
            _diff_lines(item.after_text),
            fromfile=before_name,
            tofile=after_name,
            lineterm="",
        )
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _assert_current_state(item: PreparedOperation) -> None:
    path = item.path
    if path.is_symlink():
        raise PatchStateChangedError(f"{item.relative_path} became a symbolic link")
    # Re-validate only through the workspace owned by the caller; this helper
    # handles the content snapshot after that path-policy check has occurred.
    if item.operation.operation == "create":
        if path.exists():
            raise PatchStateChangedError(
                f"create target changed: {item.relative_path} now exists"
            )
        return
    if not path.exists() or not path.is_file():
        raise PatchStateChangedError(
            f"target changed: {item.relative_path} no longer exists"
        )
    try:
        current = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise PatchStateChangedError(
            f"target changed: {item.relative_path} is no longer UTF-8 text"
        ) from error
    if current != item.before_text:
        raise PatchStateChangedError(
            f"target changed after preview: {item.relative_path}"
        )


def _write_utf8_atomically(path: Path, content: str) -> None:
    target_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    descriptor, temp_name = tempfile.mkstemp(
        prefix=".coding-harness-", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.chmod(temp_name, target_mode)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def apply_prepared_patch(prepared_patch: PreparedPatch) -> list[str]:
    """Apply an already approved patch in deterministic path order.

    All operations are rechecked before the first write.  Each is checked again
    immediately before its mutation so an external edit never gets overwritten
    silently.  This is intentionally not a rollback transaction.
    """

    workspace = prepared_patch.workspace
    try:
        for item in prepared_patch.operations:
            workspace.validate_text_path(
                item.relative_path, require_exists=item.operation.operation != "create"
            )
            _assert_current_state(item)
    except WorkspaceError as error:
        raise PatchStateChangedError(str(error)) from error

    applied: list[str] = []
    try:
        for item in prepared_patch.operations:
            try:
                workspace.validate_text_path(
                    item.relative_path,
                    require_exists=item.operation.operation != "create",
                )
                _assert_current_state(item)
                assert item.after_text is not None
                _write_utf8_atomically(item.path, item.after_text)
                applied.append(item.relative_path)
            except (WorkspaceError, PatchStateChangedError) as error:
                raise PatchStateChangedError(str(error)) from error
    except Exception as error:
        if isinstance(error, PatchStateChangedError) and not applied:
            raise
        unapplied = [
            item.relative_path
            for item in prepared_patch.operations
            if item.relative_path not in applied
        ]
        raise PatchApplyError(
            "patch application stopped after "
            f"{len(applied)} operation(s): {error}. "
            f"Applied: {', '.join(applied) or '(none)'}. "
            f"Not applied: {', '.join(unapplied) or '(none)'}.",
            applied,
            unapplied,
        ) from error
    return applied
