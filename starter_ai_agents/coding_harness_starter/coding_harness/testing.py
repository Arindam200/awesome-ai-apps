"""The one deliberately small and fixed test runner used by the harness."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


TEST_COMMAND_DISPLAY = "python -m unittest discover -s tests -v"
TEST_ARGUMENTS: tuple[str, ...] = (
    sys.executable,
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-v",
)
DEFAULT_TEST_TIMEOUT_SECONDS = 30
DEFAULT_OUTPUT_LIMIT = 12 * 1024


@dataclass(frozen=True)
class TestResult:
    """A bounded record of a single fixed unittest invocation."""

    command: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return not self.timed_out and self.exit_code == 0

    def error_summary(self, limit: int = 1_500) -> str:
        """Return the useful tail without dumping an entire test log to the model."""
        output = "\n".join(part for part in (self.stdout, self.stderr) if part).strip()
        return _tail_truncate(output, limit)


def fixed_test_argv() -> list[str]:
    """Return a new copy so no caller can mutate the fixed command for later runs."""
    return list(TEST_ARGUMENTS)


def run_tests(
    workspace: Path | str | object,
    *,
    timeout_seconds: int = DEFAULT_TEST_TIMEOUT_SECONDS,
    output_limit: int = DEFAULT_OUTPUT_LIMIT,
) -> TestResult:
    """Run only stdlib unittest discovery in the locked workspace.

    ``workspace`` accepts either a path or the project's ``Workspace`` object.  No
    command string is accepted on purpose: neither the CLI nor a model may select
    what process this module launches.
    """
    root = _workspace_root(workspace)
    argv = fixed_test_argv()
    bounded_output_limit = max(0, min(output_limit, DEFAULT_OUTPUT_LIMIT))
    try:
        completed = subprocess.run(
            argv,
            cwd=str(root),
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        return TestResult(
            command=tuple(argv),
            exit_code=None,
            stdout=_truncate(_as_text(error.stdout), bounded_output_limit),
            stderr=_truncate(_as_text(error.stderr), bounded_output_limit),
            timed_out=True,
        )

    return TestResult(
        command=tuple(argv),
        exit_code=completed.returncode,
        stdout=_truncate(completed.stdout, bounded_output_limit),
        stderr=_truncate(completed.stderr, bounded_output_limit),
    )


def _workspace_root(workspace: Path | str | object) -> Path:
    # pathlib.Path itself has a ``root`` property (``C:\\`` on Windows), so
    # only unwrap the project's Workspace-like objects after handling paths.
    root = (
        workspace
        if isinstance(workspace, (Path, str))
        else getattr(workspace, "root", workspace)
    )
    return Path(root).resolve()


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _truncate(value: str | bytes | None, limit: int) -> str:
    text = _as_text(value)
    if limit < 1:
        return ""
    if len(text) <= limit:
        return text
    marker = "\n... [output truncated]"
    if limit <= len(marker):
        return text[:limit]
    return text[: limit - len(marker)] + marker


def _tail_truncate(value: str | bytes | None, limit: int) -> str:
    """Keep the end of a diagnostic, where unittest reports failures."""

    text = _as_text(value)
    if limit < 1:
        return ""
    if len(text) <= limit:
        return text
    marker = "... [output truncated]\n"
    if limit <= len(marker):
        return text[-limit:]
    return marker + text[-(limit - len(marker)) :]
