"""Exercise the published Context Relay CLI and its stdio MCP transport."""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from context_relay_nconnect_handoff.cli import _run_relay, _stop_relay, probe_handoff

RELAY_BIN = shutil.which(os.environ.get("CONTEXT_RELAY_BIN", "relay"))


@unittest.skipUnless(RELAY_BIN, "install @mahekara28/context-relay@0.3.0-beta.1")
class HandoffTransportTest(unittest.TestCase):
    def setUp(self):
        """Own an isolated profile and close its service before deleting SQLite files."""
        directory = tempfile.TemporaryDirectory(prefix="relay-nconnect-test-")
        self.addCleanup(directory.cleanup)
        self.data_dir = Path(directory.name)
        self.addCleanup(_stop_relay, RELAY_BIN, self.data_dir)
        self.fixture = _run_relay(RELAY_BIN, ["demo"], self.data_dir)

    def stored_status(self):
        """Read persisted state independently of the MCP probe's summary."""
        return _run_relay(
            RELAY_BIN, ["handoff", "show", "--id", self.fixture["handoffId"]], self.data_dir
        )["status"]

    def test_synthetic_handoff_is_inspected_and_acknowledged_over_mcp(self):
        """Check both the MCP response and independently persisted acceptance."""
        summary = asyncio.run(
            probe_handoff(
                self.fixture["projectId"],
                self.fixture["handoffId"],
                relay_bin=RELAY_BIN,
                data_dir=self.data_dir,
                accept_synthetic=True,
            )
        )
        self.assertTrue(summary["synthetic"])
        self.assertEqual(summary["status"], "accepted")
        self.assertEqual(summary["packetVersion"], "relay.packet/v1")
        self.assertEqual(summary["goal"], "Prevent duplicate webhook charges.")
        self.assertIn("relay_handoff_accept", summary["mcpToolsVerified"])
        self.assertEqual(self.stored_status(), "accepted")

    def test_read_only_probe_leaves_synthetic_handoff_offered(self):
        """Ensure inspection cannot acknowledge a real user's handoff."""
        summary = asyncio.run(
            probe_handoff(
                self.fixture["projectId"],
                self.fixture["handoffId"],
                relay_bin=RELAY_BIN,
                data_dir=self.data_dir,
            )
        )
        self.assertEqual(summary["status"], "offered")
        self.assertEqual(self.stored_status(), "offered")

    def test_invalid_project_handoff_and_cross_project_ids_fail_without_tracebacks(self):
        """Exercise invalid IDs through the CLI and the published MCP server."""
        other_root = self.data_dir / "other-project"
        other_root.mkdir()
        other_project = _run_relay(
            RELAY_BIN, ["project", "add", "--root", str(other_root)], self.data_dir
        )
        for project_id, handoff_id in [
            ("missing-project", self.fixture["handoffId"]),
            (self.fixture["projectId"], "missing-handoff"),
            (other_project["id"], self.fixture["handoffId"]),
        ]:
            with self.subTest(project_id=project_id, handoff_id=handoff_id):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "context_relay_nconnect_handoff.cli",
                        "--relay-bin",
                        RELAY_BIN,
                        "inspect",
                        "--project-id",
                        project_id,
                        "--handoff-id",
                        handoff_id,
                        "--data-dir",
                        str(self.data_dir),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("relay-nconnect-demo:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertNotIn("ExceptionGroup", result.stderr)
                self.assertEqual(self.stored_status(), "offered")

    def test_default_demo_stops_its_service_and_removes_the_temporary_profile(self):
        """Catch leaked services and open SQLite files in the default demo."""
        scratch = self.data_dir / "temporary-profiles"
        scratch.mkdir()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "context_relay_nconnect_handoff.cli",
                "--relay-bin",
                RELAY_BIN,
                "demo",
            ],
            env={**os.environ, "TMPDIR": str(scratch), "TEMP": str(scratch), "TMP": str(scratch)},
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "accepted")
        self.assertEqual(list(scratch.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
