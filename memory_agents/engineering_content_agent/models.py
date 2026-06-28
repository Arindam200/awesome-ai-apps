"""Plain Python data contracts for the Developer Trend & DevRel Ideation Agent."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


def _split_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _score(value: object) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 0
    return max(0, min(100, number))


class Serializable:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class CompanyContext(Serializable):
    company_name: str = ""
    product: str = ""
    audience: str = ""
    seed_keywords: list[str] = field(default_factory=list)
    competitors: list[str] = field(default_factory=list)
    existing_topics: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.company_name = self.company_name.strip()
        self.product = self.product.strip()
        self.audience = self.audience.strip()
        self.seed_keywords = _split_list(self.seed_keywords)
        self.competitors = _split_list(self.competitors)
        self.existing_topics = _split_list(self.existing_topics)


@dataclass
class SearchQueryPlan(Serializable):
    rationale: str
    hn_queries: list[str] = field(default_factory=list)
    dev_queries: list[str] = field(default_factory=list)
    dev_tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.hn_queries = _split_list(self.hn_queries)
        self.dev_queries = _split_list(self.dev_queries)
        self.dev_tags = _split_list(self.dev_tags)


@dataclass
class HNItem(Serializable):
    title: str
    url: str
    source_type: str
    author: str | None = None
    points: int | None = None
    num_comments: int | None = None
    created_at: str | None = None
    text: str | None = None


@dataclass
class HNDeveloperSignal(Serializable):
    topic: str
    pain_point: str
    developer_question: str
    evidence_summary: str
    intensity_score: int
    source_urls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.intensity_score = _score(self.intensity_score)
        self.source_urls = _split_list(self.source_urls)


@dataclass
class DEVArticle(Serializable):
    title: str
    url: str
    id: int | None = None
    path: str | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)
    published_at: str | None = None
    positive_reactions_count: int | None = None
    comments_count: int | None = None
    description: str | None = None
    body_excerpt: str | None = None

    def __post_init__(self) -> None:
        self.tags = _split_list(self.tags)


@dataclass
class DEVSupplySignal(Serializable):
    topic: str
    supply_quality_score: int
    common_angles: list[str] = field(default_factory=list)
    saturated_angles: list[str] = field(default_factory=list)
    missing_angles: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.common_angles = _split_list(self.common_angles)
        self.saturated_angles = _split_list(self.saturated_angles)
        self.missing_angles = _split_list(self.missing_angles)
        self.source_urls = _split_list(self.source_urls)
        self.supply_quality_score = _score(self.supply_quality_score)


@dataclass
class ContentGap(Serializable):
    topic: str
    demand_score: int
    supply_gap_score: int
    memory_novelty_score: int
    total_score: int
    why_it_matters: str
    supply_gap: str
    recommended_asset_type: str
    business_intent_score: int = 50
    search_intent: str = "implementation"
    demand_evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.demand_score = _score(self.demand_score)
        self.supply_gap_score = _score(self.supply_gap_score)
        self.memory_novelty_score = _score(self.memory_novelty_score)
        self.business_intent_score = _score(self.business_intent_score)
        self.total_score = _score(self.total_score)
        self.demand_evidence = _split_list(self.demand_evidence)


@dataclass
class TrendDigestItem(Serializable):
    topic: str
    why_trending: str
    intensity_score: int
    dev_saturation: str
    hn_links: list[str] = field(default_factory=list)
    dev_links: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.intensity_score = _score(self.intensity_score)
        self.hn_links = _split_list(self.hn_links)
        self.dev_links = _split_list(self.dev_links)


@dataclass
class ContentIdea(Serializable):
    title: str
    format: str
    angle: str
    outline: list[str]
    score: int
    confidence: str
    hn_evidence: list[str] = field(default_factory=list)
    dev_gap: str = ""
    dev_links: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.score = _score(self.score)
        self.format = self.format.strip()
        self.hn_evidence = _split_list(self.hn_evidence)
        self.dev_links = _split_list(self.dev_links)
        self.outline = _split_list(self.outline)


@dataclass
class IdeationReport(Serializable):
    company: str
    summary: str
    trend_digest: list[TrendDigestItem] = field(default_factory=list)
    content_ideas: list[ContentIdea] = field(default_factory=list)
    memory_notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.trend_digest = [
            item
            if isinstance(item, TrendDigestItem)
            else TrendDigestItem(**item)
            for item in self.trend_digest
            if isinstance(item, TrendDigestItem) or isinstance(item, dict)
        ]
        self.content_ideas = [
            idea
            if isinstance(idea, ContentIdea)
            else ContentIdea(**idea)
            for idea in self.content_ideas
            if isinstance(idea, ContentIdea) or isinstance(idea, dict)
        ]
        self.memory_notes = _split_list(self.memory_notes)


@dataclass
class AgentRunResult(Serializable):
    context: CompanyContext
    query_plan: SearchQueryPlan
    hn_items: list[HNItem]
    dev_articles: list[DEVArticle]
    hn_signals: list[HNDeveloperSignal]
    dev_signals: list[DEVSupplySignal]
    content_gaps: list[ContentGap]
    report: IdeationReport
    markdown: str
    memory_notes: list[str] = field(default_factory=list)
    team_member_responses: list[str] = field(default_factory=list)
    judge_score: float | None = None
    judge_notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.memory_notes = _split_list(self.memory_notes)
        self.team_member_responses = _split_list(self.team_member_responses)
        self.judge_notes = _split_list(self.judge_notes)
        if isinstance(self.report, dict):
            self.report = IdeationReport(**self.report)
        elif not isinstance(self.report, IdeationReport):
            raise TypeError("AgentRunResult.report must be an IdeationReport.")
