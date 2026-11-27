"""Offline checks of the healing layer: no model calls.

Guardrails: allowlist, open-bug rule, syntax check, rollback, repair budget.
Sorting: each kind of failure gets the right label, and only CODE_BUG opens a repair."""
import os
import shutil
from types import SimpleNamespace

import pytest

from config import ROOT, TOOLS_DIR
from healing.healer import Healer, HealingMiddleware, tool_path
from healing.recorder import Recorder
from provider_api.server import FAULTS

BROKEN = ROOT / "scenarios" / "broken" / "fetch_pricing.py"
WORKING = ROOT / "scenarios" / "working" / "fetch_pricing.py"
TARGET = TOOLS_DIR / "fetch_pricing.py"
FIX = [{"find": 'data["price_usd"]', "replace": 'data["pricing"]["unit_usd"]'},
       {"find": 'data["cached_price_usd"]', "replace": 'data["pricing"]["cached_unit_usd"]'},
       {"find": 'data["output_price_usd"]', "replace": 'data["pricing"]["output_unit_usd"]'}]
ARGS = {"model_id": "meta-llama/Llama-3.3-70B-Instruct"}


@pytest.fixture
def healer(provider_api):
    shutil.copy(BROKEN, TARGET)
    os.chdir(ROOT)
    h = Healer(Recorder(live=False), provider_api)
    yield h
    shutil.copy(WORKING, TARGET)
    shutil.rmtree(ROOT / "failures", ignore_errors=True)


def call(healer, name="fetch_pricing", args=ARGS):
    """Run one tool call through the middleware, like the agent would."""
    tool = next(t for t in healer.langchain_tools() if t.name == name)
    request = SimpleNamespace(tool_call={"name": name, "args": args, "id": "call_1"})
    return HealingMiddleware(healer).wrap_tool_call(request, lambda req: tool.func(**req.tool_call["args"]))


def open_bug(healer):
    out = call(healer)
    assert out.content.startswith("CODE_BUG")
    return out


# ---------------------------------------------------------------- guardrails
def test_allowlist_blocks_files_outside_tools():
    for name in ("../contracts", "__init__", "../provider_api/client", "../tests/test_fetch_pricing"):
        with pytest.raises(PermissionError):
            tool_path(name)


def test_no_repair_without_an_open_code_bug(healer):
    assert healer.repair("fetch_pricing", "guess", FIX).startswith("REPAIR REFUSED")
    assert TARGET.read_text() == BROKEN.read_text()


def test_syntax_error_is_rejected_before_save(healer):
    open_bug(healer)
    out = healer.repair("fetch_pricing", "x", [{"find": 'data["price_usd"]', "replace": 'data["pricing"'}])
    assert out.startswith("REPAIR REJECTED")
    assert TARGET.read_text() == BROKEN.read_text()


def test_patch_that_fails_checks_is_rolled_back(healer):
    open_bug(healer)
    out = healer.repair("fetch_pricing", "x", [{"find": 'float(data["price_usd"])', "replace": "1.0"}])
    assert "rolled back" in out
    assert TARGET.read_text() == BROKEN.read_text()
    assert not TARGET.with_suffix(".py.bak").exists()


def test_repair_budget_is_two_per_tool(healer):
    open_bug(healer)
    bad = [{"find": 'float(data["price_usd"])', "replace": "1.0"}]
    healer.repair("fetch_pricing", "x", bad)
    healer.repair("fetch_pricing", "x", bad)
    assert healer.repair("fetch_pricing", "x", FIX).startswith("REPAIR REFUSED")


def test_correct_patch_is_kept_and_tool_recovers(healer):
    open_bug(healer)
    assert healer.repair("fetch_pricing", "API nests prices", FIX).startswith("REPAIR VERIFIED")
    assert 'data["pricing"]["unit_usd"]' in TARGET.read_text()
    call(healer)
    assert any(e["type"] == "recovered" for e in healer.rec.events)


# ---------------------------------------------------------------- sorting failures
def test_rate_limit_is_retried_not_repaired(healer):
    shutil.copy(WORKING, TARGET)
    FAULTS.reset(rate_limit_pricing=2)
    out = call(healer)
    assert '"input_usd_per_1m": 0.13' in str(getattr(out, "content", out))
    assert sum(e["type"] == "retry" for e in healer.rec.events) == 2
    assert healer.open_bugs == {}


def test_expired_key_needs_a_human(healer):
    shutil.copy(WORKING, TARGET)
    FAULTS.reset(expired_key=True)
    out = call(healer)
    assert out.content.startswith("NEEDS_HUMAN")
    assert healer.open_bugs == {}
    assert healer.repair("fetch_pricing", "x", FIX).startswith("REPAIR REFUSED")


def test_retired_model_is_a_bad_argument(healer):
    shutil.copy(WORKING, TARGET)
    out = call(healer, args={"model_id": "Qwen/Qwen3-235B-A22B-Instruct"})
    assert out.content.startswith("BAD_ARGUMENTS")
    assert "Qwen/Qwen3-235B-A22B-Instruct-2507" in out.content
    assert healer.open_bugs == {}


def test_wrong_output_is_a_code_bug(healer):
    shutil.copy(WORKING, TARGET)
    shutil.copy(ROOT / "scenarios" / "broken" / "fetch_usage.py", TOOLS_DIR / "fetch_usage.py")
    try:
        out = call(healer, "fetch_usage", {"month": "2026-11"})
        assert out.content.startswith("CODE_BUG")
        assert "API reported total=26" in (ROOT / "failures" / "fetch_usage.md").read_text()
    finally:
        shutil.copy(ROOT / "scenarios" / "working" / "fetch_usage.py", TOOLS_DIR / "fetch_usage.py")
