
"""Build page-level citations from retrieved PDF evidence."""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Citation:
    page_number: int
    excerpt: str
    source: str = "uploaded PDF"

    def __post_init__(self):
        if self.page_number < 1:
            raise ValueError("page_number must be one-based (>= 1)")

        if not self.excerpt.strip():
            raise ValueError("Citation excerpt cannot be empty")

        if not self.source.strip():
            raise ValueError("Citation source cannot be empty")


def build_citations(
    evidence: Iterable[dict],
) -> list[Citation]:
    """Convert retrieved evidence into unique, page-level citations.

    Each evidence dictionary must contain:
        page_number: one-based PDF page number
        text: the supporting text or visual description
        source: optional source label

    Duplicate citations on the same page are deduplicated by page and excerpt.
    """
    citations = []
    seen = set()

    for item in evidence:
        page_number = item.get("page_number")
        text = item.get("text", "")
        source = item.get("source", "uploaded PDF")

        if not isinstance(page_number, int) or isinstance(page_number, bool):
            raise ValueError("page_number must be an integer")

        if page_number < 1:
            raise ValueError("page_number must be >= 1")

        if not isinstance(text, str) or not text.strip():
            continue

        if not isinstance(source, str) or not source.strip():
            raise ValueError("source must be a non-empty string")

        excerpt = text.strip()
        key = (page_number, excerpt, source)

        if key in seen:
            continue

        seen.add(key)
        citations.append(
            Citation(
                page_number=page_number,
                excerpt=excerpt,
                source=source,
            )
        )

    return citations


def format_citations(citations: Iterable[Citation]) -> str:
    """Format citations for display in an answer."""
    lines = []

    for citation in citations:
        lines.append(
            f"[Page {citation.page_number}] "
            f"{citation.excerpt} "
            f"(Source: {citation.source})"
        )

    return "\n".join(lines)


def format_answer_with_citations(
    answer: str,
    citations: Iterable[Citation],
) -> str:
    """Append formatted evidence citations to an answer."""
    answer = answer.strip()

    if not answer:
        raise ValueError("answer cannot be empty")

    citation_text = format_citations(citations)

    if not citation_text:
        return f"{answer}\n\nNo supporting citations were retrieved."

    return f"{answer}\n\nSources:\n{citation_text}"
