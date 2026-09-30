"""The agent loop with a fake OpenAI-compatible client: no API key or network needed."""

import json
from types import SimpleNamespace

import pytest

from early_warning import generate, run_agent
from early_warning.agent import MAX_TOOL_ROUNDS
from early_warning.models import patient_from_dict
from early_warning.report import render
from early_warning.tools import ToolSession
from main import main


def tool_call(name, args):
    return SimpleNamespace(id=f"call_{name}", function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def completion(content=None, tool_calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))])


class FakeCompletions:
    """Behaves like a tool-calling model on Token Factory: first calls every tool it was offered,
    then answers from the tool results sent back to it."""

    def __init__(self, reply=None, error=None, never_answers=False):
        self.reply, self.error, self.never_answers, self.calls = reply, error, never_answers, 0

    def create(self, model, messages, tools, temperature):
        self.calls += 1
        if self.error:
            raise self.error
        results = {m["tool_call_id"].removeprefix("call_"): json.loads(m["content"])
                   for m in messages if m["role"] == "tool"}
        if self.never_answers or not results:
            return completion(tool_calls=[
                tool_call(t["function"]["name"], {"vital": "spo2"} if t["function"]["parameters"]["properties"] else {})
                for t in tools
            ])
        return completion(content=self.reply(results) if callable(self.reply) else self.reply)


def fake_client(**kw):
    return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(**kw)))


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
    assert r.source == "offline" and "NEBIUS_API_KEY" in r.note


def test_agent_calls_tools_and_uses_their_level():
    client = fake_client(reply=good_reply)
    r = run_agent(generate("early_sepsis"), api_key="x", client=client)
    assert r.source == "nebius" and r.note is None
    assert client.chat.completions.calls == 2  # one round of tool calls, then the answer
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
    client = fake_client(never_answers=True)
    r = run_agent(generate("runner"), api_key="x", client=client)
    assert r.source == "offline" and "did not answer" in r.note
    assert client.chat.completions.calls == MAX_TOOL_ROUNDS


def test_a_think_block_before_the_answer_is_ignored():
    client = fake_client(reply=lambda res: "<think>{not json}</think>\n" + good_reply(res))
    r = run_agent(generate("early_sepsis"), api_key="x", client=client)
    assert r.source == "nebius" and r.explanation["clinician_summary"].startswith("SpO2")


def test_tool_specs_match_the_tools():
    session = ToolSession(generate("stable"))
    specs = {s["function"]["name"]: s["function"] for s in session.specs()}
    assert set(specs) == {t.__name__ for t in session.tools()}
    assert all(s["description"] and s["parameters"]["type"] == "object" for s in specs.values())
    assert specs["check_trend"]["parameters"]["required"] == ["vital"]


def test_bad_tool_calls_from_the_model_return_errors():
    session = ToolSession(generate("stable"))
    assert "error" in session.call("get_lab_results", "{}")
    assert "error" in session.call("check_trend", "not json")
    assert "error" in session.call("check_trend", "[1]")
    assert "error" in session.call("check_trend", json.dumps({"vital": "hr", "hours": "soon"}))
    assert "error" in session.call("get_news2", json.dumps({"extra": 1}))
    assert session.call("get_news2", None)["total"] >= 0


@pytest.mark.parametrize("data", [[], "patient", 3])
def test_patient_json_must_be_an_object(data):
    with pytest.raises(ValueError):
        patient_from_dict(data)


def test_bad_tool_argument_returns_an_error_not_a_crash():
    tools = {t.__name__: t for t in ToolSession(generate("stable")).tools()}
    assert "error" in tools["check_trend"](vital="glucose")
    assert tools["check_trend"](vital="hr", hours=100)["window_hours"] == 12.0


def test_report_and_cli(capsys):
    r = run_agent(generate("early_sepsis"), offline=True)
    text = render(r, "Early sepsis")
    assert "Level:" in text and "Contributing factors" in text and "not diagnosis" in text
    assert main(["--sample", "copd", "--offline"]) == 0
    assert "Level: Stable" in capsys.readouterr().out
