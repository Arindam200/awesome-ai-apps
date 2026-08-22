# Todo fixture workspace

This directory is the workspace root when you run `python main.py` without
`--workspace`. Paths in a coding-agent proposal are therefore relative to this
directory:

- `todo.py` is the implementation file.
- `tests/test_todo.py` is the existing unittest file.
- A new filtering test belongs in the existing `tests/` directory, for example
  `tests/test_filtering.py`.

Do not prefix paths with `fixture_repo/`, and do not propose a new directory:
the harness permits file creation only when the target's parent directory
already exists. The starting fixture deliberately has no status-filtering
implementation; the example task is meant to add it.

Before running the harness, this fixture is intentionally complete only for
its original behaviour: `list_todos(items)` returns every item in input order.
Verify that clean baseline from this directory with the same fixed command the
harness will later use:

```bash
python -m unittest discover -s tests -v
```

The recommended task should add an optional status filter supporting `all`,
`completed`, and `pending`, reject an invalid value deterministically, and add
new tests without changing these original tests.
