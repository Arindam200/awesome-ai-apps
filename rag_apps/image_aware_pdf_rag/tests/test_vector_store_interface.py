
import math

import pytest

from interfaces.vector_store import (
    SearchResult,
    VectorDocument,
    VectorStore,
    validate_document,
    validate_search_input,
    validate_vector,
)


class FakeVectorStore:
    """Minimal in-memory implementation for contract testing."""

    def __init__(self):
        self.documents = {}

    def add_documents(self, documents):
        for document in documents:
            validate_document(document)
            self.documents[document.id] = document

    def search(self, query_embedding, top_k=5, filters=None):
        validate_search_input(query_embedding, top_k)

        results = []

        for document in self.documents.values():
            if filters and any(
                document.metadata.get(key) != value
                for key, value in filters.items()
            ):
                continue

            if len(document.embedding) != len(query_embedding):
                raise ValueError("Embedding dimensions do not match")

            # Dot product for this simple mock only.
            score = sum(
                a * b
                for a, b in zip(query_embedding, document.embedding)
            )

            results.append(
                SearchResult(
                    id=document.id,
                    text=document.text,
                    metadata=document.metadata,
                    score=score,
                )
            )

        return sorted(
            results,
            key=lambda result: result.score,
            reverse=True,
        )[:top_k]

    def delete(self, ids):
        for document_id in ids:
            self.documents.pop(document_id, None)


def make_document(
    document_id="chunk-1",
    page_number=1,
    text="Revenue increased.",
    embedding=None,
):
    return VectorDocument(
        id=document_id,
        text=text,
        embedding=embedding or [0.8, 0.2],
        metadata={
            "page_number": page_number,
            "source_id": "report.pdf",
            "content_type": "text",
        },
    )


def test_fake_store_implements_interface():
    assert isinstance(FakeVectorStore(), VectorStore)


def test_add_and_search_document():
    store = FakeVectorStore()
    store.add_documents([make_document()])

    results = store.search([0.8, 0.2], top_k=1)

    assert len(results) == 1
    assert results[0].id == "chunk-1"
    assert results[0].text == "Revenue increased."
    assert results[0].metadata["page_number"] == 1


def test_preserves_page_metadata():
    store = FakeVectorStore()
    store.add_documents([make_document(page_number=7)])

    result = store.search([0.8, 0.2])[0]

    assert result.metadata["page_number"] == 7


def test_search_respects_top_k():
    store = FakeVectorStore()
    store.add_documents([
        make_document("chunk-1", 1, "First"),
        make_document("chunk-2", 2, "Second", [0.7, 0.3]),
    ])

    assert len(store.search([0.8, 0.2], top_k=1)) == 1


def test_search_filters_metadata():
    store = FakeVectorStore()
    store.add_documents([
        make_document("chunk-1", 1, "First"),
        make_document("chunk-2", 2, "Second"),
    ])

    results = store.search(
        [0.8, 0.2],
        filters={"page_number": 2},
    )

    assert len(results) == 1
    assert results[0].metadata["page_number"] == 2


def test_delete_document():
    store = FakeVectorStore()
    store.add_documents([make_document()])

    store.delete(["chunk-1"])

    assert store.search([0.8, 0.2]) == []


def test_rejects_empty_document_id():
    with pytest.raises(ValueError, match="ID"):
        validate_document(make_document(document_id=" "))


def test_rejects_invalid_page_number():
    with pytest.raises(ValueError, match="page_number"):
        validate_document(make_document(page_number=0))


def test_rejects_invalid_vectors():
    with pytest.raises(ValueError):
        validate_vector([])

    with pytest.raises(ValueError):
        validate_vector([math.nan])

    with pytest.raises(ValueError):
        validate_vector([True])


def test_rejects_invalid_top_k():
    with pytest.raises(ValueError):
        validate_search_input([0.1, 0.2], 0)


def test_rejects_mismatched_embedding_dimensions():
    store = FakeVectorStore()
    store.add_documents([make_document(embedding=[0.1, 0.2])])

    with pytest.raises(ValueError, match="dimensions"):
        store.search([0.1, 0.2, 0.3])
