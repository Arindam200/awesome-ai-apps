"""The agent loop with a fake Gemini client: no API key or network needed."""

import json
from types import SimpleNamespace

from early_warning import generate, run_agent
from early_warning.report import render
from main import main


class FakeModels:
    """Behaves like automatic function calling: calls every tool it was given, then answers."""

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, 0

    def generate_content(self, model, contents, config):
        self.calls += 1
        if self.error:
            raise self.error
        results = {}
        for tool in config.tools:
            name = tool.__name__
            if name in ("check_personal_baseline", "check_trend"):
                results[name] = tool(vital="spo2")
            else:
                results[name] = tool()
        text = self.reply(results) if callable(self.reply) else self.reply
        return SimpleNamespace(text=text)


def fake_client(**kw):
    return SimpleNamespace(models=FakeModels(**kw))


def good_reply(results, level=None):
    a = results["get_risk_assessment"]
    return json.dumps({
        "level": level or a["level"],
        "clinician_summary": f"SpO2 is drifting; score {a['score']}.",
        "key_findings": [f["detail"] for f in a["factors"][:2]],
        "patient_message": "A doctor will check on you.",
        "suggested_review": a["urgency"],
    })


def test_offline_mode_needs_no_key():
    r = run_agent(generate("slow_hypoxia"), offline=True)
    assert r.source == "offline" and r.assessment["level"] == r.explanation["level"]
    assert r.explanation["clinician_summary"].startswith(r.assessment["level"])


def test_missing_key_falls_back_with_a_note():
    r = run_agent(generate("stable"), api_key="")
    assert r.source == "offline" and "GEMINI_API_KEY" in r.note


def test_agent_calls_tools_and_uses_their_level():
    client = fake_client(reply=good_reply)
    r = run_agent(generate("early_sepsis"), api_key="x", client=client)
    assert r.source == "gemini" and r.note is None
    tools_called = {t["tool"] for t in r.trace}
    assert {"get_news2", "get_qsofa", "get_risk_assessment", "check_trend"} <= tools_called
    json.dumps([t["result"] for t in r.trace])  # tool results are JSON-able for the model


def test_a_wrong_level_from_the_model_is_overridden():
    client = fake_client(reply=lambda res: good_reply(res, level="Stable"))
    r = run_agent(generate("early_sepsis"), api_key="x", client=client)
    assert r.explanation["level"] == r.assessment["level"] != "Stable"
    assert "tool-computed level" in r.note


def test_unparseable_reply_and_errors_fall_back():
    r = run_agent(generate("runner"), api_key="x", client=fake_client(reply="I think the patient is fine."))
    assert r.source == "offline" and "could not be parsed" in r.note
    r = run_agent(generate("runner"), api_key="x", client=fake_client(error=RuntimeError("quota")))
    assert r.source == "offline" and "RuntimeError" in r.note


def test_bad_tool_argument_returns_an_error_not_a_crash():
    from early_warning.tools import ToolSession

    tools = {t.__name__: t for t in ToolSession(generate("stable")).tools()}
    assert "error" in tools["check_trend"](vital="glucose")
    assert tools["check_trend"](vital="hr", hours=100)["window_hours"] == 12.0


def test_report_and_cli(capsys):
    r = run_agent(generate("early_sepsis"), offline=True)
    text = render(r, "Early sepsis")
    assert "Level:" in text and "Contributing factors" in text and "not diagnosis" in text
    assert main(["--sample", "copd", "--offline"]) == 0
    assert "Level: Stable" in capsys.readouterr().out
