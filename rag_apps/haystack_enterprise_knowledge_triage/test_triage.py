import pytest
from haystack.document_stores.in_memory import InMemoryDocumentStore

from triage import TriageAgent, ingest, keyword_intent


@pytest.fixture(scope="module")
def agent():
    store = InMemoryDocumentStore()
    assert ingest(store) >= 10
    return TriageAgent(store, llm=None, min_confidence=0.35)


def test_intent_routing():
    assert keyword_intent("How many sick days do I get?") == "hr"
    assert keyword_intent("What is the MFA requirement?") == "security"
    assert keyword_intent("How do I roll back a deploy during an incident?") == "operations"
    assert keyword_intent("What is the meal allowance for travel?") == "finance"
    assert keyword_intent("Who won the football match?") == "general"


def test_cited_answer(agent):
    a = agent.ask("How many paid sick days do employees get?")
    assert not a.fallback
    assert a.intent == "hr"
    assert a.citations[0].startswith("hr_leave_policy.md")
    assert "10" in a.answer


def test_cross_doc_routing(agent):
    a = agent.ask("What is the daily meal allowance for international travel?")
    assert a.citations[0].startswith("expense_faq.md")


def test_no_evidence_fallback(agent):
    a = agent.ask("What is the recipe for chocolate cake?")
    assert a.fallback and a.citations == []


def test_llm_intent_and_generation_are_used():
    store = InMemoryDocumentStore()
    ingest(store)
    calls = []

    def fake(msgs):
        calls.append(msgs)
        return '{"intent": "hr"}' if "Classify" in msgs[-1].text else "10 days [1]"

    a = TriageAgent(store, llm=fake).ask("How many sick days do I get?")
    assert len(calls) == 2 and a.answer == "10 days [1]"
