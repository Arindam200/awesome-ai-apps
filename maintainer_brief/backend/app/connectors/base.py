from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawItem:
    """A single raw event from an API source, before normalization."""

    source_kind: str  # github|hackernews|reddit|osv
    source_url: str
    title: str
    body: str = ""
    author: str | None = None
    observed_at: datetime | None = None
    extra: dict = field(default_factory=dict)
