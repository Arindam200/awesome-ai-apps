from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from main import approved_by_human, preview_changes
from models import FileChange
from workspace import ALLOWED_TEST_COMMAND, Workspace, WorkspaceViolation


def change(path: str, content: str = "updated\n") -> FileChange:
    """Build a small valid proposal for workspace tests."""
    return FileChange(path=path, new_content=content, reason="test change")


def test_lists_and_reads_only_workspace_files(tmp_path: Path) -> None:
    """Workspace inspection returns bounded relative paths and contents."""
    (tmp_path / "module.py").write_text("value = 1\n", encoding="utf-8")
    workspace = Workspace(tmp_path)

    assert workspace.list_files() == ["module.py"]
    assert workspace.read_file("module.py") == "value = 1\n"


def test_rejects_path_traversal(tmp_path: Path) -> None:
    """Parent traversal cannot escape the configured root."""
    workspace = Workspace(tmp_path)

    with pytest.raises(WorkspaceViolation, match="escapes"):
        workspace.read_file("../secret.txt")


def test_rejects_symlink_that_escapes_workspace(tmp_path: Path) -> None:
    """A symlink cannot provide an alias to an external file."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    (workspace_root / "link.txt").symlink_to(outside)

    with pytest.raises(WorkspaceViolation, match="escapes"):
        Workspace(workspace_root).read_file("link.txt")


def test_does_not_expose_environment_files(tmp_path: Path) -> None:
    """Environment files stay hidden even behind an in-workspace symlink."""
    (tmp_path / ".env").write_text("API_KEY=secret\n", encoding="utf-8")
    (tmp_path / "config.txt").symlink_to(tmp_path / ".env")
    workspace = Workspace(tmp_path)

    assert workspace.list_files() == []
    with pytest.raises(WorkspaceViolation, match="not exposed"):
        workspace.read_file(".env")
    with pytest.raises(WorkspaceViolation, match="not exposed"):
        workspace.read_file("config.txt")


def test_requires_approval_before_writing(tmp_path: Path) -> None:
    """The workspace rejects writes without an affirmative human gate."""
    target = tmp_path / "module.py"
    target.write_text("original\n", encoding="utf-8")
    workspace = Workspace(tmp_path)

    with pytest.raises(PermissionError, match="explicit human approval"):
        workspace.apply_changes([change("module.py")], approved=False)

    assert target.read_text(encoding="utf-8") == "original\n"


def test_applies_an_approved_change(tmp_path: Path) -> None:
    """An approved proposal may update a file within the workspace."""
    target = tmp_path / "module.py"
    target.write_text("original\n", encoding="utf-8")
    workspace = Workspace(tmp_path)

    changed = workspace.apply_changes([change("module.py")], approved=True)

    assert changed == ["module.py"]
    assert target.read_text(encoding="utf-8") == "updated\n"


def test_rolls_back_an_incomplete_multi_file_change(tmp_path: Path) -> None:
    """A later invalid target restores files changed earlier in the batch."""
    first = tmp_path / "first.py"
    first.write_text("original\n", encoding="utf-8")
    (tmp_path / "not_a_file").mkdir()
    workspace = Workspace(tmp_path)

    with pytest.raises(WorkspaceViolation, match="not a file"):
        workspace.apply_changes(
            [change("first.py"), change("not_a_file")], approved=True
        )

    assert first.read_text(encoding="utf-8") == "original\n"


def test_failed_batch_removes_new_parent_directories(
    tmp_path: Path, monkeypatch
) -> None:
    """Rollback removes empty parent directories created by the batch."""
    original_write_text = Path.write_text

    def fail_second_write(path: Path, *args, **kwargs):
        """Simulate an I/O failure after the first file is written."""
        if path.name == "second.py":
            raise OSError("simulated write failure")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_second_write)
    workspace = Workspace(tmp_path)

    with pytest.raises(WorkspaceViolation, match="Could not apply"):
        workspace.apply_changes(
            [change("new/nested/first.py"), change("second.py")], approved=True
        )

    assert not (tmp_path / "new").exists()
    assert not (tmp_path / "second.py").exists()


def test_rejects_non_utf8_files(tmp_path: Path) -> None:
    """Binary data becomes a recoverable workspace violation."""
    (tmp_path / "binary.dat").write_bytes(b"\xff\xfe")

    with pytest.raises(WorkspaceViolation, match="not valid UTF-8"):
        Workspace(tmp_path).read_file("binary.dat")


def test_diff_preview_enforces_existing_file_size(tmp_path: Path, monkeypatch) -> None:
    """Diff rendering does not read an oversized existing file."""
    (tmp_path / "large.py").write_text("12345", encoding="utf-8")
    monkeypatch.setattr("workspace.MAX_FILE_SIZE", 4)

    with pytest.raises(WorkspaceViolation, match="read limit"):
        Workspace(tmp_path).preview_diff(change("large.py", "ok"))


def test_diff_preview_enforces_proposed_file_size(tmp_path: Path, monkeypatch) -> None:
    """Diff rendering rejects oversized model output before splitting it."""
    monkeypatch.setattr("workspace.MAX_FILE_SIZE", 4)

    with pytest.raises(WorkspaceViolation, match="Proposed content"):
        Workspace(tmp_path).preview_diff(change("new.py", "12345"))


def test_invalid_preview_emits_a_structured_summary(tmp_path: Path, capsys) -> None:
    """An unsafe proposal is rejected before the approval prompt."""
    rendered = preview_changes(Workspace(tmp_path), [change("../escape.py")])

    assert not rendered
    output = capsys.readouterr().out
    assert '"status": "invalid_proposal"' in output
    assert '"error":' in output


def test_preview_rejects_duplicate_paths(tmp_path: Path, capsys) -> None:
    """Duplicate targets are rejected before any diff is rendered."""
    rendered = preview_changes(
        Workspace(tmp_path), [change("same.py"), change("same.py")]
    )

    assert not rendered
    output = capsys.readouterr().out
    assert '"status": "invalid_proposal"' in output
    assert "Duplicate change" in output
    assert "PATCH PREVIEW" not in output


def test_preview_rejects_directory_target(tmp_path: Path, capsys) -> None:
    """Existing directories cannot reach the approval prompt as file targets."""
    (tmp_path / "package").mkdir()

    rendered = preview_changes(Workspace(tmp_path), [change("package")])

    assert not rendered
    output = capsys.readouterr().out
    assert '"status": "invalid_proposal"' in output
    assert "Target is not a file" in output
    assert "PATCH PREVIEW" not in output


def test_runs_only_the_predefined_pytest_command(tmp_path: Path) -> None:
    """Test execution uses the immutable argument list and no shell."""
    (tmp_path / "test_example.py").write_text(
        "def test_example():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )

    result = Workspace(tmp_path).run_tests()

    assert result.command == list(ALLOWED_TEST_COMMAND)
    assert result.command == [sys.executable, "-m", "pytest", "-q"]
    assert result.passed


def test_test_timeout_returns_a_structured_failure(tmp_path: Path, monkeypatch) -> None:
    """A pytest timeout is represented by a failed TestResult."""

    def raise_timeout(*args, **kwargs):
        """Simulate a child process that exceeds its deadline."""
        raise subprocess.TimeoutExpired(
            cmd=list(ALLOWED_TEST_COMMAND),
            timeout=1,
            output="partial output",
            stderr="partial error",
        )

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    result = Workspace(tmp_path).run_tests(timeout_seconds=1)

    assert result.returncode == 124
    assert result.stdout == "partial output"
    assert "partial error" in result.stderr
    assert "timed out after 1 seconds" in result.stderr


def test_approved_fixture_fix_turns_red_tests_green(tmp_path: Path) -> None:
    """The approved edit and predefined command complete a red-green loop."""
    (tmp_path / "calculator.py").write_text(
        "def add(left, right):\n    return left - right\n", encoding="utf-8"
    )
    (tmp_path / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    workspace = Workspace(tmp_path)

    assert not workspace.run_tests().passed
    workspace.apply_changes(
        [
            change(
                "calculator.py",
                "def add(left, right):\n    return left + right\n",
            )
        ],
        approved=True,
    )

    assert workspace.run_tests().passed


@pytest.mark.parametrize("answer", ["y", "Y", "yes", " YES "])
def test_accepts_explicit_approval(answer: str) -> None:
    """Only clear affirmative spellings open the write gate."""
    assert approved_by_human(answer)


@pytest.mark.parametrize("answer", ["", "n", "no", "sure", "ok"])
def test_rejects_ambiguous_approval(answer: str) -> None:
    """Empty, negative, and ambiguous responses keep the gate closed."""
    assert not approved_by_human(answer)
