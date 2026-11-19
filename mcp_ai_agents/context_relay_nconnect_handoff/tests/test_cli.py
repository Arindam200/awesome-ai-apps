"""Regression checks for error reporting, deadlines and configuration validation."""

import asyncio
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from mcp.shared.exceptions import McpError
from mcp.types import ErrorData

from context_relay_nconnect_handoff import cli

if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup, ExceptionGroup


class ErrorReportingTest(unittest.TestCase):
    def run_failure(self, error):
        """Exercise the public CLI boundary without launching a service."""
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(cli, "_demo", side_effect=error),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = cli.main(["demo", "--data-dir", directory])
        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertNotIn("Traceback", stderr.getvalue())
        self.assertNotIn("ExceptionGroup", stderr.getvalue())
        return stderr.getvalue()

    def test_mcp_error_is_reported_directly_and_in_nested_groups(self):
        """Report the underlying MCP message at either exception-group depth."""
        error = McpError(ErrorData(code=-32602, message="Unknown handoff"))
        for wrapped in [error, ExceptionGroup("transport", [ExceptionGroup("session", [error])])]:
            with self.subTest(grouped=wrapped is not error):
                self.assertEqual(
                    self.run_failure(wrapped), "relay-nconnect-demo: Unknown handoff\n"
                )

    def test_all_expected_leaves_are_reported_without_duplicates(self):
        """Keep distinct causes without printing repeated transport wrappers."""
        error = ExceptionGroup(
            "transport", [ValueError("bad ID"), RuntimeError("closed"), ValueError("bad ID")]
        )
        self.assertEqual(
            self.run_failure(error), "relay-nconnect-demo: bad ID\nrelay-nconnect-demo: closed\n"
        )

    def test_unexpected_errors_and_mixed_groups_propagate_intact(self):
        """Do not turn programming errors into expected CLI failures."""
        unexpected = AssertionError("programming error")
        for error in [unexpected, ExceptionGroup("mixed", [ValueError("bad ID"), unexpected])]:
            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)) as caught:
                self.run_failure(error)
            self.assertIs(caught.exception, error)

    def test_interrupts_and_cancellation_are_not_converted_to_cli_failures(self):
        """Preserve process control exceptions, including mixed base groups."""
        for leaf in [KeyboardInterrupt(), SystemExit(2), asyncio.CancelledError()]:
            for error in [leaf, BaseExceptionGroup("cancelled", [ValueError("bad ID"), leaf])]:
                with (
                    self.subTest(error=type(error).__name__),
                    self.assertRaises(type(error)) as caught,
                ):
                    self.run_failure(error)
                self.assertIs(caught.exception, error)

    def test_relay_subprocess_deadline_stops_a_stalled_process(self):
        """Exercise a real child that never finishes within the deadline."""
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(cli, "PROCESS_TIMEOUT_SECONDS", 0.1),
            self.assertRaises(subprocess.TimeoutExpired),
        ):
            cli._run_relay(sys.executable, ["-c", "import time; time.sleep(60)"], Path(directory))

    def test_mcp_deadline_reports_a_stalled_server(self):
        """Bound initialization against a child that never speaks MCP."""
        stderr = io.StringIO()
        with (
            patch.object(cli, "MCP_TIMEOUT", timedelta(seconds=0.1)),
            patch.object(cli, "_relay_args", return_value=["-c", "import time; time.sleep(60)"]),
            contextlib.redirect_stderr(stderr),
        ):
            code = cli.main(
                [
                    "--relay-bin",
                    sys.executable,
                    "inspect",
                    "--project-id",
                    "project",
                    "--handoff-id",
                    "handoff",
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn("relay-nconnect-demo:", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


class TemporaryProfileTest(unittest.TestCase):
    def setUp(self):
        """Keep fake service files in an owned directory; never start Relay."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = directory.name

    def run_demo(self, error=None, stop_error=None):
        """Exercise the default CLI path with real files and controlled failures."""
        self.stdout, self.stderr = io.StringIO(), io.StringIO()

        def demo(relay_bin, data_dir):
            self.profile = data_dir
            (data_dir / "service.lock").write_text("fake service")
            (data_dir / "relay.db").write_text("recoverable data")
            if error is not None:
                raise error
            return {"status": "accepted"}

        def stop(relay_bin, data_dir):
            self.assertEqual((data_dir / "relay.db").read_text(), "recoverable data")
            if stop_error is not None:
                raise stop_error
            (data_dir / "service.lock").unlink()

        with (
            patch.object(cli.tempfile, "tempdir", self.directory),
            patch.object(cli, "_demo", side_effect=demo),
            patch.object(cli, "_stop_relay", side_effect=stop),
            contextlib.redirect_stdout(self.stdout),
            contextlib.redirect_stderr(self.stderr),
        ):
            return cli.main(["demo"])

    def assert_retained_profile(self):
        """A failed stop must leave both the lock and database available."""
        self.assertEqual((self.profile / "service.lock").read_text(), "fake service")
        self.assertEqual((self.profile / "relay.db").read_text(), "recoverable data")
        self.assertIn(str(self.profile), self.stderr.getvalue())
        self.assertEqual(self.stdout.getvalue(), "")

    def test_success_stops_service_before_removing_profile(self):
        """Successful shutdown permits removal and normal JSON output."""
        self.assertEqual(self.run_demo(), 0)
        self.assertFalse(self.profile.exists())
        self.assertEqual(json.loads(self.stdout.getvalue()), {"status": "accepted"})
        self.assertEqual(self.stderr.getvalue(), "")

    def test_demo_failure_still_removes_profile_after_successful_stop(self):
        """Cleanup must also work on an exceptional exit from the demo."""
        error = AssertionError("demo failed")
        with self.assertRaises(AssertionError) as caught:
            self.run_demo(error=error)
        self.assertIs(caught.exception, error)
        self.assertFalse(self.profile.exists())

    def test_failed_stop_retains_profile_and_reports_recovery_path(self):
        """A shutdown error or timeout must not delete a running service's files."""
        for error in [RuntimeError("stop failed"), subprocess.TimeoutExpired("relay stop", 60)]:
            with self.subTest(error=type(error).__name__):
                self.assertEqual(self.run_demo(stop_error=error), 1)
                self.assert_retained_profile()
                self.assertIn(str(error), self.stderr.getvalue())

    def test_failed_stop_preserves_unexpected_errors_and_process_control(self):
        """The cleanup failure must not replace the original exception."""
        for error in [AssertionError("demo failed"), KeyboardInterrupt(), asyncio.CancelledError()]:
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)) as caught:
                    self.run_demo(error=error, stop_error=RuntimeError("stop failed"))
                self.assertIs(caught.exception, error)
                self.assert_retained_profile()
                self.assertIn("stop failed", self.stderr.getvalue())

    def test_both_expected_failures_are_reported(self):
        """Keep the primary CLI diagnostic as well as the cleanup diagnostic."""
        self.assertEqual(
            self.run_demo(error=ValueError("bad handoff"), stop_error=RuntimeError("stop failed")),
            1,
        )
        self.assert_retained_profile()
        self.assertIn("bad handoff", self.stderr.getvalue())
        self.assertIn("stop failed", self.stderr.getvalue())

    def test_directory_removal_failure_preserves_the_demo_error(self):
        """A filesystem cleanup failure must not hide the original error either."""
        error = AssertionError("demo failed")
        with (
            patch.object(cli.shutil, "rmtree", side_effect=PermissionError("file busy")),
            self.assertRaises(AssertionError) as caught,
        ):
            self.run_demo(error=error)
        self.assertIs(caught.exception, error)
        self.assertFalse((self.profile / "service.lock").exists())
        self.assertEqual((self.profile / "relay.db").read_text(), "recoverable data")
        self.assertIn(str(self.profile), self.stderr.getvalue())
        self.assertIn("file busy", self.stderr.getvalue())

    def test_interrupt_during_shutdown_still_propagates(self):
        """Without an earlier error, a cleanup interrupt must reach the caller."""
        error = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.run_demo(stop_error=error)
        self.assertIs(caught.exception, error)
        self.assert_retained_profile()


class NConnectConfigurationTest(unittest.TestCase):
    def server(self, **overrides):
        """Match the JSON schema emitted by Codex's mcp list command."""
        return {
            "name": "context_relay",
            "enabled": True,
            "transport": {
                "type": "stdio",
                "command": "node",
                "args": [
                    "/relay/dist/cli.js",
                    "mcp",
                    "--project",
                    "expected",
                    "--harness",
                    "codex",
                ],
            },
            **overrides,
        }

    def check(self, servers):
        """Supply configuration JSON without invoking NConnect or a model."""
        with patch.object(
            cli.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, json.dumps(servers), ""),
        ) as run:
            result = cli.check_nconnect("test-model", "nconnect", "expected")
        self.assertEqual(run.call_args.args[0][-4:], ["codex", "mcp", "list", "--json"])
        self.assertEqual(run.call_args.kwargs["env"]["NCONNECT_DISABLE_AUTOUPDATE"], "1")
        return result

    def test_enabled_entry_with_matching_project_and_harness_passes(self):
        """Return configuration evidence without claiming a model request."""
        result = self.check([self.server()])
        self.assertEqual(result["projectId"], "expected")
        self.assertTrue(result["configurationOnly"])
        self.assertFalse(result["modelRequestSent"])

    def test_equals_syntax_passes(self):
        """Accept the alternate CLI spelling for project and harness flags."""
        server = self.server()
        server["transport"]["args"] = ["mcp", "--project=expected", "--harness=codex"]
        self.assertEqual(self.check([server])["status"], "enabled")

    def test_missing_disabled_duplicate_or_malformed_servers_fail(self):
        """Reject entries that cannot identify one enabled Relay server."""
        for servers in [
            [],
            {},
            [None],
            [self.server(enabled=False)],
            [self.server(enabled="true")],
            [self.server(name="context_relay_other")],
            [self.server(), self.server()],
            [self.server(transport="invalid")],
        ]:
            with (
                self.subTest(servers=servers),
                self.assertRaises((RuntimeError, ValueError, TypeError)),
            ):
                self.check(servers)

    def test_other_project_harness_or_ambiguous_arguments_fail(self):
        """Reject wrong bindings and conflicting or incomplete flags."""
        for args in [
            ["mcp", "--project", "other", "--harness", "codex"],
            ["mcp", "--project", "expected", "--harness", "claude"],
            ["mcp", "--project", "expected", "--harness", "codex", "--project", "other"],
            ["mcp", "--project"],
            ["mcp", 1],
            None,
        ]:
            server = self.server()
            server["transport"]["args"] = args
            with self.subTest(args=args), self.assertRaises(RuntimeError):
                self.check([server])

    def test_http_entry_does_not_pass_as_a_project_bound_stdio_server(self):
        """Require the configured transport used by this example."""
        with self.assertRaises(RuntimeError):
            self.check(
                [self.server(transport={"type": "streamable_http", "url": "http://localhost"})]
            )


if __name__ == "__main__":
    unittest.main()
