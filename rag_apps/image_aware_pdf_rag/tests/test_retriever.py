
"""Tests for PDFRetriever."""

import pytest

from interfaces.vector_store import SearchResult
from retrieval.retriever import PDFRetriever


class FakeEmbeddings:
    def __init__(self):
        self.queries = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [1.0, 0.0, 0.0]


class FakeVectorStore:
    def __init__(self, results=None):
        self.results = results or []
        self.last_query_embedding = None
        self.last_top_k = None
        self.last_filters = None

    def search(self, query_embedding, top_k=5, filters=None):
        self.last_query_embedding = query_embedding
        self.last_top_k = top_k
        self.last_filters = filters

        results = self.results

        if filters:
            results = [
                result
                for result in results
                if all(
                    result.metadata.get(key) == value
                    for key, value in filters.items()
                )
            ]

        return results[:top_k]


def make_result(
    chunk_id,
    source_id,
    page_number,
    text,
    content_type="text",
):
    return SearchResult(
        id=chunk_id,
        text=text,
        metadata={
            "source_id": source_id,
            "source_name": f"{source_id}.pdf",
            "page_number": page_number,
            "content_type": content_type,
        },
        score=0.95,
    )


def test_retriever_returns_page_aware_evidence():
    embeddings = FakeEmbeddings()
    store = FakeVectorStore(
        [
            make_result(
                "a:page:3:chunk:0",
                "a",
                3,
                "Revenue increased by 20%.",
            )
        ]
    )

    retriever = PDFRetriever(embeddings, store)
    evidence = retriever.retrieve("How did revenue change?")

    assert embeddings.queries == ["How did revenue change?"]
    assert store.last_query_embedding == [1.0, 0.0, 0.0]
    assert len(evidence) == 1
    assert evidence[0].page_number == 3
    assert evidence[0].text == "Revenue increased by 20%."
    assert evidence[0].source == "a.pdf"
    assert evidence[0].content_type == "text"


def test_retriever_preserves_visual_description_type():
    store = FakeVectorStore(
        [
            make_result(
                "a:page:4:visual:0",
                "a",
                4,
                "The chart shows revenue increasing.",
                content_type="visual_description",
            )
        ]
    )

    retriever = PDFRetriever(FakeEmbeddings(), store)
    evidence = retriever.retrieve("What does the chart show?")

    assert len(evidence) == 1
    assert evidence[0].page_number == 4
    assert evidence[0].content_type == "visual_description"


@pytest.mark.parametrize("invalid_value", [None, 42, "  "])
def test_retriever_defaults_invalid_source_metadata(invalid_value):
    result = make_result("a:1", "a", 1, "Evidence")
    result.metadata["source_name"] = invalid_value
    store = FakeVectorStore([result])

    evidence = PDFRetriever(FakeEmbeddings(), store).retrieve("Question")

    assert len(evidence) == 1
    assert evidence[0].source == "uploaded PDF"


@pytest.mark.parametrize("invalid_value", [None, 42, "  "])
def test_retriever_defaults_invalid_content_type_metadata(invalid_value):
    result = make_result("a:1", "a", 1, "Evidence")
    result.metadata["content_type"] = invalid_value
    store = FakeVectorStore([result])

    evidence = PDFRetriever(FakeEmbeddings(), store).retrieve("Question")

    assert len(evidence) == 1
    assert evidence[0].content_type == "text"


def test_retriever_can_limit_search_to_one_pdf():
    store = FakeVectorStore(
        [
            make_result("a:1", "a", 1, "Evidence from PDF A"),
            make_result("b:1", "b", 2, "Evidence from PDF B"),
        ]
    )

    retriever = PDFRetriever(FakeEmbeddings(), store)
    evidence = retriever.retrieve(
        "Find evidence",
        source_id="b",
    )

    assert store.last_filters == {"source_id": "b"}
    assert len(evidence) == 1
    assert evidence[0].source == "b.pdf"


def test_retriever_respects_top_k():
    store = FakeVectorStore(
        [
            make_result("a:1", "a", 1, "First"),
            make_result("a:2", "a", 2, "Second"),
        ]
    )

    retriever = PDFRetriever(FakeEmbeddings(), store)
    evidence = retriever.retrieve("Find evidence", top_k=1)

    assert store.last_top_k == 1
    assert len(evidence) == 1


@pytest.mark.parametrize("query", ["", "   ", None, 123])
def test_retriever_rejects_invalid_query(query):
    retriever = PDFRetriever(FakeEmbeddings(), FakeVectorStore())

    with pytest.raises((ValueError, TypeError)):
        retriever.retrieve(query)


def test_retriever_rejects_invalid_top_k():
    retriever = PDFRetriever(FakeEmbeddings(), FakeVectorStore())

    with pytest.raises(ValueError):
        retriever.retrieve("Question", top_k=0)


def test_retriever_skips_results_without_valid_page_numbers():
    store = FakeVectorStore(
        [
            make_result("a:bad", "a", 0, "Invalid page"),
            make_result("a:good", "a", 2, "Valid evidence"),
        ]
    )

    retriever = PDFRetriever(FakeEmbeddings(), store)
    evidence = retriever.retrieve("Find evidence")

    assert len(evidence) == 1
    assert evidence[0].page_number == 2
    assert evidence[0].text == "Valid evidence"


def test_retriever_returns_empty_list_when_nothing_matches():
    retriever = PDFRetriever(FakeEmbeddings(), FakeVectorStore())

    assert retriever.retrieve("Unknown topic") == []
