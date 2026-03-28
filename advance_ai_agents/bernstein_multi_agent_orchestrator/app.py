"""Minimal TODO API — intentionally missing validation, error handling, and tests.

This is the "before" state. Run Bernstein to spawn parallel AI agents
that add input validation, proper error handling, and full test coverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from flask import Flask, jsonify, request

app = Flask(__name__)


@dataclass
class TodoStore:
    """In-memory store for TODO items."""

    items: dict[int, dict[str, object]] = field(default_factory=dict)
    next_id: int = 1


store = TodoStore()


@app.get("/todos")
def list_todos():
    return jsonify(list(store.items.values()))


@app.post("/todos")
def create_todo():
    data = request.get_json()
    todo = {"id": store.next_id, "title": data["title"], "done": False}
    store.items[store.next_id] = todo
    store.next_id += 1
    return jsonify(todo), 201


@app.patch("/todos/<int:todo_id>")
def update_todo(todo_id: int):
    todo = store.items[todo_id]
    data = request.get_json()
    todo.update(data)
    return jsonify(todo)


@app.delete("/todos/<int:todo_id>")
def delete_todo(todo_id: int):
    del store.items[todo_id]
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)