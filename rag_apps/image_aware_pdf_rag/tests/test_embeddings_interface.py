
import pytest

from interfaces.embeddings import (
    EmbeddingModel,
    validate_embedding,
    validate_embeddings,
    validate_query,
    validate_texts,
)


class FakeEmbeddingModel:
    """Deterministic mock for testing the embedding contract."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        validate_texts(texts)
        return [[float(len(text)), 0.5] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        validate_query(text)
        return [float(len(text)), 0.5]


def test_fake_provider_implements_interface():
    model = FakeEmbeddingModel()

    assert isinstance(model, EmbeddingModel)


def test_embed_documents_returns_one_vector_per_text():
    model = FakeEmbeddingModel()

    vectors = model.embed_documents(["Revenue grew", "Costs fell"])

    assert len(vectors) == 2
    assert all(len(vector) == 2 for vector in vectors)


def test_embed_query_returns_vector():
    model = FakeEmbeddingModel()

    vector = model.embed_query("What happened to revenue?")

    assert isinstance(vector, list)
    assert len(vector) == 2


def test_rejects_empty_document_list():
    with pytest.raises(ValueError):
        validate_texts([])


@pytest.mark.parametrize("texts", [["valid", ""], ["   "], [None]])
def test_rejects_invalid_document_texts(texts):
    with pytest.raises(ValueError):
        validate_texts(texts)


@pytest.mark.parametrize("query", ["", "   ", None, 123])
def test_rejects_invalid_queries(query):
    with pytest.raises(ValueError):
        validate_query(query)


def test_rejects_empty_embedding():
    with pytest.raises(ValueError):
        validate_embedding([])


def test_rejects_non_numeric_embedding_values():
    with pytest.raises(ValueError):
        validate_embedding([0.1, "invalid"])


def test_rejects_non_finite_values():
    with pytest.raises(ValueError):
        validate_embedding([float("nan")])

    with pytest.raises(ValueError):
        validate_embedding([float("inf")])


def test_validates_embedding_count():
    with pytest.raises(ValueError, match="Expected 2 embeddings"):
        validate_embeddings([[0.1, 0.2]], expected_count=2)


def test_rejects_mismatched_dimensions():
    with pytest.raises(ValueError, match="same dimensions"):
        validate_embeddings(
            [[0.1, 0.2], [0.3, 0.4, 0.5]],
            expected_count=2,
        )


def test_accepts_valid_embeddings():
    validate_embeddings(
        [[0.1, 0.2], [0.3, 0.4]],
        expected_count=2,
    )
