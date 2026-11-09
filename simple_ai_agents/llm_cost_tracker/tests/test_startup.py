"""Exercise CLI and dashboard configuration independently of the working directory."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from openai import OpenAI
from streamlit.testing.v1 import AppTest

import main
import tracker
from tracker import load_rows

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def example(tmp_path):
    """Copy runnable files without local credentials, databases or dependencies."""
    project = tmp_path / "example"
    project.mkdir()
    for name in ["main.py", "tracker.py", "dashboard.py", "pricing.example.json"]:
        shutil.copyfile(PROJECT / name, project / name)
    return project


@pytest.mark.parametrize("working_directory", ["project", "parent", "unrelated"])
def test_demo_uses_project_files_from_any_directory(example, tmp_path, working_directory):
    """Find bundled rates and keep the demo database in the same project directory."""
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    cwd = {"project": example, "parent": tmp_path, "unrelated": unrelated}[working_directory]
    environment = {key: value for key, value in os.environ.items() if not key.startswith("LLM_")}
    environment["LLM_PRICING_FILE"] = "missing-live-prices.json"
    environment["LLM_COST_DB"] = "live.sqlite3"
    result = subprocess.run(
        [sys.executable, str(example / "main.py"), "--demo"],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(load_rows(example / ".data/demo.sqlite3")) == 3
    assert not (example / "live.sqlite3").exists()
    if cwd != example:
        assert not (cwd / ".data").exists()


def test_live_missing_prices_explains_setup_before_request(monkeypatch, tmp_path, capsys):
    """Explain a missing live pricing file without sending a request or exposing secrets."""
    monkeypatch.setenv("LLM_API_KEY", "offline-test-key")
    monkeypatch.setenv("LLM_MODEL", "offline-model")
    monkeypatch.setenv("LLM_PRICING_FILE", str(tmp_path / "missing.json"))
    monkeypatch.setenv("LLM_COST_DB", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr(sys, "argv", ["main.py"])
    calls = []

    def respond(request):
        """Capture accidental sends without allowing any external network access."""
        calls.append(request)
        return main.demo_reply(request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        with OpenAI(api_key="offline-test-key", http_client=http) as client:
            monkeypatch.setattr(main, "OpenAI", lambda **_: client)
            assert main.main() == 1
    output = capsys.readouterr().out
    assert "Pricing file not found" in output
    assert "LLM_PRICING_FILE" in output and "pricing.example.json" in output
    assert "offline-test-key" not in output
    assert not (tmp_path / "usage.sqlite3").exists()
    assert not calls


@pytest.mark.parametrize("configuration", ["default", "dotenv", "input"])
def test_dashboard_relative_path_uses_project_directory(
    example, tmp_path, monkeypatch, configuration
):
    """Read default, .env and manually entered relative paths from another directory."""
    result = subprocess.run(
        [sys.executable, str(example / "main.py"), "--demo"],
        cwd=example,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    monkeypatch.setattr(tracker, "PROJECT_DIR", example, raising=False)
    # Register cleanup even when load_dotenv creates a previously absent variable.
    monkeypatch.setenv("LLM_COST_DB", "")
    monkeypatch.delenv("LLM_COST_DB", raising=False)
    if configuration == "dotenv":
        (example / ".env").write_text("LLM_COST_DB=.data/demo.sqlite3\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(example / "dashboard.py"), default_timeout=15).run()
    if configuration == "input":
        shutil.copyfile(example / ".data/demo.sqlite3", example / "alternate.sqlite3")
        app.text_input[0].set_value("alternate.sqlite3").run()
    assert not app.exception
    assert {metric.label: metric.value for metric in app.metric}["Requests"] == "3"
    assert not (tmp_path / ".data").exists()


@pytest.mark.parametrize("path_mode", ["defaults", "relative", "absolute", "cli", "unpriced"])
def test_live_cli_uses_project_pricing_and_database(
    example, tmp_path, monkeypatch, capsys, path_mode
):
    """Record actual SDK fixture usage with defaults, environment paths or a CLI override."""
    monkeypatch.setattr(tracker, "PROJECT_DIR", example, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "offline-test-key")
    monkeypatch.setenv("LLM_MODEL", "fixture-model")
    monkeypatch.setenv("LLM_PROVIDER", "test")
    pricing = example / ("pricing.json" if path_mode == "defaults" else "custom.json")
    pricing.write_text(
        json.dumps(
            {}
            if path_mode == "unpriced"
            else {
                "test": {"fixture-model": {"input_per_million_usd": 1, "output_per_million_usd": 2}}
            }
        ),
        encoding="utf-8",
    )
    argv = ["main.py"]
    database = example / ".data/usage.sqlite3"
    for name in ["LLM_PRICING_FILE", "LLM_COST_DB"]:
        monkeypatch.delenv(name, raising=False)
    if path_mode != "defaults":
        absolute = path_mode == "absolute"
        monkeypatch.setenv("LLM_PRICING_FILE", str(pricing if absolute else pricing.name))
        database = example / "custom/usage.sqlite3"
        monkeypatch.setenv("LLM_COST_DB", str(database if absolute else "custom/usage.sqlite3"))
    if path_mode == "cli":
        monkeypatch.setenv("LLM_COST_DB", "ignored.sqlite3")
        argv += ["--database", "custom/usage.sqlite3"]
    monkeypatch.setattr(sys, "argv", argv)
    calls = []

    def respond(request):
        """Serve a synthetic reply through the real SDK's request/response path."""
        calls.append(request)
        return main.demo_reply(request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        with OpenAI(api_key="offline-test-key", http_client=transport) as client:
            monkeypatch.setattr(main, "OpenAI", lambda **_: client)
            assert main.main() == 0
    assert len(calls) == 1
    assert load_rows(database)[0]["estimated_cost_usd"] == (
        None if path_mode == "unpriced" else "0.0014"
    )
    assert not (tmp_path / "custom").exists()
    assert not (example / "ignored.sqlite3").exists()
    assert ("costs will be unknown" in capsys.readouterr().out) == (path_mode == "unpriced")


def test_live_default_never_falls_back_to_demo_prices(example, monkeypatch, capsys):
    """Require real pricing configuration even when the bundled demo rate would match."""
    monkeypatch.setattr(tracker, "PROJECT_DIR", example, raising=False)
    monkeypatch.chdir(example)
    monkeypatch.setenv("LLM_API_KEY", "offline-test-key")
    monkeypatch.setenv("LLM_MODEL", "fixture-model")
    monkeypatch.setenv("LLM_PROVIDER", "demo")
    monkeypatch.delenv("LLM_PRICING_FILE", raising=False)
    monkeypatch.setattr(sys, "argv", ["main.py"])
    calls = []

    def respond(request):
        """Expose an accidental fallback as a successful synthetic completion."""
        calls.append(request)
        return main.demo_reply(request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        with OpenAI(api_key="offline-test-key", http_client=http) as client:
            monkeypatch.setattr(main, "OpenAI", lambda **_: client)
            assert main.main() == 1
    assert "Pricing file not found" in capsys.readouterr().out
    assert not calls
