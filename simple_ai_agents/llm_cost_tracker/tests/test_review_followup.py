"""Regression checks for dashboard data selection and isolated startup errors."""

import shutil
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

import main
import tracker

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def example(tmp_path, monkeypatch):
    """Keep all configuration and records in a temporary example directory."""
    monkeypatch.setattr(tracker, "PROJECT_DIR", tmp_path)
    shutil.copyfile(PROJECT / "pricing.example.json", tmp_path / "pricing.example.json")
    monkeypatch.setenv("LLM_MODEL", "fixture-model")
    monkeypatch.setenv("LLM_API_KEY", "offline-test-key")
    monkeypatch.setenv("LLM_PROVIDER", "demo")
    monkeypatch.setenv("LLM_PRICING_FILE", "pricing.example.json")
    monkeypatch.setenv("LLM_COST_DB", ".data/usage.sqlite3")
    return tmp_path


def fail_expansion(monkeypatch):
    """Model pathlib's documented failure for an unresolvable user home on either OS."""
    original = Path.expanduser

    def expand(path):
        if path.as_posix() == "~unresolvable_user/records":
            raise RuntimeError("Could not determine home directory")
        return original(path)

    monkeypatch.setattr(Path, "expanduser", expand)


def test_demo_ignores_unresolvable_live_pricing(example, monkeypatch):
    """An unrelated live pricing setting must not stop the offline demo."""
    fail_expansion(monkeypatch)
    monkeypatch.setenv("LLM_PRICING_FILE", "~unresolvable_user/records")
    monkeypatch.setattr(sys, "argv", ["main.py", "--demo"])
    assert main.main() == 0
    assert len(tracker.load_rows(example / ".data/demo.sqlite3")) == 3


@pytest.mark.parametrize("demo", [True, False])
def test_cli_explains_unresolvable_database_path(example, monkeypatch, capsys, demo):
    """Both CLI modes explain path-expansion failures without a traceback."""
    fail_expansion(monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "--database", "~unresolvable_user/records", *(["--demo"] if demo else [])],
    )
    assert main.main() == 1
    assert "Database path" in capsys.readouterr().out


def test_database_file_error_is_not_reported_as_missing_pricing(example, monkeypatch, capsys):
    """A FileNotFoundError from database setup must not be blamed on a valid pricing file."""
    client = MagicMock()
    client.__enter__.return_value = client
    monkeypatch.setattr(main, "OpenAI", lambda **_: client)
    monkeypatch.setattr(
        sqlite3, "connect", MagicMock(side_effect=FileNotFoundError("private-path"))
    )
    monkeypatch.setattr(sys, "argv", ["main.py"])
    assert main.main() == 1
    output = capsys.readouterr().out
    assert "Database initialization failed" in output
    assert "Pricing file not found" not in output and "private-path" not in output
    client.chat.completions.create.assert_not_called()


def seed(path, example, count=1):
    """Create known request records using the actual tracker and local SQLite."""
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=200)
    )
    instance = tracker.CostTracker(client, path, "demo", example / "pricing.example.json")
    for _ in range(count):
        instance.create(model="fixture-model")


def test_dashboard_does_not_accept_viewer_supplied_database_paths(example):
    """Viewers may inspect the configured database without browsing the server filesystem."""
    seed(example / ".data/usage.sqlite3", example)
    app = AppTest.from_file(str(PROJECT / "dashboard.py"), default_timeout=15).run()
    assert not app.exception
    assert {metric.label: metric.value for metric in app.metric}["Requests"] == "1"
    assert not app.text_input


def test_dashboard_requires_explicit_live_or_demo_selection(example, monkeypatch):
    """Without operator configuration, never silently substitute demo rows for live usage."""
    seed(example / ".data/usage.sqlite3", example)
    seed(example / ".data/demo.sqlite3", example, count=2)
    monkeypatch.delenv("LLM_COST_DB")
    app = AppTest.from_file(str(PROJECT / "dashboard.py"), default_timeout=15).run()
    assert not app.exception
    assert not app.metric and not app.text_input
    app.selectbox[0].select("Live requests").run()
    assert not app.exception
    assert {metric.label: metric.value for metric in app.metric}["Requests"] == "1"
    app.selectbox[0].select("Offline demo").run()
    assert {metric.label: metric.value for metric in app.metric}["Requests"] == "2"


def test_dashboard_explains_operator_path_expansion_errors(example, monkeypatch):
    """An invalid operator setting produces guidance rather than a Streamlit exception."""
    fail_expansion(monkeypatch)
    monkeypatch.setenv("LLM_COST_DB", "~unresolvable_user/records")
    app = AppTest.from_file(str(PROJECT / "dashboard.py"), default_timeout=15).run()
    assert not app.exception
    assert "No readable request database" in app.info[0].value


def test_configured_live_database_does_not_hide_the_demo(example):
    """A configured live file remains separate while viewers can choose the fixed demo."""
    seed(example / ".data/usage.sqlite3", example)
    seed(example / ".data/demo.sqlite3", example, count=2)
    app = AppTest.from_file(str(PROJECT / "dashboard.py"), default_timeout=15).run()
    assert not app.exception
    assert {metric.label: metric.value for metric in app.metric}["Requests"] == "1"
    source = next(widget for widget in app.selectbox if widget.label == "Request source")
    source.select("Offline demo").run()
    assert not app.exception
    assert {metric.label: metric.value for metric in app.metric}["Requests"] == "2"
    assert not app.text_input


@pytest.mark.parametrize("problem", ["directory", "invalid-json", "invalid-rates", "unreadable"])
def test_live_pricing_failures_are_identified_before_any_request(
    example, monkeypatch, capsys, problem
):
    """Invalid/unreadable pricing never becomes a database error or a provider call."""
    pricing = example / "bad-pricing.json"
    if problem == "directory":
        pricing.mkdir()
    else:
        pricing.write_text(
            "{" if problem == "invalid-json" else '{"demo":{"m":{}}}', encoding="utf-8"
        )
    if problem == "unreadable":
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path == pricing:
                raise PermissionError("private-pricing-detail")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setenv("LLM_PRICING_FILE", str(pricing))
    monkeypatch.setattr(sys, "argv", ["main.py"])
    client = MagicMock()
    client.__enter__.return_value = client
    monkeypatch.setattr(main, "OpenAI", lambda **_: client)
    assert main.main() == 1
    output = capsys.readouterr().out
    assert "Pricing configuration" in output
    assert "Database initialization failed" not in output
    assert "private-pricing-detail" not in output
    client.chat.completions.create.assert_not_called()
