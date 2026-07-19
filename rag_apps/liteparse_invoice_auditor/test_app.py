"""Regression tests for the invoice auditor."""

import ast
import unittest
from pathlib import Path


APP_PATH = Path(__file__).with_name("app.py")


def load_string_constant(name: str) -> str:
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} was not found in {APP_PATH}")


class AuditPromptTests(unittest.TestCase):
    def test_json_schema_braces_are_not_treated_as_format_fields(self) -> None:
        prompt = load_string_constant("AUDIT_PROMPT")

        rendered = prompt.format(
            filename="arindam-resume.pdf",
            document="Example resume text",
        )

        self.assertIn('"doc_type"', rendered)
        self.assertIn("arindam-resume.pdf", rendered)
        self.assertIn("Example resume text", rendered)
        self.assertNotIn("{filename}", rendered)
        self.assertNotIn("{document}", rendered)


if __name__ == "__main__":
    unittest.main()
