"""Behavioral tests with the real SDK, SQLite and dashboard, without provider calls."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from openai import OpenAI
from streamlit.testing.v1 import AppTest

import main
from main import demo_reply
from tracker import CostTracker, load_pricing, load_rows


@pytest.fixture
def setup(tmp_path):
    """Create a configured tracker with a deterministic SDK-shaped response."""
    pricing = tmp_path / "prices.json"
    pricing.write_text(
        json.dumps(
            {"test": {"model": {"input_per_million_usd": "1.25", "output_per_million_usd": "2.5"}}}
        )
    )
    client = MagicMock()
    response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=200))
    client.chat.completions.create.return_value = response
    tracker = CostTracker(client, tmp_path / "usage.db", "test", pricing)
    return tracker, client, response, pricing


def test_known_usage_cost_and_response_identity(setup):
    """Record configured usage costs while preserving the original SDK response."""
    tracker, client, response, _ = setup
    assert (
        tracker.create(model="model", tag="research", messages=[{"content": "secret-prompt"}])
        is response
    )
    row = load_rows(tracker.database)[0]
    assert row["input_tokens"] == 1000 and row["output_tokens"] == 200
    assert Decimal(row["estimated_cost_usd"]) == Decimal("0.00175")
    assert row["tag"] == "research" and row["latency_ms"] >= 0 and row["status"] == "success"
    assert "secret-prompt" not in json.dumps(row)
    client.chat.completions.create.assert_called_once_with(
        model="model", messages=[{"content": "secret-prompt"}]
    )


@pytest.mark.parametrize(
    "usage",
    [
        None,
        SimpleNamespace(prompt_tokens=None, completion_tokens=3),
        SimpleNamespace(prompt_tokens=2, completion_tokens=None),
        SimpleNamespace(prompt_tokens=-1, completion_tokens=3),
        SimpleNamespace(prompt_tokens=True, completion_tokens=3),
        SimpleNamespace(prompt_tokens=float("nan"), completion_tokens=3),
        SimpleNamespace(prompt_tokens=2**64, completion_tokens=3),
    ],
)
def test_incomplete_or_invalid_usage_remains_unknown(setup, usage):
    """Keep invalid usage unknown instead of reporting zero cost."""
    tracker, _, response, _ = setup
    response.usage = usage
    tracker.create(model="model")
    assert load_rows(tracker.database)[0]["estimated_cost_usd"] is None


def test_missing_price_is_unknown_but_real_zero_usage_is_zero(setup):
    """Distinguish unknown prices from an actual zero-token request."""
    tracker, _, response, _ = setup
    tracker.create(model="unpriced")
    response.usage = SimpleNamespace(prompt_tokens=0, completion_tokens=0)
    tracker.create(model="model")
    rows = load_rows(tracker.database)
    assert rows[0]["estimated_cost_usd"] is None
    assert Decimal(rows[1]["estimated_cost_usd"]) == 0


def test_provider_failure_rethrows_exact_object_and_does_not_store_message(setup):
    """Preserve the original failure without storing its potentially sensitive text."""
    tracker, client, _, _ = setup
    error = RuntimeError("provider-error-containing-a-secret")
    client.chat.completions.create.side_effect = error
    with pytest.raises(RuntimeError) as caught:
        tracker.create(model="model")
    assert caught.value is error
    row = load_rows(tracker.database)[0]
    assert row["status"] == "error" and row["error_type"] == "RuntimeError"
    assert row["estimated_cost_usd"] is None
    assert "containing-a-secret" not in json.dumps(row)


def test_storage_failure_does_not_hide_success_or_original_error(setup, monkeypatch, caplog):
    """Keep provider results intact when metadata persistence fails."""
    tracker, client, response, _ = setup
    monkeypatch.setattr(
        sqlite3, "connect", MagicMock(side_effect=sqlite3.OperationalError("secret"))
    )
    assert tracker.create(model="model") is response
    error = RuntimeError("original")
    client.chat.completions.create.side_effect = error
    with pytest.raises(RuntimeError) as caught:
        tracker.create(model="model")
    assert caught.value is error
    assert "metadata could not be saved" in caplog.text
    assert "secret" not in caplog.text


def test_unrepresentable_cost_does_not_hide_success(setup, caplog):
    """Retain usage with unknown cost when an extreme configured rate overflows."""
    tracker, _, response, _ = setup
    tracker.prices[("test", "model")] = (Decimal("1e999999"), Decimal(0))
    assert tracker.create(model="model") is response
    row = load_rows(tracker.database)[0]
    assert row["estimated_cost_usd"] is None and row["input_tokens"] == 1000
    assert "cost could not be estimated" in caplog.text


def test_streaming_is_rejected_before_sending_a_request(setup):
    """Reject unsupported streaming before invoking the client's create method."""
    tracker, client, _, _ = setup
    with pytest.raises(ValueError, match="Streaming"):
        tracker.create(model="model", stream=True)
    client.chat.completions.create.assert_not_called()
    assert load_rows(tracker.database) == []


@pytest.mark.parametrize("rate", [True, -1, "NaN", "Infinity", "not-a-rate", None])
def test_invalid_prices_are_rejected(setup, rate):
    """Reject malformed, negative and non-finite configured prices."""
    _, _, _, pricing = setup
    pricing.write_text(
        json.dumps(
            {"test": {"model": {"input_per_million_usd": rate, "output_per_million_usd": "1"}}}
        )
    )
    with pytest.raises(ValueError):
        load_pricing(pricing)


def test_provider_prices_are_separate_and_decimal_rates_are_exact(setup):
    """Keep per-provider rates separate and parse decimal JSON prices exactly."""
    _, _, _, pricing = setup
    pricing.write_text(
        '{"one":{"m":{"input_per_million_usd":0.1,"output_per_million_usd":0}},'
        '"two":{"m":{"input_per_million_usd":2,"output_per_million_usd":3}}}'
    )
    prices = load_pricing(pricing)
    assert prices[("one", "m")] == (Decimal("0.1"), Decimal(0))
    assert prices[("two", "m")] != prices[("one", "m")]


def test_parameterized_writes_and_concurrent_requests_are_not_lost(setup):
    """Store concurrent calls and literal SQL-looking tags without losing records."""
    tracker, _, _, _ = setup
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(
            pool.map(
                lambda _: tracker.create(model="model", tag="x'); DROP TABLE requests;--"),
                range(20),
            )
        )
    rows = load_rows(tracker.database)
    assert len(rows) == 20
    assert all(row["tag"] == "x'); DROP TABLE requests;--" for row in rows)


def test_read_only_dashboard_loader_does_not_create_missing_file(tmp_path):
    """Avoid creating an empty database when the dashboard path is wrong."""
    missing = tmp_path / "missing.db"
    with pytest.raises(sqlite3.Error):
        load_rows(missing)
    assert not missing.exists()


def test_demo_default_does_not_use_the_live_database(monkeypatch):
    """Keep demo records separate from the environment's live database by default."""
    constructor = MagicMock()
    monkeypatch.setattr(main, "CostTracker", constructor)
    monkeypatch.setenv("LLM_COST_DB", "host-usage.sqlite3")
    monkeypatch.setattr("sys.argv", ["main.py", "--demo"])
    assert main.main() == 0
    assert constructor.call_args.args[1] == Path(".data/demo.sqlite3")


def test_live_cli_does_not_echo_provider_error(monkeypatch, capsys):
    """Return a useful error without exposing raw provider exception content."""
    monkeypatch.setenv("LLM_API_KEY", "offline-key")
    monkeypatch.setenv("LLM_MODEL", "offline-model")
    constructor = MagicMock()
    constructor.return_value.create.side_effect = RuntimeError("secret-provider-error-body")
    monkeypatch.setattr(main, "CostTracker", constructor)
    monkeypatch.setattr("sys.argv", ["main.py"])
    assert main.main() == 1
    output = capsys.readouterr().out
    assert "RuntimeError" in output and "secret-provider-error-body" not in output


@pytest.mark.parametrize(
    "base_url", ["https://api.tokenfactory.nebius.com/v1/", "http://localhost:11434/v1/"]
)
def test_real_sdk_http_fixture_records_metadata(tmp_path, base_url):
    """Exercise actual SDK serialization for hosted and local compatible endpoints."""
    urls = []

    def respond(request):
        """Capture the request URL and serve an offline completion."""
        urls.append(str(request.url))
        return demo_reply(request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        with OpenAI(api_key="offline", base_url=base_url, http_client=transport) as client:
            tracker = CostTracker(
                client, tmp_path / "demo.db", "demo", Path("pricing.example.json")
            )
            response = tracker.create(model="fixture-model", tag="demo", messages=[])
            assert response.choices[0].message.content == "Offline fixture reply"
    assert Decimal(load_rows(tracker.database)[0]["estimated_cost_usd"]) == Decimal("0.0014")
    assert urls == [base_url + "chat/completions"]


def test_dashboard_displays_known_and_unknown_costs(setup, monkeypatch):
    """Show exact totals, unknown-cost counts and all three requested charts."""
    tracker, _, response, _ = setup
    tracker.create(model="model", tag="known")
    response.usage = None
    tracker.create(model="model", tag="unknown")
    monkeypatch.setenv("LLM_COST_DB", str(tracker.database))
    app = AppTest.from_file(str(Path("dashboard.py").resolve()), default_timeout=15).run()
    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Requests"] == "2"
    assert metrics["Unknown-cost requests"] == "1"
    assert metrics["Estimated cost (known requests)"] == "$0.00175000"
    charts = app.get("vega_lite_chart") or app.get("arrow_vega_lite_chart")
    assert len(charts) == 3


def test_dashboard_unpriced_provider_filter_keeps_total_unknown(setup, monkeypatch):
    """Keep an entirely unpriced provider's filtered total unknown."""
    tracker, client, _, pricing = setup
    tracker.create(model="model")
    other = CostTracker(client, tracker.database, "unpriced-provider", pricing)
    other.create(model="model")
    monkeypatch.setenv("LLM_COST_DB", str(tracker.database))
    app = AppTest.from_file(str(Path("dashboard.py").resolve()), default_timeout=15).run()
    app.selectbox[0].select("unpriced-provider").run()
    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Requests"] == "1"
    assert metrics["Estimated cost (known requests)"] == "Unknown"
    assert not app.get("vega_lite_chart") and not app.get("arrow_vega_lite_chart")


def test_dashboard_empty_or_missing_database_is_explained(tmp_path, monkeypatch):
    """Explain an unreadable database in the UI without crashing or creating it."""
    monkeypatch.setenv("LLM_COST_DB", str(tmp_path / "absent.db"))
    app = AppTest.from_file(str(Path("dashboard.py").resolve()), default_timeout=15).run()
    assert not app.exception
    assert "No readable request database" in app.info[0].value
