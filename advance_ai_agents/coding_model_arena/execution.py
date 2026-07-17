"""Runs a candidate's code against a challenge's hidden tests.

Default backend is a local subprocess with a timeout, which is fine for the small,
pure-algorithmic presets shipped here. Set ``SANDBOX_BACKEND=contree`` (with
NEBIUS_API_KEY / NEBIUS_PROJECT_ID and Nebius Sandboxes access) to instead run
each submission in an isolated Nebius Sandboxes container, using the same
Contree-backed isolation used by the companion `branching_agent_race` demo.

This is a demo execution harness, not a production sandbox: the local
backend trusts the machine it runs on. Don't expose it on the open internet
without swapping in the Contree backend (or E2B, as `coding_agent_harness`
does) for real isolation.
"""

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass

from challenges import HiddenTest

TIMEOUT_SECONDS = 12
SUCCESS_MARKER = "ALL_TESTS_PASSED"
RESULTS_MARKER = "ARENA_TEST_RESULTS="


@dataclass
class ExecutionResult:
    passed: bool
    stdout: str
    stderr: str
    elapsed_seconds: float
    backend: str
    failure_kind: str | None = None
    passed_tests: int = 0
    total_tests: int = 0
    earned_points: int = 0
    total_points: int = 0

    @property
    def test_score(self) -> int:
        if not self.total_points:
            return 0
        return round(100 * self.earned_points / self.total_points)


def _harness_source(candidate_code: str, test_code: str) -> str:
    return (
        "import time\n"
        f"_start = time.perf_counter()\n"
        f"{candidate_code}\n"
        "solution = two_sum if 'two_sum' in dir() else "
        "(is_valid if 'is_valid' in dir() else "
        "(merge if 'merge' in dir() else "
        "(LRUCache if 'LRUCache' in dir() else None)))\n"
        f"{test_code}\n"
        f"print('{SUCCESS_MARKER}')\n"
    )


def _scored_harness_source(candidate_code: str, tests: tuple[HiddenTest, ...]) -> str:
    test_data = [(test.name, test.code, test.weight) for test in tests]
    return f"""import json
import traceback

candidate_code = {candidate_code!r}
test_cases = {test_data!r}
results = []

for name, test_code, weight in test_cases:
    namespace = {{}}
    try:
        exec(candidate_code, namespace)
        solution = next(
            (namespace.get(entrypoint) for entrypoint in
             ('two_sum', 'is_valid', 'merge', 'LRUCache', 'reconcile_events',
              'plan_rollout', 'apply_config')
             if namespace.get(entrypoint) is not None),
            None,
        )
        if solution is None:
            raise NameError('Required solution entrypoint was not defined')
        namespace['solution'] = solution
        exec(test_code, namespace)
    except BaseException as exc:
        error = ''.join(traceback.format_exception_only(type(exc), exc)).strip()
        results.append({{'name': name, 'passed': False, 'weight': weight, 'error': error}})
    else:
        results.append({{'name': name, 'passed': True, 'weight': weight, 'error': ''}})
    print('{RESULTS_MARKER}' + json.dumps(results), flush=True)

"""


def _normalize_tests(test_spec: str | tuple[HiddenTest, ...]) -> tuple[HiddenTest, ...]:
    if isinstance(test_spec, str):
        return (HiddenTest(name="Complete hidden suite", code=test_spec),)
    return tuple(test_spec)


def run_local(
    candidate_code: str, test_spec: str | tuple[HiddenTest, ...]
) -> ExecutionResult:
    import time

    tests = _normalize_tests(test_spec)
    source = _scored_harness_source(candidate_code, tests)
    total_points = sum(test.weight for test in tests)
    start = time.perf_counter()
    path = None

    def build_result(
        stdout: str,
        stderr: str,
        elapsed: float,
        *,
        timed_out: bool = False,
    ) -> ExecutionResult:
        result_line = next(
            (
                line
                for line in reversed(stdout.splitlines())
                if line.startswith(RESULTS_MARKER)
            ),
            "",
        )
        try:
            case_results = (
                json.loads(result_line.removeprefix(RESULTS_MARKER))
                if result_line
                else []
            )
        except json.JSONDecodeError:
            case_results = []
        passed_tests = sum(1 for result in case_results if result["passed"])
        earned_points = sum(
            result["weight"] for result in case_results if result["passed"]
        )
        passed = (
            not timed_out
            and bool(case_results)
            and len(case_results) == len(tests)
            and passed_tests == len(tests)
        )
        report = [
            f"{'PASS' if result['passed'] else 'FAIL'}: {result['name']}"
            + (f": {result['error']}" if result["error"] else "")
            for result in case_results
        ]
        if timed_out:
            report.append(
                f"TIMEOUT: candidate exceeded {TIMEOUT_SECONDS}s after "
                f"{len(case_results)}/{len(tests)} hidden cases"
            )
        elif passed:
            report.append(SUCCESS_MARKER)
        return ExecutionResult(
            passed=passed,
            stdout="\n".join(report),
            stderr=stderr.strip(),
            elapsed_seconds=elapsed,
            backend="local-subprocess",
            failure_kind=None if passed else "candidate",
            passed_tests=passed_tests,
            total_tests=len(tests),
            earned_points=earned_points,
            total_points=total_points,
        )

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            path = f.name
        proc = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        elapsed = time.perf_counter() - start
        return build_result(
            proc.stdout,
            proc.stderr,
            elapsed,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - start
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return build_result(
            stdout,
            stderr,
            elapsed,
            timed_out=True,
        )
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def run_contree(candidate_code: str, test_code: str) -> ExecutionResult:
    import time

    from contree_sdk import ContreeSync

    source = _harness_source(candidate_code, test_code)
    start = time.perf_counter()
    path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as file:
            file.write(source)
            path = file.name
        client = ContreeSync()
        image = client.images.use("python:3.11-slim")
        result = image.run(
            shell="python /submission.py",
            files={"/submission.py": path},
        ).wait()
        elapsed = time.perf_counter() - start
        passed = result.exit_code == 0 and SUCCESS_MARKER in (result.stdout or "")
        return ExecutionResult(
            passed=passed,
            stdout=(result.stdout or "").strip(),
            stderr=(result.stderr or "").strip(),
            elapsed_seconds=elapsed,
            backend="nebius-sandboxes",
            failure_kind=None if passed else "candidate",
        )
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def run_candidate(
    candidate_code: str, test_spec: str | tuple[HiddenTest, ...]
) -> ExecutionResult:
    """Run hidden tests locally for this demo application."""
    return run_local(candidate_code, test_spec)
