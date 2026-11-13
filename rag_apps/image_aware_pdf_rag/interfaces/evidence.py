"""Shared evidence types used by retrieval and answer orchestration."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedEvidence:
    """Evidence retrieved from a PDF, with its original page number."""

    page_number: int
    text: str
    source: str = "uploaded PDF"
    content_type: str = "text"
