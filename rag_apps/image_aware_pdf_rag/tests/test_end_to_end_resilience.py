"""Integration and resilience tests for end-to-end multimodal PDF RAG indexing and answering."""

import pymupdf
import pytest

from chunking import chunk_pages
from ingestion import PDFIngestionError, ingest_pdf
from interfaces.vector_store import VectorDocument
from interfaces.vision import VisionResult
from pipeline import AnswerOrchestrator
from retrieval.retriever import PDFRetriever
from vectorstores.faiss_store import FAISSVectorStore
from vision import describe_pdf_pages


def make_multipage_pdf(page_count: int = 3) -> bytes:
    """Create a test PDF with text and drawing on each page."""
    doc = pymupdf.open()
    for i in range(1, page_count + 1):
        page = doc.new_page(width=400, height=400)
        page.insert_text((50, 50), f"Section {i}: Content for page {i}")
        page.draw_rect(pymupdf.Rect(50, 100, 200, 250), color=(0, 0, 1), fill=(0.9, 0.9, 1))
    data = doc.tobytes()
    doc.close()
    return data


class FakeEmbedder:
    def __init__(self, dimension: int = 8):
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            val = float(len(text) % 10 + 1) / 10.0
            vec = [val] * self.dimension
            results.append(vec)
        return results

    def embed_query(self, text: str) -> list[float]:
        val = float(len(text) % 10 + 1) / 10.0
        return [val] * self.dimension


class ControlledVisionModel:
    """Mock vision model that can selectively fail on specific pages."""

    def __init__(self, fail_pages: set[int] | None = None, fail_reason: str = "length"):
        self.fail_pages = fail_pages or set()
        self.fail_reason = fail_reason
        self.processed_pages: list[int] = []

    def describe_page(self, image_png: bytes, page_number: int) -> VisionResult:
        self.processed_pages.append(page_number)
        if page_number in self.fail_pages:
            if self.fail_reason == "length":
                raise RuntimeError(
                    f"Groq returned an incomplete page description (completion token limit reached) on page {page_number}"
                )
            elif self.fail_reason == "rate_limit":
                raise RuntimeError(
                    f"Groq rate limit exceeded (HTTP 429) while processing page {page_number}"
                )
            elif self.fail_reason == "empty":
                raise RuntimeError(
                    f"Groq returned an empty page description for page {page_number}"
                )
            else:
                raise RuntimeError(f"Vision failed on page {page_number}: unexpected error")

        return VisionResult(
            page_number=page_number,
            description=f"Visual architecture diagram on page {page_number} with components and flows.",
        )


class FakeChat:
    def __init__(self, answer: str = "Verified answer referencing the document"):
        self.answer = answer
        self.last_messages = None

    def generate(self, messages):
        self.last_messages = messages
        return self.answer


def test_all_pages_considered_and_indexed():
    """Verify that every page of a multi-page PDF is processed and indexed."""
    pdf_bytes = make_multipage_pdf(page_count=3)
    pages = ingest_pdf(pdf_bytes)
    assert len(pages) == 3

    chunk_result = chunk_pages(pages)
    chunks = chunk_result.chunks
    assert len(chunks) == 3
    assert {c.page_number for c in chunks} == {1, 2, 3}

    embedder = FakeEmbedder()
    store = FAISSVectorStore()
    source_id = "test_doc_all"

    # Index text
    for i, chunk in enumerate(chunks):
        vec = embedder.embed_documents([chunk.text])[0]
        store.add_documents([
            VectorDocument(
                id=f"{source_id}:text:{i}",
                text=chunk.text,
                embedding=vec,
                metadata={
                    "page_number": chunk.page_number,
                    "content_type": "text",
                    "source_id": source_id,
                },
            )
        ])

    # Describe visuals for all pages
    vision = ControlledVisionModel()
    for page in pages:
        res = vision.describe_page(page.image_png, page.page_number)
        vec = embedder.embed_documents([res.description])[0]
        store.add_documents([
            VectorDocument(
                id=f"{source_id}:visual:{res.page_number}",
                text=res.description,
                embedding=vec,
                metadata={
                    "page_number": res.page_number,
                    "content_type": "visual_description",
                    "source_id": source_id,
                },
            )
        ])

    assert vision.processed_pages == [1, 2, 3]

    retriever = PDFRetriever(embedder, store)
    results = retriever.retrieve("diagram", top_k=10, source_id=source_id)
    retrieved_pages = {item.page_number for item in results}
    assert {1, 2, 3}.issubset(retrieved_pages)


def test_one_page_vision_failure_does_not_stop_subsequent_pages():
    """Verify that failure on page 2 does not stop page 1 or page 3 from indexing."""
    pdf_bytes = make_multipage_pdf(page_count=3)
    pages = ingest_pdf(pdf_bytes)
    vision = ControlledVisionModel(fail_pages={2})

    batch = describe_pdf_pages(pages, vision)

    assert vision.processed_pages == [1, 2, 3]
    assert set(batch.failures) == {2}
    assert "incomplete page description" in batch.failures[2]
    assert [d.page_number for d in batch.descriptions] == [1, 3]


def test_text_indexing_continues_when_all_vision_fails():
    """Verify that when vision fails completely, text indexing is intact and searchable."""
    pdf_bytes = make_multipage_pdf(page_count=2)
    pages = ingest_pdf(pdf_bytes)
    chunk_result = chunk_pages(pages)
    chunks = chunk_result.chunks

    embedder = FakeEmbedder()
    store = FAISSVectorStore()
    source_id = "text_fallback_doc"

    # Index text
    for i, chunk in enumerate(chunks):
        vec = embedder.embed_documents([chunk.text])[0]
        store.add_documents([
            VectorDocument(
                id=f"{source_id}:text:{i}",
                text=chunk.text,
                embedding=vec,
                metadata={
                    "page_number": chunk.page_number,
                    "content_type": "text",
                    "source_id": source_id,
                },
            )
        ])

    # Simulate all vision failing
    vision = ControlledVisionModel(fail_pages={1, 2}, fail_reason="rate_limit")
    failed_visuals = []
    for page in pages:
        try:
            vision.describe_page(page.image_png, page.page_number)
        except Exception:
            failed_visuals.append(page.page_number)

    assert failed_visuals == [1, 2]

    retriever = PDFRetriever(embedder, store)
    results = retriever.retrieve("Content for page 1", top_k=5, source_id=source_id)
    assert len(results) > 0
    assert results[0].page_number in {1, 2}
    assert results[0].content_type == "text"


def test_correct_page_number_metadata_and_citations():
    """Verify that retrieved text and visual evidence have correct page numbers and generate citations."""
    pdf_bytes = make_multipage_pdf(page_count=2)
    ingest_pdf(pdf_bytes)

    embedder = FakeEmbedder()
    store = FAISSVectorStore()
    source_id = "citation_doc"

    t_vec = embedder.embed_documents(["Specific text claim on page 1"])[0]
    store.add_documents([
        VectorDocument(
            id=f"{source_id}:text:0",
            text="Specific text claim on page 1",
            embedding=t_vec,
            metadata={"page_number": 1, "content_type": "text", "source_id": source_id, "source": "test.pdf"},
        )
    ])

    v_vec = embedder.embed_documents(["Chart showing 45% revenue on page 2"])[0]
    store.add_documents([
        VectorDocument(
            id=f"{source_id}:visual:1",
            text="Chart showing 45% revenue on page 2",
            embedding=v_vec,
            metadata={"page_number": 2, "content_type": "visual_description", "source_id": source_id, "source": "test.pdf"},
        )
    ])

    retriever = PDFRetriever(embedder, store)
    evidence = retriever.retrieve("revenue", top_k=5, source_id=source_id)
    assert len(evidence) == 2
    page_numbers = {e.page_number for e in evidence}
    assert page_numbers == {1, 2}

    orchestrator = AnswerOrchestrator(retriever, FakeChat("Revenue is 45% according to page 2."))
    result = orchestrator.answer_question("What is the revenue?")
    assert len(result.citations) >= 1
    citation_pages = {c.page_number for c in result.citations}
    assert citation_pages == {1, 2}


def test_empty_or_invalid_pdf_handling():
    """Verify that empty or invalid PDF input is rejected with clear exception."""
    with pytest.raises(ValueError):
        ingest_pdf(b"")

    with pytest.raises(PDFIngestionError):
        ingest_pdf(b"Not a valid PDF header content")


def test_query_for_chart_1_1_selects_page_1_over_page_2():
    """Regression test: Query for Chart 1.1 must select Page 1 evidence over Page 2 Chart 1.2."""
    store = FAISSVectorStore()
    source_id = "reproduction_doc"

    # Simulated embedding dimension = 4
    # Suppose both pages have similar vector representations for general economic/chart terms
    vec_general = [0.5, 0.5, 0.5, 0.5]
    vec_slightly_closer_to_p2 = [0.52, 0.52, 0.52, 0.52]

    # Page 1: Chart 1.1: GDP growth projection with orange line labelled "ONS data" and shaded fan bands
    page1_text = (
        "Visual description of page 1: Chart 1.1: GDP growth projections and uncertainty. "
        "The orange line is labelled 'ONS data'. Shaded fan bands to its right represent uncertainty around projected GDP growth."
    )
    # Page 2: Chart 1.2: Historical comparison where orange line indicates 1990
    page2_text = (
        "Visual description of page 2: Chart 1.2: Historical inflation and output from 1990 to 2010. "
        "The orange line is labelled '1990'. The blue line shows baseline."
    )

    store.add_documents([
        VectorDocument(
            id=f"{source_id}:visual:1",
            text=page1_text,
            embedding=vec_general,
            metadata={"page_number": 1, "content_type": "visual_description", "source_id": source_id, "source": "report.pdf"},
        ),
        VectorDocument(
            id=f"{source_id}:visual:2",
            text=page2_text,
            embedding=vec_slightly_closer_to_p2,
            metadata={"page_number": 2, "content_type": "visual_description", "source_id": source_id, "source": "report.pdf"},
        ),
    ])

    class ConstantEmbedder:
        def embed_query(self, text: str) -> list[float]:
            # Query embedding is slightly closer to vec_slightly_closer_to_p2 by pure cosine/dot product
            return [0.5, 0.5, 0.5, 0.5]

    retriever = PDFRetriever(ConstantEmbedder(), store)
    query = "What is the label of the orange line in Chart 1.1, and what do the shaded bands to its right represent?"
    evidence = retriever.retrieve(query=query, top_k=2, source_id=source_id)

    # 1. Top evidence MUST be from Page 1 (Chart 1.1), not Page 2 (Chart 1.2)
    assert len(evidence) >= 1
    assert evidence[0].page_number == 1
    assert "Chart 1.1" in evidence[0].text
    assert "ONS data" in evidence[0].text

    # 2. Verify answer orchestration correctly passes page 1 evidence to chat model
    class VerifyingChat:
        def generate(self, messages):
            user_msg = messages[-1]["content"]
            assert "Chart 1.1" in user_msg
            assert "ONS data" in user_msg
            return "The orange line in Chart 1.1 is labelled 'ONS data', and the shaded fan bands represent uncertainty around projected GDP growth. [Page 1]"

    orchestrator = AnswerOrchestrator(retriever, VerifyingChat())
    res = orchestrator.answer_question(query)
    assert "ONS data" in res.answer
    assert any(c.page_number == 1 for c in res.citations)
