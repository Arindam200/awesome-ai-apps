
"""Tests for the local FAISS vector store."""

import numpy as np
import pytest

from interfaces.vector_store import VectorDocument
from vectorstores.faiss_store import FAISSVectorStore


def make_document(
    chunk_id: str,
    source_id: str,
    page_number: int,
    embedding: list[float],
    text: str | None = None,
) -> VectorDocument:
    return VectorDocument(
        id=chunk_id,
        text=text or f"Text for {chunk_id}",
        embedding=embedding,
        metadata={
            "source_id": source_id,
            "source_name": f"{source_id}.pdf",
            "page_number": page_number,
            "content_type": "text",
        },
    )


def test_add_and_search_documents():
    store = FAISSVectorStore(dimension=3)

    store.add_documents(
        [
            make_document("a:1", "a", 1, [1, 0, 0], "Revenue increased."),
            make_document("b:1", "b", 1, [0, 1, 0], "Hiring increased."),
        ]
    )

    results = store.search([1, 0, 0], top_k=1)

    assert len(results) == 1
    assert results[0].id == "a:1"
    assert results[0].text == "Revenue increased."
    assert results[0].metadata["page_number"] == 1
    assert results[0].score == pytest.approx(1.0)


def test_metadata_filter_limits_search_to_one_pdf():
    store = FAISSVectorStore(dimension=3)

    store.add_documents(
        [
            make_document("a:1", "a", 1, [1, 0, 0]),
            make_document("b:1", "b", 1, [1, 0, 0]),
        ]
    )

    results = store.search(
        [1, 0, 0],
        top_k=5,
        filters={"source_id": "b"},
    )

    assert len(results) == 1
    assert results[0].id == "b:1"
    assert results[0].metadata["source_id"] == "b"


def test_delete_source_does_not_delete_other_pdfs():
    store = FAISSVectorStore(dimension=3)

    store.add_documents(
        [
            make_document("a:1", "a", 1, [1, 0, 0]),
            make_document("a:2", "a", 2, [0.9, 0.1, 0]),
            make_document("b:1", "b", 1, [0, 1, 0]),
        ]
    )

    deleted = store.delete_source("a")
    remaining = store.search([1, 0, 0], top_k=10)

    assert deleted == 2
    assert {item.id for item in remaining} == {"b:1"}


def test_delete_unknown_source_is_safe():
    store = FAISSVectorStore(dimension=3)
    store.add_documents(
        [make_document("a:1", "a", 1, [1, 0, 0])]
    )

    assert store.delete_source("missing") == 0
    assert len(store.search([1, 0, 0], top_k=5)) == 1


def test_readding_same_chunk_id_replaces_old_document():
    store = FAISSVectorStore(dimension=3)

    store.add_documents(
        [make_document("a:1", "a", 1, [1, 0, 0], "Old text")]
    )
    store.add_documents(
        [make_document("a:1", "a", 1, [0, 1, 0], "Updated text")]
    )

    results = store.search([0, 1, 0], top_k=5)

    assert len(results) == 1
    assert results[0].text == "Updated text"
    assert results[0].id == "a:1"


def test_save_and_reload(tmp_path):
    store = FAISSVectorStore(
        dimension=3,
        persist_dir=tmp_path,
    )
    store.add_documents(
        [
            make_document(
                "report:page:2:chunk:0",
                "report",
                2,
                [1, 0, 0],
                "Revenue was 20% higher.",
            )
        ]
    )

    version = (tmp_path / FAISSVectorStore.CURRENT_FILENAME).read_text(
        encoding="ascii"
    )
    version_dir = tmp_path / FAISSVectorStore.VERSIONS_DIRNAME / version
    assert (version_dir / FAISSVectorStore.INDEX_FILENAME).exists()
    assert (version_dir / FAISSVectorStore.METADATA_FILENAME).exists()

    loaded = FAISSVectorStore.load(tmp_path)
    results = loaded.search([1, 0, 0], top_k=1)

    assert len(results) == 1
    assert results[0].id == "report:page:2:chunk:0"
    assert results[0].metadata["source_id"] == "report"
    assert results[0].metadata["page_number"] == 2
    assert results[0].text == "Revenue was 20% higher."


def test_failed_save_keeps_previous_version_active(tmp_path, monkeypatch):
    store = FAISSVectorStore(dimension=3, persist_dir=tmp_path)
    store.add_documents(
        [make_document("a:1", "a", 1, [1, 0, 0], "Original")]
    )
    current_version = (tmp_path / FAISSVectorStore.CURRENT_FILENAME).read_text(
        encoding="ascii"
    )

    def fail_write_index(index, path):
        raise OSError("simulated index write failure")

    monkeypatch.setattr("vectorstores.faiss_store.faiss.write_index", fail_write_index)

    with pytest.raises(OSError, match="simulated index write failure"):
        store.add_documents(
            [make_document("a:2", "a", 2, [0, 1, 0], "Uncommitted")]
        )

    assert (tmp_path / FAISSVectorStore.CURRENT_FILENAME).read_text(
        encoding="ascii"
    ) == current_version
    loaded = FAISSVectorStore.load(tmp_path)
    results = loaded.search([1, 0, 0], top_k=5)
    assert [result.text for result in results] == ["Original"]


def test_rejects_wrong_embedding_dimension():
    store = FAISSVectorStore(dimension=3)

    document = make_document(
        "a:1",
        "a",
        1,
        [1, 0],
    )

    with pytest.raises(ValueError, match="dimension"):
        store.add_documents([document])


def test_rejects_duplicate_ids_in_one_batch():
    store = FAISSVectorStore(dimension=3)

    with pytest.raises(ValueError, match="Duplicate"):
        store.add_documents(
            [
                make_document("same", "a", 1, [1, 0, 0]),
                make_document("same", "a", 2, [0, 1, 0]),
            ]
        )


def test_rejects_non_finite_embedding():
    store = FAISSVectorStore(dimension=3)

    with pytest.raises(ValueError, match="finite"):
        store.add_documents(
            [make_document("a:1", "a", 1, [np.nan, 0, 0])]
        )


def test_search_empty_store_returns_no_results():
    store = FAISSVectorStore(dimension=3)

    assert store.search([1, 0, 0], top_k=3) == []
