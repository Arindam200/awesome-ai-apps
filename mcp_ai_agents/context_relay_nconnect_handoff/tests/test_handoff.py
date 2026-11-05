"""Exercise the published Context Relay CLI and its stdio MCP transport."""

import asyncio
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from context_relay_nconnect_handoff.cli import _run_relay, probe_handoff


@unittest.skipUnless(shutil.which("relay"), "install @mahekara28/context-relay@0.3.0-beta.1")
class HandoffTransportTest(unittest.TestCase):
    def test_synthetic_handoff_is_inspected_and_acknowledged_over_mcp(self):
        with tempfile.TemporaryDirectory(prefix="relay-nconnect-test-") as directory:
            data_dir = Path(directory)
            fixture = _run_relay("relay", ["demo"], data_dir)
            summary = asyncio.run(
                probe_handoff(
                    fixture["projectId"],
                    fixture["handoffId"],
                    data_dir=data_dir,
                    accept_synthetic=True,
                )
            )

            self.assertTrue(summary["synthetic"])
            self.assertEqual(summary["status"], "accepted")
            self.assertEqual(summary["packetVersion"], "relay.packet/v1")
            self.assertEqual(summary["goal"], "Prevent duplicate webhook charges.")
            self.assertIn("relay_handoff_accept", summary["mcpToolsVerified"])

    def test_read_only_probe_leaves_synthetic_handoff_offered(self):
        with tempfile.TemporaryDirectory(prefix="relay-nconnect-test-") as directory:
            data_dir = Path(directory)
            fixture = _run_relay("relay", ["demo"], data_dir)
            summary = asyncio.run(
                probe_handoff(fixture["projectId"], fixture["handoffId"], data_dir=data_dir)
            )
            shown = subprocess.run(
                ["relay", "handoff", "show", "--id", fixture["handoffId"], "--data-dir", directory],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual(summary["status"], "offered")
            self.assertEqual(json.loads(shown.stdout)["status"], "offered")


if __name__ == "__main__":
    unittest.main()
