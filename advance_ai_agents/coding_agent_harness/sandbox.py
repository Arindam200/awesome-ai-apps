"""E2B sandbox wrapper: run the workspace's pytest suite in an isolated VM."""
from __future__ import annotations

from pathlib import Path

from e2b import Sandbox

try:  # raised by commands.run on a non-zero exit code (e.g. failing tests)
    from e2b import CommandExitException
except ImportError:  # older e2b versions export it from the exceptions module
    from e2b.exceptions import CommandExitException  # type: ignore[no-redef]

SANDBOX_WORKDIR = "/home/user/workspace"
IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".git"}


def run_pytest_in_sandbox(workspace_root: Path, test_path: str = "tests") -> dict:
    """Upload the workspace to a fresh E2B sandbox, run pytest, report back.

    Returns: {"passed": bool, "summary": str, "stdout": str, "returncode": int}
    """
    sandbox = Sandbox.create(timeout=300)
    try:
        for file in sorted(workspace_root.rglob("*")):
            if not file.is_file() or any(p in IGNORED_PARTS for p in file.parts):
                continue
            rel = file.relative_to(workspace_root)
            sandbox.files.write(f"{SANDBOX_WORKDIR}/{rel}", file.read_text())

        sandbox.commands.run("pip install -q pytest", timeout=120)
        try:
            proc = sandbox.commands.run(
                f"cd {SANDBOX_WORKDIR} && python -m pytest {test_path} -q",
                timeout=180,
            )
            returncode, stdout, stderr = proc.exit_code, proc.stdout, proc.stderr
        except CommandExitException as exc:
            returncode = exc.exit_code
            stdout, stderr = exc.stdout, exc.stderr
    finally:
        try:
            sandbox.kill()
        except Exception:
            pass

    output = (stdout + ("\n" + stderr if stderr else "")).strip()
    summary_lines = [line for line in stdout.strip().splitlines() if line.strip()]
    return {
        "passed": returncode == 0,
        "summary": summary_lines[-1] if summary_lines else f"exit code {returncode}",
        "stdout": output[-4000:],
        "returncode": returncode,
    }
