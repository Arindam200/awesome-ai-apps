"""Tests for the fixture's existing, intentionally minimal behavior."""

import unittest

from todo import Todo, list_todos


class ListTodosTests(unittest.TestCase):
    def test_returns_every_todo_in_input_order(self) -> None:
        todos = [
            Todo("Write the starter", completed=True),
            Todo("Review the patch"),
            Todo("Run the tests"),
        ]

        self.assertEqual(list_todos(todos), todos)

    def test_returns_an_empty_list_for_no_todos(self) -> None:
        self.assertEqual(list_todos([]), [])


if __name__ == "__main__":
    unittest.main()
