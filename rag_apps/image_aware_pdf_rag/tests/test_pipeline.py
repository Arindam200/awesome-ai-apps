
"""Tests for the provider-independent PDF RAG answer pipeline."""

from types import SimpleNamespace

import pytest

from pipeline import (
    AnswerOrchestrator,
    RetrievedEvidence,
)


class FakeRetriever:
    """Return predefined evidence without using a real vector database."""

    def __init__(self, evidence=None):
        self.evidence = evidence or []
        self.last_query = None
        self.last_top_k = None

    def retrieve(self, query: str, top_k: int = 5):
        self.last_query = query
        self.last_top_k = top_k
        return self.evidence


class FakeChatModel:
    """Return a predefined answer without calling an LLM API."""

    def __init__(self, answer="The report shows positive growth."):
        self.answer = answer
        self.last_messages = None

    def generate(self, messages):
        self.last_messages = messages
        return self.answer


@pytest.fixture
def sample_evidence():
    return [
        RetrievedEvidence(
            page_number=2,
            text="Revenue increased by 15% in 2025.",
            source="annual_report.pdf",
            content_type="text",
        ),
        RetrievedEvidence(
            page_number=4,
            text="The bar chart shows growth across all quarters.",
            source="annual_report.pdf",
            content_type="visual_description",
        ),
    ]


def test_answer_question_returns_answer_and_citations(sample_evidence):
    retriever = FakeRetriever(sample_evidence)
    chat_model = FakeChatModel()
    orchestrator = AnswerOrchestrator(retriever, chat_model)

    result = orchestrator.answer_question(
        "What does the report say about growth?"
    )

    assert result.answer == "The report shows positive growth."
    assert len(result.citations) == 2
    assert {citation.page_number for citation in result.citations} == {2, 4}
    assert "The report shows positive growth." in result.formatted_answer


def test_retriever_receives_question_and_top_k(sample_evidence):
    retriever = FakeRetriever(sample_evidence)
    orchestrator = AnswerOrchestrator(
        retriever=retriever,
        chat_model=FakeChatModel(),
        top_k=3,
    )

    orchestrator.answer_question("What is the revenue growth?")

    assert retriever.last_query == "What is the revenue growth?"
    assert retriever.last_top_k == 3


def test_chat_model_receives_system_prompt_and_evidence(sample_evidence):
    chat_model = FakeChatModel()
    orchestrator = AnswerOrchestrator(
        retriever=FakeRetriever(sample_evidence),
        chat_model=chat_model,
    )

    orchestrator.answer_question("Summarize the report.")

    messages = chat_model.last_messages

    assert messages is not None
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Summarize the report." in messages[1]["content"]
    assert "Revenue increased by 15% in 2025." in messages[1]["content"]
    assert "Page: 2" in messages[1]["content"]
    assert "bar chart shows growth" in messages[1]["content"]


def test_answer_question_includes_recent_chat_history(sample_evidence):
    chat_model = FakeChatModel()
    orchestrator = AnswerOrchestrator(
        retriever=FakeRetriever(sample_evidence),
        chat_model=chat_model,
    )
    history = [
        {"role": "user", "content": "What is the report about?"},
        {"role": "assistant", "content": "It is about revenue growth."},
    ]

    orchestrator.answer_question(
        "Can you expand on that?",
        history=history,
    )

    assert chat_model.last_messages is not None
    assert chat_model.last_messages[1:3] == history
    assert "Can you expand on that?" in chat_model.last_messages[3]["content"]


def test_empty_retrieval_returns_message_without_calling_chat_model():
    retriever = FakeRetriever([])
    chat_model = FakeChatModel()
    orchestrator = AnswerOrchestrator(retriever, chat_model)

    result = orchestrator.answer_question("What is the report about?")

    assert "couldn't find relevant evidence" in result.answer.lower()
    assert result.citations == []
    assert result.formatted_answer
    assert chat_model.last_messages is None


def test_empty_question_raises_value_error():
    orchestrator = AnswerOrchestrator(
        FakeRetriever([]),
        FakeChatModel(),
    )

    with pytest.raises(ValueError, match="Question cannot be empty"):
        orchestrator.answer_question("   ")


@pytest.mark.parametrize("top_k", [0, -1, True, 1.5])
def test_invalid_top_k_raises_value_error(top_k):
    with pytest.raises(ValueError, match="top_k must be a positive integer"):
        AnswerOrchestrator(
            retriever=FakeRetriever([]),
            chat_model=FakeChatModel(),
            top_k=top_k,
        )


@pytest.mark.parametrize(
    "invalid_answer",
    ["", "   ", None, 123],
)
def test_invalid_chat_response_raises_runtime_error(invalid_answer, sample_evidence):
    orchestrator = AnswerOrchestrator(
        retriever=FakeRetriever(sample_evidence),
        chat_model=FakeChatModel(invalid_answer),
    )

    with pytest.raises(
        RuntimeError,
        match="Chat model returned an empty or invalid answer",
    ):
        orchestrator.answer_question("What does the report say?")


def test_invalid_page_number_is_rejected():
    retriever = FakeRetriever(
        [
            {
                "page_number": 0,
                "text": "Some evidence",
                "source": "report.pdf",
            }
        ]
    )
    orchestrator = AnswerOrchestrator(retriever, FakeChatModel())

    with pytest.raises(
        ValueError,
        match="one-based page_number",
    ):
        orchestrator.answer_question("What does the report say?")


def test_structural_evidence_object_is_accepted():
    retriever = FakeRetriever(
        [
            SimpleNamespace(
                page_number=2,
                text="The report shows growth.",
                source="report.pdf",
                content_type="text",
            )
        ]
    )
    orchestrator = AnswerOrchestrator(retriever, FakeChatModel())

    result = orchestrator.answer_question("What does the report show?")

    assert result.citations[0].page_number == 2
    assert result.citations[0].source == "report.pdf"


@pytest.mark.parametrize(
    "item",
    [
        SimpleNamespace(
            page_number=1,
            text="Evidence",
            source="report.pdf",
        ),
    ],
)
def test_missing_evidence_fields_are_rejected(item):
    orchestrator = AnswerOrchestrator(FakeRetriever([item]), FakeChatModel())

    with pytest.raises(TypeError, match="missing required"):
        orchestrator.answer_question("What does the report say?")


def test_blank_evidence_is_ignored():
    retriever = FakeRetriever(
        [
            RetrievedEvidence(
                page_number=1,
                text="   ",
            )
        ]
    )
    chat_model = FakeChatModel()
    orchestrator = AnswerOrchestrator(retriever, chat_model)

    result = orchestrator.answer_question("Summarize this PDF.")

    assert "usable text or visual evidence" in result.answer.lower()
    assert result.citations == []
    assert chat_model.last_messages is None


def test_visual_evidence_content_type_is_preserved():
    retriever = FakeRetriever(
        [
            RetrievedEvidence(
                page_number=3,
                text="The diagram contains three processing stages.",
                source="architecture.pdf",
                content_type="visual_description",
            )
        ]
    )
    chat_model = FakeChatModel("The diagram has three processing stages.")
    orchestrator = AnswerOrchestrator(retriever, chat_model)

    result = orchestrator.answer_question(
        "How many processing stages are shown?"
    )

    assert result.answer == "The diagram has three processing stages."
    assert len(result.citations) == 1
    assert result.citations[0].page_number == 3
    assert "Content type: visual_description" in chat_model.last_messages[1]["content"]
