from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from coding_harness.testing import (
    DEFAULT_OUTPUT_LIMIT,
    TEST_ARGUMENTS,
    TestResult,
    run_tests,
)


class TestFixedRunner(unittest.TestCase):
    def test_uses_fixed_argv_locked_cwd_and_no_shell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.CompletedProcess(TEST_ARGUMENTS, 0, "ok", "")
            with patch(
                "coding_harness.testing.subprocess.run", return_value=completed
            ) as run:
                result = run_tests(Path(directory))

            self.assertTrue(result.passed)
            args, kwargs = run.call_args
            self.assertEqual(args[0], list(TEST_ARGUMENTS))
            self.assertEqual(kwargs["cwd"], str(Path(directory).resolve()))
            self.assertFalse(kwargs["shell"])

    def test_timeout_is_reported_with_bounded_output(self) -> None:
        error = subprocess.TimeoutExpired(
            list(TEST_ARGUMENTS), 30, output=b"a" * 100, stderr=b"b" * 100
        )
        with tempfile.TemporaryDirectory() as directory:
            with patch("coding_harness.testing.subprocess.run", side_effect=error):
                result = run_tests(directory, output_limit=50)

        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)
        self.assertLessEqual(len(result.stdout), 50)
        self.assertLessEqual(len(result.stderr), 50)

    def test_nonzero_exit_is_not_success(self) -> None:
        completed = subprocess.CompletedProcess(TEST_ARGUMENTS, 2, "", "failure")
        with tempfile.TemporaryDirectory() as directory:
            with patch("coding_harness.testing.subprocess.run", return_value=completed):
                result = run_tests(directory)
        self.assertFalse(result.passed)
        self.assertEqual(result.exit_code, 2)

    def test_error_summary_keeps_the_tail_of_a_long_failure_log(self) -> None:
        result = TestResult(
            TEST_ARGUMENTS,
            1,
            "setup output\n",
            "x" * 2_000 + "\nAssertionError: expected value\n",
        )

        summary = result.error_summary(limit=80)

        self.assertLessEqual(len(summary), 80)
        self.assertTrue(summary.startswith("... [output truncated]"))
        self.assertIn("AssertionError: expected value", summary)

    def test_output_limits_remain_bounded_for_small_and_oversized_requests(
        self,
    ) -> None:
        result = TestResult(TEST_ARGUMENTS, 1, "", "important failure")
        self.assertEqual(result.error_summary(limit=5), "ilure")

        completed = subprocess.CompletedProcess(
            TEST_ARGUMENTS, 1, "x" * (DEFAULT_OUTPUT_LIMIT + 100), ""
        )
        with tempfile.TemporaryDirectory() as directory:
            with patch("coding_harness.testing.subprocess.run", return_value=completed):
                bounded = run_tests(directory, output_limit=DEFAULT_OUTPUT_LIMIT * 2)
        self.assertLessEqual(len(bounded.stdout), DEFAULT_OUTPUT_LIMIT)


if __name__ == "__main__":
    unittest.main()
