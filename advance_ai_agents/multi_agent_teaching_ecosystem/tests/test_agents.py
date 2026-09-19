"""Offline tests: no API key and no network needed."""

from fractions import Fraction

import pytest

from teaching_ecosystem.agents import analyst, coach, curator, diagnostician, examiner
from teaching_ecosystem.llm import LLMError, OfflineLLM
from teaching_ecosystem.state import (
    GAP_BELOW,
    PRIOR,
    apply_diagnosis,
    close_gap,
    new_student,
)
from teaching_ecosystem.topic import (
    is_simplest,
    load_personas,
    load_topic,
    parse_answer,
)
from teaching_ecosystem.workflow import build_workflow, initial_state


@pytest.fixture(scope="module")
def topic():
    return load_topic()


class FailingLLM:
    name = "failing"

    def generate(self, **kwargs):
        raise LLMError("simulated outage")


def test_topic_pack_is_consistent(topic):
    assert len(topic.questions) == 40
    assert topic.order[0] == "C1" and topic.order[-1] == "C8"
    for q in topic.questions.values():
        if q["kind"] == "mcq":
            assert sum(1 for o in q["options"] if o.get("correct")) == 1
            assert all(o["tag"] in topic.taxonomy for o in q["options"] if not o.get("correct"))


@pytest.mark.parametrize("text,value", [("3/5", Fraction(3, 5)), ("0.6", Fraction(3, 5)), ("6 pieces", Fraction(6)),
                                        ("2 / 1", Fraction(2)), ("they are equal", None)])
def test_parse_answer(text, value):
    assert parse_answer(text) == value


def test_is_simplest():
    assert is_simplest("3/5") and is_simplest("2") and not is_simplest("5/10")


def test_mastery_update_and_gap(topic):
    s = new_student("s1", "Asha", "kn", topic.order)
    q = topic.questions["Q16"]
    apply_diagnosis(s, q, "4/8", diagnostician.diagnose_mcq(q, "4/8"))
    assert s.mastery["C4"] == pytest.approx(PRIOR - 0.20)
    apply_diagnosis(s, q, "4/8", diagnostician.diagnose_mcq(q, "4/8"))
    assert s.mastery["C4"] < GAP_BELOW and s.gaps["C4"] == "open"
    assert s.top_gap() == ("C4", "add_denominators")
    assert close_gap(s, "C4", retry_correct=True) and s.gaps["C4"] == "closed"


def test_mcq_diagnosis_uses_the_answer_key(topic):
    q = topic.questions["Q16"]
    assert diagnostician.diagnose_mcq(q, "1")["correct"]
    d = diagnostician.diagnose_mcq(q, "4/8")
    assert d["misconception_tag"] == "add_denominators" and d["source"] == "key"


def test_text_diagnosis_rules_then_llm(topic):
    q = topic.questions["Q19"]  # 2/5 + 1/10 in simplest form
    assert diagnostician.diagnose_text(topic, q, "1/2", None)["correct"]
    assert diagnostician.diagnose_text(topic, q, "0.5", None)["correct"]
    unsimplified = diagnostician.diagnose_text(topic, q, "5/10", None)
    assert not unsimplified["correct"] and unsimplified["misconception_tag"] == "careless_arithmetic"
    unknown = diagnostician.diagnose_text(topic, q, "7/15", OfflineLLM())
    assert unknown["source"] == "offline" and unknown["misconception_tag"] == "unclassified"
    outage = diagnostician.diagnose_text(topic, q, "7/15", FailingLLM())
    assert outage["source"] == "fallback" and not outage["correct"]


def test_photo_without_vision_asks_for_typed_answer(topic):
    d = diagnostician.diagnose_photo(topic, topic.questions["Q22"], b"not-an-image", OfflineLLM())
    assert d["needs_typed_answer"]


def test_examiner_respects_prerequisites(topic):
    s = new_student("s1", "Asha", "en", topic.order)
    question, reason = examiner.next_question(topic, s)
    assert question["concept_id"] == "C1"          # only the root is ready at the prior
    s.mastery["C1"] = 0.65
    s.mastery["C3"] = 0.65
    question, _ = examiner.next_question(topic, s)
    assert question["concept_id"] in {"C2", "C4", "C5"}
    assert "prerequisites" in reason


def test_analyst_challenges_a_whole_class_reteach(topic):
    students = {}
    for i in range(10):
        s = new_student(f"s{i}", f"S{i}", "en", topic.order)
        q = topic.questions["Q16"]
        answer = "4/8" if i < 3 else "1"   # 3 of 10 make the mistake
        apply_diagnosis(s, q, answer, diagnostician.diagnose_mcq(q, answer))
        students[s.id] = s
    a = analyst.analyze(topic, students)
    proposal = {"recommendations": [{"group_label": "Whole class", "concept_id": "C4",
                                     "misconception_tag": "add_denominators", "headline": "Re-teach adding",
                                     "plan_5min": ["a", "b", "c"], "worked_example": "3/4 + 1/4 = 1", "why": ""}]}
    critiques = analyst.rule_critiques(a, proposal)
    assert critiques[0]["verdict"] == "revise" and "3 of 10" in critiques[0]["reason"]


def test_curator_caches_and_uses_bank_for_retry(topic):
    cache = {}
    llm = OfflineLLM()
    first, source = curator.lesson(topic, "C4", "add_denominators", "en", llm, cache)
    _again, source_again = curator.lesson(topic, "C4", "add_denominators", "en", llm, cache)
    assert source == "offline" and source_again == "cache" and len(first["practice"]) == 3
    retry = curator.retry_items(topic, None, "C4", "add_denominators")
    assert len(retry) == 2 and all(r["question_id"] in topic.questions for r in retry)


def test_script_share():
    assert curator.script_share("ಛೇದಗಳು ಒಂದೇ", "kn") == 1.0
    assert curator.script_share("denominators", "kn") == 0.0


def test_coach_falls_back_to_a_template(topic):
    s = new_student("s1", "Asha", "en", topic.order)
    students = {"s1": s}
    a = analyst.analyze(topic, students)
    proposal, source = coach.propose(topic, a, students, FailingLLM())
    assert source == "template" and proposal["recommendations"]
    message, msource = coach.parent_message(topic, s, "C4", "add_denominators", FailingLLM())
    assert msource == "template" and "Asha" in message["message"]


def test_full_workflow_offline(topic):
    llm = OfflineLLM()
    graph = build_workflow(llm)
    final = graph.invoke(initial_state(topic, load_personas(), seed=42))
    agents = [e["agent"] for e in final["events"]]
    assert agents[0] == "Examiner" and "Analyst" in agents and agents[-1] == "Coach"
    assert final["analysis"]["n_students"] == 30
    assert any(c["verdict"] == "revise" for c in final["critiques"])     # the naive draft is challenged
    assert final["recommendations"][0]["group_label"].startswith("Group A")
    assert len(final["lessons"]) == 3 and all(len(lesson["retry"]) == 2 for lesson in final["lessons"])
    assert "TextDiagnosis" not in llm.calls                                  # the simulated class never needs the LLM


def test_workflow_is_deterministic(topic):
    def run():
        return build_workflow(OfflineLLM()).invoke(initial_state(topic, load_personas(), seed=7))

    first, second = run(), run()
    assert first["analysis"] == second["analysis"]
