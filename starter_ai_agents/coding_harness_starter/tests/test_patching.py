from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coding_harness.models import FileOperation
from coding_harness.patching import (
    PatchApplyError,
    PatchStateChangedError,
    PatchValidationError,
    apply_prepared_patch,
    prepare_patch,
)
from coding_harness.workspace import MAX_FILE_BYTES, Workspace


class PatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "module.py").write_text("value = 1\n", encoding="utf-8")
        self.workspace = Workspace(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_create_update_and_diff(self) -> None:
        prepared = prepare_patch(
            self.workspace,
            [
                FileOperation(
                    operation="create",
                    path="new.txt",
                    content="new\n",
                    reason="add test",
                ),
                FileOperation(
                    operation="update",
                    path="module.py",
                    expected_old_text="1",
                    content="2",
                    reason="change value",
                ),
            ],
        )
        self.assertIn("--- /dev/null", prepared.diff)
        self.assertIn("+++ b/new.txt", prepared.diff)
        self.assertEqual(apply_prepared_patch(prepared), ["module.py", "new.txt"])
        self.assertEqual(
            (self.root / "module.py").read_text(encoding="utf-8"), "value = 2\n"
        )
        self.assertEqual((self.root / "new.txt").read_text(encoding="utf-8"), "new\n")

    def test_invalid_operation_prevents_any_partial_write(self) -> None:
        with self.assertRaises(PatchValidationError):
            prepare_patch(
                self.workspace,
                [
                    FileOperation(
                        operation="create",
                        path="new.txt",
                        content="new\n",
                        reason="would be valid",
                    ),
                    FileOperation(
                        operation="update",
                        path="module.py",
                        expected_old_text="not here",
                        content="x",
                        reason="invalid",
                    ),
                ],
            )
        self.assertFalse((self.root / "new.txt").exists())
        self.assertEqual(
            (self.root / "module.py").read_text(encoding="utf-8"), "value = 1\n"
        )

    def test_patch_cannot_modify_paths_outside_the_workspace(self) -> None:
        outside = self.root.parent / "outside_patch_target.py"
        for path in ("../outside_patch_target.py", str(outside.resolve())):
            with self.subTest(path=path):
                with self.assertRaises(PatchValidationError):
                    prepare_patch(
                        self.workspace,
                        [
                            FileOperation(
                                operation="create",
                                path=path,
                                content="unsafe = True\n",
                                reason="must remain inside the workspace",
                            )
                        ],
                    )
        self.assertFalse(outside.exists())

    def test_create_requires_an_existing_parent_directory(self) -> None:
        proposal = FileOperation(
            operation="create",
            path="new_tests/test_filtering.py",
            content="import unittest\n",
            reason="add coverage",
        )

        with self.assertRaisesRegex(
            PatchValidationError,
            "cannot create 'new_tests/test_filtering.py': parent directory "
            "'new_tests' does not exist; this patch has not written any files, "
            "and this MVP does not create directories",
        ):
            prepare_patch(self.workspace, [proposal])

        self.assertFalse((self.root / "new_tests").exists())

    def test_update_requires_one_exact_old_text_match(self) -> None:
        (self.root / "module.py").write_text("x x", encoding="utf-8")
        proposal = FileOperation(
            operation="update",
            path="module.py",
            expected_old_text="x",
            content="y",
            reason="ambiguous",
        )
        with self.assertRaisesRegex(PatchValidationError, "exactly once"):
            prepare_patch(self.workspace, [proposal])

    def test_update_rejects_an_oversized_result(self) -> None:
        (self.root / "module.py").write_text(
            "a" * (MAX_FILE_BYTES - 1) + "x", encoding="utf-8"
        )
        proposal = FileOperation(
            operation="update",
            path="module.py",
            expected_old_text="x",
            content="xxx",
            reason="would exceed the workspace limit",
        )
        with self.assertRaisesRegex(PatchValidationError, "exceeds"):
            prepare_patch(self.workspace, [proposal])

    def test_changes_after_preview_are_not_overwritten(self) -> None:
        prepared = prepare_patch(
            self.workspace,
            [
                FileOperation(
                    operation="update",
                    path="module.py",
                    expected_old_text="1",
                    content="2",
                    reason="change",
                )
            ],
        )
        (self.root / "module.py").write_text("value = external\n", encoding="utf-8")
        with self.assertRaises(PatchStateChangedError):
            apply_prepared_patch(prepared)

    def test_apply_error_reports_completed_and_uncompleted_operations(self) -> None:
        prepared = prepare_patch(
            self.workspace,
            [
                FileOperation(
                    operation="create", path="a.txt", content="a\n", reason="first"
                ),
                FileOperation(
                    operation="create", path="b.txt", content="b\n", reason="second"
                ),
            ],
        )
        with patch("coding_harness.patching._write_utf8_atomically") as write:
            write.side_effect = [None, OSError("disk full")]
            with self.assertRaises(PatchApplyError) as raised:
                apply_prepared_patch(prepared)
        self.assertEqual(raised.exception.applied_paths, ["a.txt"])
        self.assertEqual(raised.exception.unapplied_paths, ["b.txt"])
        self.assertIn("Applied: a.txt", str(raised.exception))
        self.assertIn("Not applied: b.txt", str(raised.exception))

    @unittest.skipUnless(
        os.name == "nt",
        "case aliases are specific to case-insensitive Windows filesystems",
    )
    def test_windows_case_aliases_are_conflicting_patch_paths(self) -> None:
        operations = [
            FileOperation(
                operation="create", path="Alias.py", content="one\n", reason="first"
            ),
            FileOperation(
                operation="create", path="alias.py", content="two\n", reason="second"
            ),
        ]
        with self.assertRaisesRegex(PatchValidationError, "duplicate or conflicting"):
            prepare_patch(self.workspace, operations)


if __name__ == "__main__":
    unittest.main()
