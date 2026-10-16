
import pytest

from pipeline import AnswerOrchestrator, RetrievedEvidence


class FakeRetriever:
    def __init__(self, evidence):
        self.evidence = evidence
        self.last_query = None
        self.last_top_k = None

    def retrieve(self, query, top_k=5):
        self.last_query = query
        self.last_top_k = top_k
        return self.evidence


class FakeChatModel:
    def __init__(self, response="Revenue increased in Q4."):
        self.response = response
        self.last_messages = None
        self.calls = 0

    def generate(self, messages):
        self.calls += 1
        self.last_messages = messages
        return self.response


def test_answer_includes_page_citations():
    retriever = FakeRetriever([
        RetrievedEvidence(
            page_number=3,
            text="Revenue increased by 20% in Q4.",
            source="report.pdf",
        ),
    ])
    chat_model = FakeChatModel()

    orchestrator = AnswerOrchestrator(retriever, chat_model)
    result = orchestrator.answer_question(
        "What happened to revenue?"
    )

    assert result.answer == "Revenue increased in Q4."
    assert len(result.citations) == 1
    assert result.citations[0].page_number == 3
    assert "[Page 3]" in result.formatted_answer


def test_multiple_pages_keep_their_page_numbers():
    retriever = FakeRetriever([
        RetrievedEvidence(2, "Sales increased."),
        RetrievedEvidence(5, "Costs decreased."),
    ])
    chat_model = FakeChatModel("Sales increased and costs decreased.")

    result = AnswerOrchestrator(
        retriever, chat_model
    ).answer_question("Summarize the findings.")

    page_numbers = [c.page_number for c in result.citations]

    assert page_numbers == [2, 5]
    assert "[Page 2]" in result.formatted_answer
    assert "[Page 5]" in result.formatted_answer


def test_empty_retrieval_does_not_call_llm():
    retriever = FakeRetriever([])
    chat_model = FakeChatModel()

    result = AnswerOrchestrator(
        retriever, chat_model
    ).answer_question("What is in the PDF?")

    assert result.citations == []
    assert "couldn't find relevant evidence" in result.answer
    assert chat_model.calls == 0


def test_question_is_passed_to_retriever():
    retriever = FakeRetriever([
        RetrievedEvidence(1, "The report covers 2025.")
    ])
    chat_model = FakeChatModel()

    AnswerOrchestrator(
        retriever, chat_model, top_k=3
    ).answer_question("What year is covered?")

    assert retriever.last_query == "What year is covered?"
    assert retriever.last_top_k == 3


def test_prompt_contains_retrieved_evidence():
    retriever = FakeRetriever([
        RetrievedEvidence(
            page_number=4,
            text="The chart shows a 15% increase.",
            content_type="visual_description",
        )
    ])
    chat_model = FakeChatModel("The chart shows a 15% increase.")

    AnswerOrchestrator(
        retriever, chat_model
    ).answer_question("What does the chart show?")

    prompt = chat_model.last_messages[1]["content"]

    assert "The chart shows a 15% increase." in prompt
    assert "Page: 4" in prompt
    assert "visual_description" in prompt


def test_empty_question_is_rejected():
    orchestrator = AnswerOrchestrator(
        FakeRetriever([]), FakeChatModel()
    )

    with pytest.raises(ValueError):
        orchestrator.answer_question("   ")


def test_empty_model_response_is_rejected():
    orchestrator = AnswerOrchestrator(
        FakeRetriever([
            RetrievedEvidence(1, "Some evidence.")
        ]),
        FakeChatModel("   "),
    )

    with pytest.raises(RuntimeError):
        orchestrator.answer_question("Summarize the evidence.")


def test_invalid_retrieved_page_number_is_rejected():
    orchestrator = AnswerOrchestrator(
        FakeRetriever([
            RetrievedEvidence(0, "Invalid page.")
        ]),
        FakeChatModel(),
    )

    with pytest.raises(ValueError):
        orchestrator.answer_question("What is shown?")
