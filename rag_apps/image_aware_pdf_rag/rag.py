from __future__ import annotations

import base64
import logging
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import log, sqrt
from typing import Protocol

import pymupdf

LOGGER = logging.getLogger(__name__)

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 50
MIN_RELATIVE_SCORE = 0.2
DEFAULT_NEBIUS_BASE_URL = "https://api.studio.nebius.com/v1"
DEFAULT_NEBIUS_TIMEOUT_SECONDS = 60.0
_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "which",
        "who",
        "with",
    }
)


class PdfValidationError(ValueError):
    """Raised when an uploaded document cannot be indexed safely."""


class PdfNotIndexedError(RuntimeError):
    """Raised when retrieval is attempted before indexing a document."""


class VisionDescriber(Protocol):
    """Describe visual evidence on one rendered PDF page."""

    def describe(self, image_png: bytes, page_number: int) -> str:
        """Return a concise, retrieval-friendly page description."""


class AnswerGenerator(Protocol):
    """Generate an answer from already-retrieved evidence."""

    def generate(self, question: str, hits: Sequence[SearchHit]) -> str:
        """Return an answer whose factual claims include page citations."""


class NoopVisionDescriber:
    """Text-only fallback used when no multimodal provider is configured."""

    def describe(self, image_png: bytes, page_number: int) -> str:
        return ""


@dataclass(frozen=True)
class PageEvidence:
    """Text, visual context, and preview image for one PDF page."""

    page_number: int
    text: str
    visual_description: str
    image_png: bytes

    @property
    def index_text(self) -> str:
        parts = []
        if self.text:
            parts.append(f"Page text:\n{self.text}")
        if self.visual_description:
            parts.append(f"Visual evidence:\n{self.visual_description}")
        return "\n\n".join(parts)


@dataclass(frozen=True)
class SearchHit:
    """A ranked page returned by local retrieval."""

    evidence: PageEvidence
    score: float
    matched_terms: tuple[str, ...]

    @property
    def page_number(self) -> int:
        return self.evidence.page_number

    @property
    def citation(self) -> str:
        return f"[p. {self.page_number}]"


@dataclass(frozen=True)
class Answer:
    """An answer and the page evidence used to produce it."""

    text: str
    citations: tuple[int, ...]
    hits: tuple[SearchHit, ...]


class NebiusVisionDescriber:
    """Describe page images with a Nebius OpenAI-compatible vision model."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = DEFAULT_NEBIUS_BASE_URL,
        timeout: float = DEFAULT_NEBIUS_TIMEOUT_SECONDS,
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            max_retries=2,
        )
        self._model = model

    def describe(self, image_png: bytes, page_number: int) -> str:
        encoded = base64.b64encode(image_png).decode("ascii")
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Describe the retrieval-relevant visual evidence on this PDF "
                                f"page {page_number}. Transcribe chart labels, values, legends, "
                                "table cells, diagram relationships, and units. Use only visible "
                                "evidence and keep the description under 180 words."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded}"},
                        },
                    ],
                }
            ],
        )
        return (response.choices[0].message.content or "").strip()


class ExtractiveAnswerGenerator:
    """Offline answerer that quotes the best matching page excerpts."""

    def generate(self, question: str, hits: Sequence[SearchHit]) -> str:
        if not hits:
            return "No relevant evidence was found in the indexed pages."

        query_terms = set(_tokenize(question))
        lines = []
        for hit in hits:
            excerpt = _best_excerpt(hit.evidence.index_text, query_terms)
            lines.append(f"- {excerpt} {hit.citation}")
        return "\n".join(lines)


class NebiusAnswerGenerator:
    """Synthesize a grounded answer with a Nebius chat model."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = DEFAULT_NEBIUS_BASE_URL,
        timeout: float = DEFAULT_NEBIUS_TIMEOUT_SECONDS,
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            max_retries=2,
        )
        self._model = model

    def generate(self, question: str, hits: Sequence[SearchHit]) -> str:
        if not hits:
            return "No relevant evidence was found in the indexed pages."

        context = "\n\n".join(f"[p. {hit.page_number}]\n{hit.evidence.index_text}" for hit in hits)
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Answer only from the supplied PDF evidence. Cite every factual claim "
                        "with its page marker in the exact form [p. N]. If the evidence is "
                        "insufficient, say so."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nEvidence:\n{context}",
                },
            ],
        )
        answer = (response.choices[0].message.content or "").strip()
        citation_labels = [hit.citation for hit in hits]
        if answer and not any(label in answer for label in citation_labels):
            answer = f"{answer}\n\nSources: {' '.join(citation_labels)}"
        return answer


class ImageAwarePdfRag:
    """In-memory, page-level PDF RAG pipeline with optional visual parsing."""

    def __init__(
        self,
        vision_describer: VisionDescriber | None = None,
        answer_generator: AnswerGenerator | None = None,
    ) -> None:
        self._vision_describer = vision_describer or NoopVisionDescriber()
        self._answer_generator = answer_generator or ExtractiveAnswerGenerator()
        self._pages: tuple[PageEvidence, ...] = ()
        self._document_vectors: tuple[dict[str, float], ...] = ()
        self._page_terms: tuple[frozenset[str], ...] = ()
        self._idf: dict[str, float] = {}
        self._unknown_idf = 1.0

    @property
    def pages(self) -> tuple[PageEvidence, ...]:
        return self._pages

    def index_pdf(
        self,
        pdf_bytes: bytes,
        visual_descriptions: Mapping[int, str] | None = None,
    ) -> tuple[PageEvidence, ...]:
        """Validate, render, describe, and index a PDF by page."""
        if not pdf_bytes:
            raise PdfValidationError("The uploaded PDF is empty.")
        if len(pdf_bytes) > MAX_PDF_BYTES:
            raise PdfValidationError("The PDF exceeds the 20 MB demo limit.")

        try:
            document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise PdfValidationError("The uploaded file is not a readable PDF.") from exc

        try:
            if document.needs_pass:
                raise PdfValidationError("Password-protected PDFs are not supported.")
            if document.page_count == 0:
                raise PdfValidationError("The PDF does not contain any pages.")
            if document.page_count > MAX_PDF_PAGES:
                raise PdfValidationError("The PDF exceeds the 50-page demo limit.")

            pages = []
            descriptions = _normalize_visual_descriptions(visual_descriptions or {})
            for page_index, page in enumerate(document, start=1):
                image_png = page.get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4), alpha=False).tobytes(
                    "png"
                )
                visual_description = descriptions.get(page_index, "").strip()
                if not visual_description:
                    try:
                        visual_description = (
                            self._vision_describer.describe(image_png, page_index) or ""
                        ).strip()
                    except Exception:
                        LOGGER.warning(
                            "Vision description failed for page %s; keeping text evidence only.",
                            page_index,
                            exc_info=True,
                        )
                        visual_description = ""
                pages.append(
                    PageEvidence(
                        page_number=page_index,
                        text=(page.get_text("text") or "").strip(),
                        visual_description=visual_description,
                        image_png=image_png,
                    )
                )
        finally:
            document.close()

        if not any(_tokenize(page.index_text) for page in pages):
            raise PdfValidationError(
                "The PDF has no extractable text or visual descriptions. "
                "Enable a vision provider for scanned documents."
            )

        self._pages = tuple(pages)
        self._build_index()
        return self._pages

    def search(self, question: str, top_k: int = 3) -> tuple[SearchHit, ...]:
        """Rank pages using a compact local TF-IDF cosine index."""
        if not self._pages:
            raise PdfNotIndexedError("Index a PDF before asking a question.")
        if not question.strip():
            raise ValueError("Question must not be empty.")
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        question_tokens = _tokenize(question)
        query_vector = _tf_idf_vector(question_tokens, self._idf, self._unknown_idf)
        hits = []
        for page, document_vector, page_terms in zip(
            self._pages, self._document_vectors, self._page_terms, strict=True
        ):
            score = _cosine(query_vector, document_vector)
            if score <= 0:
                continue
            hits.append(
                SearchHit(
                    evidence=page,
                    score=score,
                    matched_terms=tuple(sorted(set(question_tokens) & page_terms)),
                )
            )

        hits.sort(key=lambda hit: (-hit.score, hit.page_number))
        if not hits:
            return ()

        score_floor = hits[0].score * MIN_RELATIVE_SCORE
        return tuple(hit for hit in hits if hit.score >= score_floor)[:top_k]

    def ask(self, question: str, top_k: int = 3) -> Answer:
        """Retrieve evidence and generate an answer with page citations."""
        hits = self.search(question, top_k=top_k)
        text = self._answer_generator.generate(question, hits)
        citations = tuple(dict.fromkeys(hit.page_number for hit in hits))
        return Answer(text=text, citations=citations, hits=hits)

    def _build_index(self) -> None:
        tokenized_pages = [_tokenize(page.index_text) for page in self._pages]
        document_frequency: Counter[str] = Counter()
        for tokens in tokenized_pages:
            document_frequency.update(set(tokens))

        document_count = len(tokenized_pages)
        self._idf = {
            token: log((document_count + 1) / (frequency + 1)) + 1
            for token, frequency in document_frequency.items()
        }
        self._unknown_idf = log(document_count + 1) + 1
        self._page_terms = tuple(frozenset(tokens) for tokens in tokenized_pages)
        self._document_vectors = tuple(
            _tf_idf_vector(tokens, self._idf, self._unknown_idf) for tokens in tokenized_pages
        )


def _tokenize(text: str) -> list[str]:
    return [
        normalized
        for token in _TOKEN_PATTERN.findall(text)
        if (normalized := token.casefold()) not in _STOP_WORDS
    ]


def _normalize_visual_descriptions(
    descriptions: Mapping[int | str, str],
) -> dict[int, str]:
    """Normalize JSON-loaded page keys before indexing visual evidence."""
    normalized: dict[int, str] = {}
    for raw_page_number, description in descriptions.items():
        try:
            page_number = int(raw_page_number)
        except (TypeError, ValueError) as exc:
            raise PdfValidationError("Visual description page numbers must be integers.") from exc
        if page_number < 1:
            raise PdfValidationError("Visual description page numbers must be positive.")
        if not isinstance(description, str):
            raise PdfValidationError("Visual descriptions must be strings.")
        normalized[page_number] = description
    return normalized


def _tf_idf_vector(
    tokens: Sequence[str], idf: Mapping[str, float], unknown_idf: float
) -> dict[str, float]:
    counts = Counter(tokens)
    weights = {
        token: (1 + log(count)) * idf.get(token, unknown_idf) for token, count in counts.items()
    }
    magnitude = sqrt(sum(weight * weight for weight in weights.values()))
    if magnitude == 0:
        return {}
    return {token: weight / magnitude for token, weight in weights.items()}


def _cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(weight * right.get(token, 0.0) for token, weight in left.items())


def _best_excerpt(text: str, query_terms: set[str], limit: int = 360) -> str:
    segments = [
        segment.strip()
        for segment in re.split(r"(?<=[.!?])\s+|\n+", text)
        if segment.strip() and not segment.endswith(":")
    ]
    if not segments:
        return "Relevant page evidence"

    ranked = sorted(
        (
            (len(query_terms & set(_tokenize(segment))), index, segment)
            for index, segment in enumerate(segments)
        ),
        key=lambda item: (-item[0], -min(len(item[2]), limit), item[1]),
    )
    relevant = []
    covered_terms: set[str] = set()
    for item in ranked:
        matched_terms = query_terms & set(_tokenize(item[2]))
        if not matched_terms or matched_terms <= covered_terms:
            continue
        relevant.append(item)
        covered_terms.update(matched_terms)
        if len(relevant) == 2:
            break

    relevant.sort(key=lambda item: item[1])
    excerpt = " ".join(item[2] for item in relevant) if relevant else segments[0]
    return excerpt if len(excerpt) <= limit else f"{excerpt[: limit - 3].rstrip()}..."
