from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coding_harness.workspace import (
    MAX_FILE_BYTES,
    MAX_TOOL_OUTPUT_CHARS,
    Workspace,
    WorkspaceError,
)


class WorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "sample.py").write_text("answer = 42\n", encoding="utf-8")
        self.workspace = Workspace(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_reads_allowed_relative_utf8_text(self) -> None:
        self.assertEqual(self.workspace.read_file("sample.py"), "answer = 42\n")
        self.assertEqual(self.workspace.list_files(), ["sample.py"])

    def test_rejects_absolute_and_parent_escape(self) -> None:
        with self.assertRaises(WorkspaceError):
            self.workspace.read_file(self.root / "sample.py")
        with self.assertRaises(WorkspaceError):
            self.workspace.read_file("../sample.py")

    def test_paths_with_nul_are_rejected(self) -> None:
        with self.assertRaisesRegex(WorkspaceError, "NUL"):
            self.workspace.read_file("sample.py\x00.txt")

    def test_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as outside_directory:
            outside = Path(outside_directory) / "outside.py"
            outside.write_text("secret = True\n", encoding="utf-8")
            link = self.root / "linked.py"
            try:
                link.symlink_to(outside)
            except OSError as error:
                self.skipTest(f"symbolic links are unavailable: {error}")
            with self.assertRaises(WorkspaceError):
                self.workspace.read_file("linked.py")

    def test_rejects_a_detected_symlink_without_os_link_privileges(self) -> None:
        original_is_symlink = Path.is_symlink

        def detected_for_link(path: Path) -> bool:
            return path.name == "linked.py" or original_is_symlink(path)

        with patch.object(Path, "is_symlink", detected_for_link):
            with self.assertRaisesRegex(WorkspaceError, "symbolic links"):
                self.workspace.read_file("linked.py")

    def test_rejects_sensitive_binary_and_oversized_files(self) -> None:
        (self.root / ".env").write_text(
            "MODEL_API_KEY=not-for-agent\n", encoding="utf-8"
        )
        (self.root / "binary.py").write_bytes(b"x\x00y")
        (self.root / "large.py").write_text(
            "x" * (MAX_FILE_BYTES + 1), encoding="utf-8"
        )
        for name in (".env", "binary.py", "large.py"):
            with self.subTest(name=name):
                with self.assertRaises(WorkspaceError):
                    self.workspace.read_file(name)

    def test_ignored_directory_policy_cannot_be_bypassed_by_case(self) -> None:
        ignored = self.root / ".GIT"
        ignored.mkdir()
        (ignored / "visible.py").write_text("answer = 42\n", encoding="utf-8")
        self.assertNotIn(".GIT/visible.py", self.workspace.list_files())
        with self.assertRaisesRegex(WorkspaceError, "ignored directory"):
            self.workspace.read_file(".GIT/visible.py")

    def test_search_is_bounded_and_reports_paths_and_lines(self) -> None:
        (self.root / "second.txt").write_text("first\nneedle here\n", encoding="utf-8")
        results = self.workspace.search_text("needle")
        self.assertEqual(
            results, [{"path": "second.txt", "line": 2, "text": "needle here"}]
        )

    def test_search_output_is_bounded(self) -> None:
        (self.root / "second.txt").write_text(
            "needle " + "x" * (MAX_TOOL_OUTPUT_CHARS + 100), encoding="utf-8"
        )
        results = self.workspace.search_text("needle")
        self.assertLessEqual(
            sum(len(result["text"]) for result in results), MAX_TOOL_OUTPUT_CHARS
        )

    def test_search_finds_matches_after_read_display_limit(self) -> None:
        (self.root / "late.txt").write_text(
            "x" * (MAX_TOOL_OUTPUT_CHARS + 1) + "needle", encoding="utf-8"
        )
        self.assertEqual(
            self.workspace.search_text("needle"),
            [
                {
                    "path": "late.txt",
                    "line": 1,
                    "text": "x" * (MAX_TOOL_OUTPUT_CHARS - len("needle")) + "needle",
                }
            ],
        )

    def test_file_listing_is_bounded(self) -> None:
        for index in range(200):
            name = f"{index:03d}_{'x' * 70}.txt"
            (self.root / name).write_text("needle\n", encoding="utf-8")

        listed = self.workspace.list_files()
        self.assertLessEqual(sum(len(path) for path in listed), MAX_TOOL_OUTPUT_CHARS)

    def test_file_listing_stops_traversal_at_the_file_limit(self) -> None:
        def walk_until_resumed(*_: object, **__: object):
            yield str(self.root), ["later"], ["sample.py"]
            self.fail("list_files traversed after reaching its file limit")

        with (
            patch(
                "coding_harness.workspace.os.walk", return_value=walk_until_resumed()
            ),
            patch("coding_harness.workspace.MAX_LISTED_FILES", 1),
        ):
            self.assertEqual(self.workspace.list_files(), ["sample.py"])


if __name__ == "__main__":
    unittest.main()
