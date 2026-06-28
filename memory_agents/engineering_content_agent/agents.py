"""Agno specialist agents and report guardrails."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from agno.agent import Agent

from engram_memory import MemoryRecord
from llm import build_model, make_agent, parse_json_object, run_agent
from models import (
    CompanyContext,
    ContentGap,
    ContentIdea,
    DEVArticle,
    DEVSupplySignal,
    HNDeveloperSignal,
    HNItem,
    IdeationReport,
    SearchQueryPlan,
    TrendDigestItem,
    AgentRunResult,
)
from config import Settings
from engram_memory import MemoryStore
from sources import search_dev_articles, search_hn

logger = logging.getLogger(__name__)


StageCallback = Callable[[str], Awaitable[None] | None]


def _preview_items(items: list[str], limit: int = 3) -> str:
    cleaned = [item.strip() for item in items if item.strip()]
    if not cleaned:
        return "general signals"
    preview = ", ".join(cleaned[:limit])
    if len(cleaned) > limit:
        preview += f" (+{len(cleaned) - limit} more)"
    return preview


async def _notify(callback: StageCallback | None, message: str) -> None:
    if not callback:
        return
    result = callback(message)
    if asyncio.iscoroutine(result):
        await result


QUERY_PLANNER_PROMPT = """
You are the Developer Trend & DevRel Ideation Agent query planner.
Create search queries that reveal real developer demand on Hacker News and current article supply on DEV.to.
Prefer high-intent implementation, debugging, migration, comparison, architecture, integration, tutorial, and production-readiness phrases.
For DEV.to, include both specific article queries and broader public tags likely to return recent articles; avoid over-narrow quoted phrases.
Return concise query lists and tags. Avoid broad tags like programming unless no better tag exists.
Return only JSON with keys: hn_queries, dev_queries, dev_tags, rationale.
"""


IDEATION_WRITER_PROMPT = """
You write DevRel talk and blog ideation for developer-tool companies.
Do not write full articles. Produce a trend digest plus ranked talk/blog/tutorial ideas with synthesized titles (not raw HN headlines).
Every idea needs HN evidence links, DEV supply gap notes, angle, outline bullets, and confidence.
The user may provide any developer product. Classify the product/category from the prompt and evidence yourself; do not assume a fixed taxonomy.
Choose DEV links per idea only when the article title, tags, description, or body excerpt actually matches that idea.
If DEV coverage is weak or unrelated, leave dev_links empty and explain the supply gap instead of reusing generic links.
Return only valid JSON matching the report shape: company, summary, trend_digest, content_ideas, memory_notes.
Use short strings. Avoid quotation marks inside text values; use apostrophes or parentheses instead.
Do not include markdown, comments, trailing commas, or prose outside the JSON object.
"""


JSON_REPAIR_PROMPT = """
You repair malformed JSON from a report-writing agent.
Return only one valid JSON object. Preserve the report content as much as possible.
Do not add commentary, markdown fences, comments, or trailing commas.
If a string contains unescaped quotation marks, replace the inner quotation marks with apostrophes.
The JSON object must use keys: company, summary, trend_digest, content_ideas, memory_notes.
"""


def _coerce_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


async def plan_queries_with_llm(context: CompanyContext, settings: Settings) -> SearchQueryPlan:
    """Ask the model to decide source searches from the active user context."""
    model = build_model(settings)
    agent = make_agent(model, QUERY_PLANNER_PROMPT, "query_planner")
    request = {
        "context": context.to_dict(),
        "requirements": [
            "Choose Hacker News queries for developer demand.",
            "Choose DEV.to article queries and tags for supply/saturation checks.",
            "Use the company, product/category, audience, and seed keywords from context.",
            "Return only source-search planning JSON; do not write the report.",
        ],
    }
    payload = parse_json_object(await run_agent(agent, json.dumps(request, ensure_ascii=False)))
    plan = SearchQueryPlan(
        rationale=str(payload.get("rationale") or "LLM-selected source search plan."),
        hn_queries=payload.get("hn_queries", []),
        dev_queries=payload.get("dev_queries", []),
        dev_tags=payload.get("dev_tags", []),
    )
    if not plan.hn_queries:
        raise RuntimeError("The LLM query planner did not choose Hacker News queries.")
    if not plan.dev_queries and not plan.dev_tags:
        raise RuntimeError("The LLM query planner did not choose DEV.to queries or tags.")
    return plan


def memory_user_id(context: CompanyContext) -> str:
    slug = "".join(
        char.lower() if char.isalnum() else "-"
        for char in context.company_name.strip()
    ).strip("-")
    return slug or "engineering-content-agent"


def fallback_hn_signals(items: list[HNItem]) -> list[HNDeveloperSignal]:
    signals: list[HNDeveloperSignal] = []
    signal_by_topic: dict[str, HNDeveloperSignal] = {}
    for item in items[:16]:
        title = item.title.strip()
        text = (item.text or title).strip()
        topic = _topic_from_hn_item(item)
        if not topic:
            continue
        score = min(100, max(25, (item.points or 0) // 2 + (item.num_comments or 0)))
        existing = signal_by_topic.get(topic.lower())
        if existing is not None:
            existing.intensity_score = max(existing.intensity_score, score)
            if item.url not in existing.source_urls:
                existing.source_urls.append(item.url)
            continue
        signal = HNDeveloperSignal(
            topic=topic,
            pain_point=text[:220],
            developer_question=f"What should developers know about {topic[:80]}?",
            evidence_summary=(
                f"HN {item.source_type} discusses {topic} with "
                f"{item.points or 0} points and {item.num_comments or 0} comments."
            ),
            intensity_score=score,
            source_urls=[item.url],
        )
        signal_by_topic[topic.lower()] = signal
        signals.append(signal)
        if len(signals) >= 8:
            break
    return signals


def _topic_from_hn_item(item: HNItem) -> str | None:
    haystack = f"{item.title} {item.text or ''}".lower()
    topic_rules = [
        (
            ("core web vitals", "pagespeed", "page speed", "lcp", "inp", "cls", "webperf"),
            "Core Web Vitals debugging and performance monitoring",
        ),
        (
            ("real-user monitoring", "rum", "user monitoring", "browser monitoring", "session replay"),
            "Real-user monitoring for production web apps",
        ),
        (
            ("api latency", "slow api", "gateway", "packet", "request latency", "timeout"),
            "Debugging API latency from user sessions",
        ),
        (
            ("network debugging", "network latency", "networking", "isp", "packet loss", "gateway"),
            "Network debugging for frontend and backend teams",
        ),
        (
            ("error rate", "error rates", "crash", "exception", "incident", "outage"),
            "Production error-rate monitoring and incident debugging",
        ),
        (
            ("web analytics", "post analytics", "custom events", "utm", "conversion", "funnel"),
            "Developer-friendly web analytics and event tracking",
        ),
        (
            ("observability", "monitoring", "tracing", "logs", "metrics"),
            "Observability workflows for developer teams",
        ),
    ]
    for needles, topic in topic_rules:
        if any(needle in haystack for needle in needles):
            return topic
    return _synth_topic_from_text(item.title, item.text or "")


def _clean_topic_fragment(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"https?://\\S+", " ", cleaned)
    cleaned = re.sub(r"[^a-zA-Z0-9+.#/ -]+", " ", cleaned)
    words = [
        word.strip(" -_/")
        for word in cleaned.split()
        if word.strip(" -_/") and word.lower().strip(" -_/") not in TOPIC_STOPWORDS
    ]
    fragment = " ".join(words[:8]).strip()
    return fragment[:90].strip()


def _synth_topic_from_text(title: str, text: str = "") -> str | None:
    fragment = _clean_topic_fragment(title)
    if not fragment:
        fragment = _clean_topic_fragment(text)
    if not fragment:
        return None
    lowered = f"{title} {text}".lower()
    if any(term in lowered for term in ("debug", "latency", "slow", "error", "failure", "incident")):
        return f"Debugging {fragment}"
    if any(term in lowered for term in ("migrate", "migration", "upgrade")):
        return f"Migration lessons for {fragment}"
    if any(term in lowered for term in ("architecture", "design", "scale", "scaling")):
        return f"Architecture tradeoffs for {fragment}"
    if any(term in lowered for term in ("benchmark", "cost", "performance", "throughput", "evaluation")):
        return f"Evaluating {fragment}"
    return fragment


def fallback_dev_signals(articles: list[DEVArticle], product: str) -> list[DEVSupplySignal]:
    if not articles:
        return [
            DEVSupplySignal(
                topic=product,
                common_angles=[],
                saturated_angles=["Introductory overviews without implementation evidence"],
                missing_angles=["Production architecture", "debugging workflows", "comparison criteria"],
                supply_quality_score=25,
                source_urls=[],
            )
        ]

    grouped = articles[:10]
    common = [article.title for article in grouped[:5]]
    urls = [article.url for article in grouped if article.url][:5]
    return [
        DEVSupplySignal(
            topic=product,
            common_angles=common,
            saturated_angles=[
                "Beginner tutorials",
                "High-level explainers",
                "Tool announcements without tradeoffs",
            ],
            missing_angles=[
                "Operational debugging details",
                "Architecture tradeoffs",
                "Evaluation criteria and failure modes",
            ],
            supply_quality_score=min(
                100,
                35 + sum(article.positive_reactions_count or 0 for article in grouped) // 20,
            ),
            source_urls=urls,
        )
    ]


def memory_novelty_score(topic: str, memories: list[MemoryRecord]) -> int:
    topic_terms = {term for term in topic.lower().split() if len(term) > 3}
    if not topic_terms or not memories:
        return 100
    best_overlap = 0
    for memory in memories:
        memory_terms = set(memory.content.lower().split())
        best_overlap = max(best_overlap, len(topic_terms & memory_terms))
    return max(20, 100 - best_overlap * 18)


def _bounded_score(value: int | float) -> int:
    return max(0, min(100, round(value)))


def _asset_type_for_topic(topic: str) -> str:
    lowered = topic.lower()
    if any(term in lowered for term in ("conference", "keynote", "meetup", "talk", "panel")):
        return "talk"
    if any(term in lowered for term in (" vs ", "versus", "alternative", "compare", "comparison", "architecture", "architect", "design", "coordination", "system")):
        return "blog"
    if any(term in lowered for term in ("debug", "error", "failure", "fix", "troubleshoot", "migrate", "migration", "upgrade", "integrate", "integration", "api", "webhook", "sdk", "tutorial", "how to", "build", "implement", "example")):
        return "tutorial"
    if any(term in lowered for term in ("landing", "pain", "problem", "evaluate")):
        return "blog"
    return "blog"


def _search_intent_for_asset(asset_type: str) -> str:
    if asset_type == "talk":
        return "conference narrative"
    if asset_type == "tutorial":
        return "implementation"
    return "technical research"


def _business_intent_score(topic: str, asset_type: str) -> int:
    lowered = f"{topic} {asset_type}".lower()
    score = 55
    if any(term in lowered for term in ("vs", "versus", "alternative", "compare", "pricing", "evaluate")):
        score += 25
    if any(term in lowered for term in ("debug", "error", "failure", "migrate", "integration", "production")):
        score += 15
    if any(term in lowered for term in ("tutorial", "guide", "article")):
        score += 5
    return _bounded_score(score)


_ASSET_PREFIX = {
    "tutorial": "How to",
    "blog": "Understanding",
    "talk": "Talk:",
}


def _brief_page_title(topic: str, asset_type: str) -> str:
    normalized = " ".join(topic.split())
    lowered = normalized.lower()
    if lowered == "production vector search with postgres and pgvector":
        return "How to run production vector search with Postgres and pgvector"
    if lowered == "debugging rag retrieval quality and relevance":
        return "How to debug RAG retrieval quality and relevance"
    if lowered == "indexing and embedding performance for vector search":
        return "How to tune indexing and embedding performance for vector search"
    if lowered == "hybrid search and reranking architecture":
        return "How to design hybrid search and reranking architecture"
    if lowered == "debugging vector query latency in production":
        return "How to debug vector query latency in production"
    if lowered == "speculative decoding and draft-model evaluation for llm serving":
        return "How to evaluate draft models for speculative decoding"
    if lowered == "production llm serving latency and throughput tuning":
        return "How to tune latency and throughput for production LLM serving"
    if lowered == "batching and kv-cache tuning for production inference":
        return "How to tune batching and KV cache for production inference"
    if lowered == "inference cost and throughput benchmarking":
        return "How to benchmark inference cost and throughput"
    if lowered == "production deployment and evaluation for faster llm serving":
        return "Production deployment checklist for faster LLM serving"
    if lowered == "migration playbooks for production ai retrieval systems":
        return "Migration playbooks for production AI retrieval systems"
    if lowered == "production debugging for ai retrieval systems":
        return "Production debugging for AI retrieval systems"
    if lowered == "production error-rate monitoring and incident debugging":
        return "How to monitor production error rates and debug incidents"
    if lowered == "core web vitals debugging and performance monitoring":
        return "How to debug Core Web Vitals with production monitoring"
    if lowered == "debugging api latency from user sessions":
        return "How to debug API latency from user sessions"
    if lowered == "network debugging for frontend and backend teams":
        return "How frontend and backend teams debug network issues"
    if lowered == "real-user monitoring for production web apps":
        return "How to use real-user monitoring in production web apps"
    if lowered == "developer-friendly web analytics and event tracking":
        return "Developer-friendly web analytics and event tracking"
    if lowered == "observability workflows for developer teams":
        return "Understanding observability workflows for developer teams"

    if asset_type == "tutorial":
        gerund_rewrites = {
            "debugging ": "debug ",
            "monitoring ": "monitor ",
            "building ": "build ",
            "using ": "use ",
            "implementing ": "implement ",
            "integrating ": "integrate ",
        }
        for prefix, replacement in gerund_rewrites.items():
            if lowered.startswith(prefix):
                return f"How to {replacement}{normalized[len(prefix):]}"
    prefix = _ASSET_PREFIX.get(asset_type, "")
    return f"{prefix} {normalized}".strip() if prefix else normalized


def _short_audience(audience: str) -> str:
    """Extract just the role/noun from an audience string, truncating at qualifiers."""
    for sep in (" who ", " that ", " caring ", " interested "):
        idx = audience.lower().find(sep)
        if idx > 0:
            return audience[:idx].strip()
    words = audience.split()
    if len(words) > 5:
        return " ".join(words[:5])
    return audience


TOPIC_STOPWORDS = {
    "about",
    "after",
    "angle",
    "article",
    "backend",
    "blog",
    "build",
    "core",
    "care",
    "debug",
    "debugging",
    "developer",
    "developers",
    "engineer",
    "frontend",
    "from",
    "guide",
    "monitor",
    "monitoring",
    "production",
    "should",
    "service",
    "services",
    "teams",
    "technical",
    "tool",
    "tools",
    "tutorial",
    "understanding",
    "user",
    "users",
    "what",
    "with",
}

FOREIGN_TOPIC_CLUSTERS = (
    {"pgvector", "postgres", "postgresql", "vector", "vectors", "rag", "retrieval", "embedding", "embeddings", "hybrid", "reranking"},
    {"vitals", "lcp", "inp", "cls"},
    {"kubernetes", "k8s", "container", "containers"},
)


def _topic_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for term in re.findall(r"[a-z0-9]+", text.lower()):
        if len(term) <= 3 or term in TOPIC_STOPWORDS:
            continue
        terms.add(term)
        if term.endswith("s") and len(term) > 4:
            terms.add(term[:-1])
    return terms


def _topic_phrases(text: str) -> set[str]:
    words = [
        term
        for term in re.findall(r"[a-z0-9]+", text.lower())
        if len(term) > 2 and term not in TOPIC_STOPWORDS
    ]
    phrases = set()
    for width in (2, 3):
        for index in range(max(0, len(words) - width + 1)):
            phrases.add(" ".join(words[index : index + width]))
    return phrases


def _dev_article_relevance(topic: str, article: DEVArticle) -> int:
    terms = _topic_terms(topic)
    phrases = _topic_phrases(topic)
    if not terms and not phrases:
        return 0
    title = article.title.lower()
    description = (article.description or "").lower()
    body = (article.body_excerpt or "").lower()
    tags = " ".join(article.tags).lower()
    haystack = f"{title} {description} {body} {tags}"

    score = 0
    for phrase in phrases:
        if phrase in title:
            score += 8
        elif phrase in description:
            score += 5
        elif phrase in body:
            score += 3
    for term in terms:
        if term in title:
            score += 5
        if term in tags:
            score += 4
        if term in description:
            score += 2
        if term in body:
            score += 1
    if score and any(term in haystack for term in ("beginner", "intro", "getting started")):
        score -= 1
    return max(score, 0)


def _topic_dev_links(
    topic: str,
    articles: list[DEVArticle],
    *,
    used_urls: set[str] | None = None,
    context_terms: set[str] | None = None,
    limit: int = 4,
) -> list[str]:
    used_urls = used_urls or set()
    scored = [
        (_dev_article_relevance(topic, article), article)
        for article in articles
        if article.url
        and article.url not in used_urls
        and (
            not context_terms
            or (_topic_terms(f"{article.title} {article.description or ''} {' '.join(article.tags)} {article.body_excerpt or ''}") & context_terms)
        )
    ]
    matched = [
        article
        for score, article in sorted(scored, key=lambda item: item[0], reverse=True)
        if score >= 5
    ]
    return [article.url for article in matched[:limit]]


def _hn_item_relevance(topic: str, item: HNItem) -> int:
    terms = _topic_terms(topic)
    phrases = _topic_phrases(topic)
    title = item.title.lower()
    text = (item.text or "").lower()
    return _text_relevance_score(terms, phrases, f"{title} {text}")


def _text_relevance_score(terms: set[str], phrases: set[str], text: str) -> int:
    score = 0
    for phrase in phrases:
        if phrase in text:
            score += 8
    for term in terms:
        if term in text:
            score += 5
    return score


def _hn_item_matches_topic(topic: str, item: HNItem, context_terms: set[str] | None) -> bool:
    terms = _topic_terms(topic)
    phrases = _topic_phrases(topic)
    if not terms and not phrases:
        return False

    title_terms = _topic_terms(item.title)
    combined_terms = _topic_terms(f"{item.title} {item.text or ''}")
    if context_terms and not (combined_terms & context_terms):
        return False

    title_score = _text_relevance_score(terms, phrases, item.title.lower())
    text_score = _text_relevance_score(terms, phrases, (item.text or "").lower())
    title_lower = item.title.lower()
    is_discussion = title_lower.startswith(("ask hn:", "tell hn:"))
    if title_score >= 8:
        return True
    if is_discussion and text_score >= 12:
        return True
    return False


def _topic_hn_links(
    topic: str,
    hn_items: list[HNItem],
    *,
    context_terms: set[str] | None = None,
    limit: int = 4,
) -> list[str]:
    scored = [
        (_hn_item_relevance(topic, item), item)
        for item in hn_items
        if item.url
        and _hn_item_matches_topic(topic, item, context_terms)
    ]
    matched = [
        item
        for score, item in sorted(scored, key=lambda item: item[0], reverse=True)
        if score >= (8 if context_terms else 5)
    ]
    return [item.url for item in matched[:limit]]


def _repair_report_links(
    report: IdeationReport,
    hn_items: list[HNItem],
    dev_articles: list[DEVArticle],
    context: CompanyContext | None = None,
) -> None:
    context_terms = _context_relevance_terms(context) if context else set()
    for idea in report.content_ideas:
        idea.hn_evidence = _topic_hn_links(idea.title, hn_items, context_terms=context_terms)
    for trend in report.trend_digest:
        trend.hn_links = _topic_hn_links(
            trend.topic,
            hn_items,
            context_terms=context_terms,
        )

    _repair_report_dev_links(report, dev_articles, context_terms=context_terms)


def _repair_report_dev_links(
    report: IdeationReport,
    dev_articles: list[DEVArticle],
    *,
    context_terms: set[str] | None = None,
) -> None:
    if not dev_articles:
        return
    used_urls: set[str] = set()
    for idea in report.content_ideas:
        topic = f"{idea.title} {idea.angle} {idea.dev_gap} {' '.join(idea.outline[:3])}"
        links = _topic_dev_links(
            topic,
            dev_articles,
            used_urls=used_urls,
            context_terms=context_terms,
            limit=3,
        )
        if links:
            idea.dev_links = links
            used_urls.update(links)
        else:
            idea.dev_links = []
            if not idea.dev_gap or "operational debugging details" in idea.dev_gap.lower():
                idea.dev_gap = "No specific DEV.to article matched this idea closely; treat this as a potential supply gap to validate."

    for trend in report.trend_digest:
        links = _topic_dev_links(
            f"{trend.topic} {trend.why_trending} {trend.dev_saturation}",
            dev_articles,
            context_terms=context_terms,
            limit=3,
        )
        trend.dev_links = links
        if not links:
            trend.dev_saturation = (
                trend.dev_saturation
                or "No specific DEV.to article matched this trend closely."
            )


def _dev_links_for_gap(
    gap: ContentGap,
    dev_signals: list[DEVSupplySignal],
    dev_articles: list[DEVArticle] | None = None,
    used_urls: set[str] | None = None,
) -> list[str]:
    if dev_articles:
        article_links = _topic_dev_links(
            f"{gap.topic} {gap.supply_gap} {gap.why_it_matters}",
            dev_articles,
            used_urls=used_urls,
        )
        if article_links:
            return article_links
    topic_terms = {term for term in gap.topic.lower().split() if len(term) > 3}
    for signal in dev_signals:
        signal_terms = set(signal.topic.lower().split())
        if topic_terms & signal_terms and signal.source_urls:
            return signal.source_urls[:4]
    return []


def fallback_content_gaps(
    hn_signals: list[HNDeveloperSignal],
    dev_signals: list[DEVSupplySignal],
    memories: list[MemoryRecord],
    seed_keywords: list[str] | None = None,
) -> list[ContentGap]:
    supply = dev_signals[0] if dev_signals else None
    gaps: list[ContentGap] = []
    for signal in hn_signals[:8]:
        asset_type = _asset_type_for_topic(signal.topic)
        novelty = memory_novelty_score(signal.topic, memories)
        supply_quality = supply.supply_quality_score if supply else 35
        gap_score = max(10, 100 - supply_quality)
        business_score = _business_intent_score(signal.topic, asset_type)
        total = (
            signal.intensity_score * 0.35
            + gap_score * 0.30
            + novelty * 0.15
            + business_score * 0.20
        )
        gaps.append(
            ContentGap(
                topic=signal.topic,
                demand_score=signal.intensity_score,
                supply_gap_score=gap_score,
                memory_novelty_score=novelty,
                business_intent_score=business_score,
                total_score=_bounded_score(total),
                why_it_matters=signal.evidence_summary,
                demand_evidence=signal.source_urls,
                supply_gap=(
                    "; ".join(supply.missing_angles)
                    if supply and supply.missing_angles
                    else "Existing DEV.to articles do not cover the operational angle in depth."
                ),
                recommended_asset_type=asset_type,
                search_intent=_search_intent_for_asset(asset_type),
            )
        )

    if seed_keywords and len(gaps) < 5:
        supply_quality = supply.supply_quality_score if supply else 35
        supply_gap_text = (
            "; ".join(supply.missing_angles)
            if supply and supply.missing_angles
            else "Existing DEV.to articles do not cover the operational angle in depth."
        )
        existing_topics = {gap.topic.lower() for gap in gaps}
        for keyword in seed_keywords:
            synthetic_topic = _topic_from_seed_keyword(keyword)
            if synthetic_topic.lower() in existing_topics:
                continue
            asset_type = _asset_type_for_topic(synthetic_topic)
            novelty = memory_novelty_score(synthetic_topic, memories)
            gap_score = max(10, 100 - supply_quality)
            business_score = _business_intent_score(synthetic_topic, asset_type)
            total = (
                50 * 0.35
                + gap_score * 0.30
                + novelty * 0.15
                + business_score * 0.20
            )
            gaps.append(
                ContentGap(
                    topic=synthetic_topic,
                    demand_score=50,
                    supply_gap_score=gap_score,
                    memory_novelty_score=novelty,
                    business_intent_score=business_score,
                    total_score=_bounded_score(total),
                    why_it_matters=f"Seed keyword '{keyword}' indicates audience interest; DEV.to supply has gaps.",
                    demand_evidence=[],
                    supply_gap=supply_gap_text,
                    recommended_asset_type=asset_type,
                    search_intent=_search_intent_for_asset(asset_type),
                )
            )
            existing_topics.add(synthetic_topic.lower())
            if len(gaps) >= 8:
                break

    return sorted(gaps, key=lambda gap: gap.total_score, reverse=True)


def _topic_from_seed_keyword(keyword: str) -> str:
    lowered = keyword.lower().strip()
    cleaned = _clean_topic_fragment(lowered)
    if not cleaned:
        return "Production implementation guide"
    if any(term in lowered for term in ("debug", "latency", "error", "failure", "incident", "timeout")):
        return f"Debugging {cleaned} in production"
    if any(term in lowered for term in ("migration", "migrate", "upgrade")):
        return f"Migration playbook for {cleaned}"
    if any(term in lowered for term in ("compare", "comparison", "alternative", "versus", " vs ")):
        return f"Evaluating {cleaned} alternatives"
    if any(term in lowered for term in ("architecture", "integration", "deploy", "scaling", "scale")):
        return f"Production {cleaned} architecture"
    if any(term in lowered for term in ("cost", "benchmark", "evaluation", "eval", "tradeoff", "throughput")):
        return f"Evaluating {cleaned} tradeoffs"
    return f"Production {cleaned} guide"


def _dev_saturation_text(dev_signals: list[DEVSupplySignal]) -> str:
    if not dev_signals:
        return "DEV.to supply unclear in this run."
    supply = dev_signals[0]
    if supply.saturated_angles:
        return "; ".join(supply.saturated_angles[:3])
    if supply.common_angles:
        return f"Common angles: {', '.join(supply.common_angles[:3])}"
    return "Limited DEV.to coverage found."


def fallback_ideation_report(
    context: CompanyContext,
    hn_signals: list[HNDeveloperSignal],
    gaps: list[ContentGap],
    dev_signals: list[DEVSupplySignal],
    dev_articles: list[DEVArticle] | None = None,
) -> IdeationReport:
    saturation = _dev_saturation_text(dev_signals)
    dev_articles = dev_articles or []
    context_terms = _context_relevance_terms(context)

    trend_digest: list[TrendDigestItem] = []
    seen_trends: set[str] = set()
    for signal in hn_signals:
        topic = signal.topic
        if not _is_context_relevant(topic, context_terms):
            continue
        trend_key = topic.strip().lower()
        if trend_key in seen_trends:
            continue
        seen_trends.add(trend_key)
        trend_gap = ContentGap(
            topic=topic,
            demand_score=signal.intensity_score,
            supply_gap_score=50,
            memory_novelty_score=50,
            total_score=signal.intensity_score,
            why_it_matters=signal.evidence_summary,
            supply_gap=saturation,
            recommended_asset_type=_asset_type_for_topic(topic),
        )
        trend_digest.append(
            TrendDigestItem(
                topic=topic,
                why_trending=signal.evidence_summary or signal.pain_point,
                intensity_score=signal.intensity_score,
                dev_saturation=saturation,
                hn_links=signal.source_urls[:4],
                dev_links=_dev_links_for_gap(trend_gap, dev_signals, dev_articles)
            )
        )
        if len(trend_digest) >= 8:
            break

    content_ideas: list[ContentIdea] = []
    seen_ideas: set[str] = set()
    used_dev_urls: set[str] = set()
    for gap in gaps:
        topic = gap.topic
        if not _is_context_relevant(topic, context_terms):
            continue
        idea_format = gap.recommended_asset_type or _asset_type_for_topic(topic)
        if idea_format not in {"talk", "blog", "tutorial"}:
            idea_format = _asset_type_for_topic(topic)
        title = _brief_page_title(topic, idea_format)
        idea_key = title.strip().lower()
        if idea_key in seen_ideas:
            continue
        seen_ideas.add(idea_key)
        content_ideas.append(
            ContentIdea(
                title=title,
                format=idea_format,
                angle=(
                    f"Lead with a realistic {context.product} implementation and show tradeoffs, "
                    "failure modes, and decision criteria instead of a beginner overview."
                ),
                outline=[
                    "Problem and developer intent",
                    "Current approaches and tradeoffs",
                    f"Implementation walkthrough with {context.product}",
                    "Failure modes and debugging checklist",
                    "Decision checklist and next steps",
                ],
                score=gap.total_score,
                confidence="High" if gap.total_score >= 70 else "Medium",
                hn_evidence=gap.demand_evidence[:4],
                dev_gap=(
                    gap.supply_gap
                    if _dev_links_for_gap(gap, dev_signals, dev_articles, used_dev_urls)
                    else "No specific DEV.to article matched this idea closely; treat this as a potential supply gap to validate."
                ),
                dev_links=[],
            )
        )
        content_ideas[-1].dev_links = _dev_links_for_gap(
            gap,
            dev_signals,
            dev_articles,
            used_dev_urls,
        )
        used_dev_urls.update(content_ideas[-1].dev_links)
        if len(content_ideas) >= 5:
            break

    if not content_ideas:
        short_audience = _short_audience(context.audience)
        title = f"How {short_audience} should evaluate {context.product}"
        content_ideas.append(
            ContentIdea(
                title=title,
                format="blog",
                angle="Use concrete evaluation criteria and a minimal runnable setup instead of product claims.",
                outline=[
                    "Evaluation criteria",
                    "Demo setup",
                    "Tradeoffs and failure modes",
                ],
                score=55,
                confidence="Low",
                hn_evidence=[],
                dev_gap="Supply is unclear; validate with more recent DEV.to searches.",
                dev_links=[],
            )
        )

    if not trend_digest and hn_signals:
        signal = next(
            (
                candidate
                for candidate in hn_signals
                if _is_context_relevant(candidate.topic, context_terms)
            ),
            hn_signals[0],
        )
        trend_digest.append(
            TrendDigestItem(
                topic=signal.topic,
                why_trending=signal.evidence_summary,
                intensity_score=signal.intensity_score,
                dev_saturation=saturation,
                hn_links=signal.source_urls[:4],
                dev_links=_topic_dev_links(signal.topic, dev_articles),
            )
        )

    strongest = content_ideas[0]
    return IdeationReport(
        company=context.company_name,
        summary=(
            f"The strongest DevRel opportunity is '{strongest.title}' because it combines "
            f"recent developer demand with a DEV.to supply gap around {context.product}."
        ),
        trend_digest=trend_digest[:8],
        content_ideas=content_ideas[:5],
        memory_notes=[],
    )


def _context_relevance_terms(context: CompanyContext) -> set[str]:
    terms = _topic_terms(
        " ".join(
            [
                context.company_name,
                context.product,
                context.audience,
                *context.seed_keywords,
                *context.competitors,
                *context.existing_topics,
            ]
        )
    )
    return {
        term
        for term in terms
        if term
        not in {
            "backend",
            "engineers",
            "platform",
            "teams",
            "systems",
            "production",
            "engineer",
            "care",
            "service",
            "services",
        }
    }


def _is_context_relevant(topic: str, context_terms: set[str]) -> bool:
    if not context_terms:
        return True
    topic_terms = _topic_terms(topic)
    if _has_foreign_topic_cluster(topic_terms, context_terms):
        return False
    return bool(topic_terms & context_terms)


def _has_foreign_topic_cluster(topic_terms: set[str], context_terms: set[str]) -> bool:
    for cluster in FOREIGN_TOPIC_CLUSTERS:
        if topic_terms & cluster and not context_terms & cluster:
            return True
    return False


def _idea_context_text(idea: ContentIdea) -> str:
    return " ".join([idea.title, idea.angle, idea.dev_gap, *idea.outline])


def _sanitize_report_for_context(
    report: IdeationReport,
    context: CompanyContext,
) -> IdeationReport:
    context_terms = _context_relevance_terms(context)
    if not context_terms:
        return report

    report.content_ideas = [
        idea
        for idea in report.content_ideas
        if _is_context_relevant(_idea_context_text(idea), context_terms)
    ]
    report.trend_digest = [
        trend
        for trend in report.trend_digest
        if _is_context_relevant(f"{trend.topic} {trend.why_trending}", context_terms)
    ]
    if not report.content_ideas or not report.trend_digest:
        return report
    return report


def _augment_report_missing_ideas(
    report: IdeationReport,
    context: CompanyContext,
    content_gaps: list[ContentGap],
    dev_signals: list[DEVSupplySignal],
    dev_articles: list[DEVArticle],
    target_count: int = 5,
) -> IdeationReport:
    report = _sanitize_report_for_context(report, context)
    if len(report.content_ideas) >= target_count:
        _repair_report_dev_links(
            report,
            dev_articles,
            context_terms=_context_relevance_terms(context),
        )
        return report

    seed_gaps = fallback_content_gaps(
        [],
        dev_signals,
        [],
        seed_keywords=context.seed_keywords,
    )
    seen_gap_topics = {gap.topic.strip().lower() for gap in content_gaps}
    merged_gaps = list(content_gaps)
    for gap in seed_gaps:
        key = gap.topic.strip().lower()
        if key in seen_gap_topics:
            continue
        merged_gaps.append(gap)
        seen_gap_topics.add(key)

    fallback = fallback_ideation_report(
        context,
        [],
        merged_gaps,
        dev_signals,
        dev_articles,
    )
    seen = {idea.title.strip().lower() for idea in report.content_ideas}
    for idea in fallback.content_ideas:
        key = idea.title.strip().lower()
        if key in seen:
            continue
        report.content_ideas.append(idea)
        seen.add(key)
        if len(report.content_ideas) >= target_count:
            break

    _repair_report_dev_links(
        report,
        dev_articles,
        context_terms=_context_relevance_terms(context),
    )
    return report


def _coerce_report_payload(report_raw: object) -> dict[str, Any]:
    if report_raw is None:
        return {}
    if isinstance(report_raw, dict):
        return report_raw
    if hasattr(report_raw, "model_dump"):
        dumped = report_raw.model_dump()
        if isinstance(dumped, dict):
            return dumped
    if hasattr(report_raw, "to_dict"):
        dumped = report_raw.to_dict()
        if isinstance(dumped, dict):
            return dumped
    return {}


def _filter_dataclass_fields(cls, payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    allowed = {field.name for field in dataclasses.fields(cls)}
    return {key: value for key, value in payload.items() if key in allowed}


def _normalize_report_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("report"), dict):
        payload = payload["report"]
    normalized = dict(payload)
    trend_items = (
        normalized.get("trend_digest")
        or normalized.get("trends")
        or normalized.get("developer_trends")
        or normalized.get("trend_digest_items")
        or []
    )
    idea_items = (
        normalized.get("content_ideas")
        or normalized.get("ideas")
        or normalized.get("recommendations")
        or normalized.get("talk_blog_ideas")
        or normalized.get("ranked_ideas")
        or []
    )
    normalized["trend_digest"] = [
        {
            "topic": str(item.get("topic") or item.get("title") or "Developer trend").strip(),
            "why_trending": str(item.get("why_trending") or item.get("summary") or item.get("reason") or "").strip(),
            "intensity_score": item.get("intensity_score") or item.get("score") or 50,
            "dev_saturation": str(item.get("dev_saturation") or item.get("dev_gap") or "").strip(),
            "hn_links": item.get("hn_links") or item.get("hn_evidence") or item.get("source_urls") or [],
            "dev_links": item.get("dev_links") or [],
        }
        for item in trend_items
        if isinstance(item, dict)
    ]
    normalized["content_ideas"] = [
        {
            "title": str(item.get("title") or item.get("idea") or item.get("topic") or "Untitled idea").strip(),
            "format": str(item.get("format") or item.get("asset_type") or "blog").strip(),
            "angle": str(item.get("angle") or item.get("why_now") or item.get("rationale") or "").strip(),
            "outline": item.get("outline") or item.get("sections") or ["Problem and developer intent", "Technical walkthrough", "Decision criteria"],
            "score": item.get("score") or item.get("priority_score") or 50,
            "confidence": str(item.get("confidence") or "Medium").strip(),
            "hn_evidence": item.get("hn_evidence") or item.get("hn_links") or item.get("source_urls") or [],
            "dev_gap": str(item.get("dev_gap") or item.get("dev_supply_gap") or "").strip(),
            "dev_links": item.get("dev_links") or item.get("dev_supply_links") or [],
        }
        for item in idea_items
        if isinstance(item, dict)
    ]
    if not normalized["trend_digest"] and normalized["content_ideas"]:
        normalized["trend_digest"] = [
            {
                "topic": idea["title"],
                "why_trending": idea["angle"] or "Derived from the model's ranked recommendation.",
                "intensity_score": idea["score"],
                "dev_saturation": idea["dev_gap"],
                "hn_links": idea["hn_evidence"],
                "dev_links": idea["dev_links"],
            }
            for idea in normalized["content_ideas"][:3]
        ]
    return _filter_dataclass_fields(IdeationReport, normalized)


def _brief_format(asset_type: str) -> str:
    lowered = asset_type.lower()
    if "talk" in lowered or "conference" in lowered or "keynote" in lowered:
        return "talk"
    if "tutorial" in lowered or "guide" in lowered or "how to" in lowered:
        return "tutorial"
    return "blog"


def _legacy_briefs_to_ideation_report(
    payload: dict[str, Any],
    context: CompanyContext,
    hn_signals: list[HNDeveloperSignal],
    dev_signals: list[DEVSupplySignal],
) -> IdeationReport | None:
    briefs = payload.get("publishing_briefs")
    if not isinstance(briefs, list) or not briefs:
        return None

    saturation = _dev_saturation_text(dev_signals)
    trend_digest: list[TrendDigestItem] = []
    for signal in hn_signals[:8]:
        trend_digest.append(
            TrendDigestItem(
                topic=signal.topic,
                why_trending=signal.evidence_summary or signal.pain_point,
                intensity_score=signal.intensity_score,
                dev_saturation=saturation,
                hn_links=signal.source_urls[:4],
                dev_links=signal.source_urls[:4],
            )
        )

    content_ideas: list[ContentIdea] = []
    for brief in briefs[:5]:
        if not isinstance(brief, dict):
            continue
        asset_type = str(brief.get("asset_type") or "blog")
        idea_format = _brief_format(asset_type)
        title = str(brief.get("page_title") or brief.get("suggested_h1") or "Untitled idea").strip()
        outline: list[str] = []
        for section in brief.get("outline") or []:
            if isinstance(section, dict):
                section_title = str(section.get("title") or "").strip()
                if section_title:
                    outline.append(section_title)
            elif isinstance(section, str) and section.strip():
                outline.append(section.strip())
        content_ideas.append(
            ContentIdea(
                title=title,
                format=idea_format,
                angle=str(
                    brief.get("differentiation_angle")
                    or brief.get("priority_rationale")
                    or ""
                ).strip(),
                outline=outline or ["Problem framing", "Implementation", "Takeaways"],
                score=int(brief.get("score") or 50),
                confidence=str(brief.get("confidence") or "Medium"),
                hn_evidence=_coerce_list(brief.get("hn_demand_evidence")),
                dev_gap=str(brief.get("dev_supply_gap") or ""),
                dev_links=_coerce_list(brief.get("dev_supply_links")),
            )
        )

    if not content_ideas:
        return None

    company = str(payload.get("company") or context.company_name or context.product).strip()
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        summary = (
            f"Migrated legacy publishing briefs into {len(content_ideas)} DevRel content ideas "
            f"for {company or context.product}."
        )
    return IdeationReport(
        company=company,
        summary=summary,
        trend_digest=trend_digest,
        content_ideas=content_ideas,
        memory_notes=_coerce_list(payload.get("memory_notes")),
    )


def _parse_ideation_report(
    report_raw: object,
    context: CompanyContext,
    hn_signals: list[HNDeveloperSignal],
    content_gaps: list[ContentGap],
    dev_signals: list[DEVSupplySignal],
    dev_articles: list[DEVArticle] | None = None,
) -> IdeationReport:
    dev_articles = dev_articles or []
    payload = _coerce_report_payload(report_raw)
    if payload.get("publishing_briefs"):
        migrated = _legacy_briefs_to_ideation_report(payload, context, hn_signals, dev_signals)
        if migrated is not None:
            if not migrated.trend_digest:
                migrated.trend_digest = fallback_ideation_report(
                    context, hn_signals, content_gaps, dev_signals, dev_articles
                ).trend_digest
            _sanitize_report_for_context(migrated, context)
            _repair_report_dev_links(
                migrated,
                dev_articles,
                context_terms=_context_relevance_terms(context),
            )
            return migrated

    if isinstance(report_raw, IdeationReport):
        report = report_raw
    else:
        try:
            report = IdeationReport(**_normalize_report_payload(payload))
        except Exception:
            report = fallback_ideation_report(
                context, hn_signals, content_gaps, dev_signals, dev_articles
            )

    if not report.content_ideas or not report.trend_digest:
        report = fallback_ideation_report(
            context, hn_signals, content_gaps, dev_signals, dev_articles
        )
    if report_needs_repair(report, context):
        report = fallback_ideation_report(
            context, hn_signals, content_gaps, dev_signals, dev_articles
        )
    _sanitize_report_for_context(report, context)
    _repair_report_dev_links(
        report,
        dev_articles,
        context_terms=_context_relevance_terms(context),
    )
    return report


def _parse_llm_report_strict(
    report_raw: object,
    context: CompanyContext,
    dev_articles: list[DEVArticle],
) -> IdeationReport:
    payload = _coerce_report_payload(report_raw)
    if isinstance(report_raw, IdeationReport):
        report = report_raw
    else:
        try:
            report = IdeationReport(**_normalize_report_payload(payload))
        except Exception as exc:
            raise RuntimeError("The Agno team did not return a valid structured report.") from exc

    if not report.content_ideas:
        raise RuntimeError("The Agno team returned no content ideas.")
    if not report.trend_digest:
        raise RuntimeError("The Agno team returned no trend digest.")
    if report_needs_repair(report, context):
        raise RuntimeError(
            "The Agno team report failed context or format validation, so I did not replace it with a deterministic fallback."
        )
    _sanitize_report_for_context(report, context)
    if not report.content_ideas or not report.trend_digest:
        raise RuntimeError("The Agno team report did not match the active product context.")
    _repair_report_dev_links(
        report,
        dev_articles,
        context_terms=_context_relevance_terms(context),
    )
    return report


async def write_report_with_llm(
    context: CompanyContext,
    query_plan: SearchQueryPlan,
    hn_items: list[HNItem],
    dev_articles: list[DEVArticle],
    memories: list[MemoryRecord],
    settings: Settings,
) -> IdeationReport:
    """Use the model to write the final report from gathered facts when team output is malformed."""
    model = build_model(settings)
    agent = make_agent(
        model,
        IDEATION_WRITER_PROMPT
        + "\nReturn one JSON object with keys: company, summary, trend_digest, content_ideas, memory_notes.",
        "final_report_writer",
    )
    request = {
        "context": context.to_dict(),
        "query_plan": query_plan.to_dict(),
        "hn_items": [item.to_dict() for item in hn_items[:20]],
        "dev_articles": [article.to_dict() for article in dev_articles[:20]],
        "memory_summaries": [memory.__dict__ for memory in memories[:8]],
        "requirements": [
            "Write exactly 5 ranked talk/blog/tutorial ideas when evidence permits.",
            "Base every idea on the provided HN/DEV/Engram facts.",
            "Do not write a full article.",
            "Do not mention internal agent failures or parsing.",
        ],
    }
    raw_report = await run_agent(agent, json.dumps(request, ensure_ascii=False))
    try:
        payload = parse_json_object(raw_report)
    except Exception as parse_exc:
        logger.warning("Final report JSON parse failed; asking GLM to repair JSON: %s", parse_exc)
        repair_agent = make_agent(model, JSON_REPAIR_PROMPT, "json_repair")
        repaired = await run_agent(
            repair_agent,
            json.dumps(
                {
                    "error": str(parse_exc),
                    "malformed_json": raw_report,
                },
                ensure_ascii=False,
            ),
        )
        payload = parse_json_object(repaired)
    report = IdeationReport(**_normalize_report_payload(payload))
    if not report.content_ideas or not report.trend_digest:
        raise RuntimeError("The GLM report writer did not produce enough usable report sections.")
    for idea in report.content_ideas:
        if idea.format not in {"talk", "blog", "tutorial"}:
            idea.format = _brief_format(idea.format)
        if _looks_like_raw_source_fragment(idea.title):
            raise RuntimeError("The GLM report writer returned a raw source fragment as an idea title.")
    for trend in report.trend_digest:
        if _looks_like_raw_source_fragment(trend.topic):
            raise RuntimeError("The GLM report writer returned a raw source fragment as a trend topic.")
    report.content_ideas = report.content_ideas[:5]
    report.trend_digest = report.trend_digest[:8]
    _repair_report_links(
        report,
        hn_items,
        dev_articles,
        context,
    )
    return report


def report_needs_repair(report: IdeationReport, context: CompanyContext) -> bool:
    if not report.content_ideas:
        return True
    context_terms = _context_relevance_terms(context)
    if any(_looks_like_raw_source_fragment(trend.topic) for trend in report.trend_digest[:5]):
        return True
    for idea in report.content_ideas[:5]:
        title = idea.title.strip()
        if _looks_like_raw_source_fragment(title):
            return True
        if context_terms and not _is_context_relevant(_idea_context_text(idea), context_terms):
            return True
        if idea.format not in {"talk", "blog", "tutorial"}:
            return True
    return False


def _looks_like_raw_source_fragment(text: str) -> bool:
    cleaned = text.strip()
    lowered = cleaned.lower()
    if any(marker in lowered for marker in ("<p>", "&gt;", "&lt;", "<a ", "</", "pissing in the ocean")):
        return True
    if cleaned.startswith((">", '"')):
        return True
    if len(cleaned) > 120:
        return True
    return False


async def run_autonomous_content_team(
    context: CompanyContext,
    settings: Settings,
    memory_store: MemoryStore,
    limit: int = 10,
    on_stage: StageCallback | None = None,
    engram_user_id: str | None = None,
    conversation_id: str | None = None,
) -> AgentRunResult:
    user_id = engram_user_id or memory_user_id(context)
    session_id = conversation_id or user_id

    await _notify(on_stage, "Query Planner: choosing HN/DEV searches with GLM")
    query_plan = await plan_queries_with_llm(context, settings)
    await _notify(
        on_stage,
        f"Query Planner: selected HN ({_preview_items(query_plan.hn_queries)}) and DEV ({_preview_items(query_plan.dev_queries or query_plan.dev_tags)})",
    )

    await _notify(
        on_stage,
        "HN, DEV.to, and Engram agents: gathering facts in parallel from GLM-selected searches",
    )
    hn_task = search_hn(query_plan.hn_queries, limit=limit)
    dev_task = search_dev_articles(
        query_plan.dev_queries,
        query_plan.dev_tags,
        limit=limit,
        api_key=settings.dev_api_key,
    )
    memory_task = memory_store.search(
        query=f"{context.company_name} {context.product} {' '.join(context.seed_keywords)}",
        user_id=user_id,
        limit=8,
    )
    hn_items, dev_articles, memories = await asyncio.gather(
        hn_task,
        dev_task,
        memory_task,
    )
    await _notify(on_stage, f"HN Demand Agent: collected {len(hn_items)} recent HN stories/comments")
    await _notify(on_stage, f"DEV Supply Agent: collected {len(dev_articles)} recent DEV.to articles")
    await _notify(on_stage, f"Engram Memory Agent: returned {len(memories)} related memories")

    await _notify(
        on_stage,
        "DevRel Ideation Writer: reasoning over gathered facts and producing the report",
    )
    report = await write_report_with_llm(
        context,
        query_plan,
        hn_items,
        dev_articles,
        memories,
        settings,
    )
    _repair_report_links(report, hn_items, dev_articles, context)
    hn_signals: list[HNDeveloperSignal] = []
    dev_signals: list[DEVSupplySignal] = []
    content_gaps: list[ContentGap] = []
    team_member_responses = [
        "Query Planner selected HN/DEV searches with GLM.",
        "HN, DEV.to, and Engram evidence were gathered in parallel.",
        "DevRel Ideation Writer produced the final report from gathered facts.",
    ]

    await _notify(on_stage, "Storing research summary in Engram Memory")
    memory_notes = await memory_store.store_research_summary(
        context=context,
        report=report,
        content_gaps=content_gaps,
        user_id=user_id,
    )
    report.memory_notes = memory_notes

    markdown = render_markdown(report, build_source_title_lookup(hn_items, dev_articles))
    result = AgentRunResult(
        context=context,
        query_plan=query_plan,
        hn_items=hn_items,
        dev_articles=dev_articles,
        hn_signals=hn_signals,
        dev_signals=dev_signals,
        content_gaps=content_gaps,
        report=report,
        markdown=markdown,
        memory_notes=memory_notes,
        team_member_responses=team_member_responses,
        judge_score=None,
        judge_notes=[],
    )
    save_latest_result(result)
    return result


def save_latest_result(result: AgentRunResult) -> Path:
    output_dir = Path(__file__).resolve().parent / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "latest_ideation_report.json"
    output_path.write_text(result.to_json(indent=2), encoding="utf-8")
    return output_path


def build_source_title_lookup(
    hn_items: list[HNItem],
    dev_articles: list[DEVArticle],
) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in hn_items:
        if item.url and item.title:
            lookup[item.url] = item.title
    for article in dev_articles:
        if article.url and article.title:
            lookup[article.url] = article.title
    return lookup


def _format_source_link(url: str, source_titles: dict[str, str] | None = None) -> str:
    source_titles = source_titles or {}
    title = source_titles.get(url, "").strip()
    if not title:
        return url
    safe_title = title.replace("[", "(").replace("]", ")")
    return f"[{safe_title}]({url})"


def render_markdown(
    report: IdeationReport,
    source_titles: dict[str, str] | None = None,
) -> str:
    lines = [
        f"# Developer Trend & DevRel Ideation Report for {report.company}",
        "",
        "## Summary",
        "",
        report.summary,
        "",
        "## Developer Trend Digest",
        "",
    ]

    if report.trend_digest:
        for index, trend in enumerate(report.trend_digest, 1):
            lines.extend([
                f"### {index}. {trend.topic}",
                "",
                f"Intensity: {trend.intensity_score} | DEV saturation: {trend.dev_saturation}",
                "",
                trend.why_trending,
                "",
                "HN links:",
                "",
            ])
            if trend.hn_links:
                lines.extend(
                    f"* {_format_source_link(url, source_titles)}"
                    for url in trend.hn_links[:4]
                )
            else:
                lines.append("* No strong HN evidence found in this run.")
            lines.append("")
            if trend.dev_links:
                lines.append("DEV.to reference articles:")
                lines.append("")
                lines.extend(
                    f"* {_format_source_link(url, source_titles)}"
                    for url in trend.dev_links[:4]
                )
                lines.append("")
            else:
                lines.append("DEV.to reference articles:")
                lines.append("")
                lines.append("* No specific DEV.to article matched this trend closely.")
                lines.append("")
    else:
        lines.append("No trend digest items were captured in this run.")
        lines.append("")

    lines.extend([
        "## Recommended Talk & Blog Ideas",
        "",
    ])

    for index, idea in enumerate(report.content_ideas, 1):
        lines.extend([
            f"### {index}. {idea.title}",
            "",
            (
                f"Score: {idea.score} | Format: {idea.format} "
                f"| Confidence: {idea.confidence}"
            ),
            "",
            idea.angle,
            "",
            "HN evidence:",
            "",
        ])
        if idea.hn_evidence:
            lines.extend(
                f"* {_format_source_link(url, source_titles)}"
                for url in idea.hn_evidence[:4]
            )
        else:
            lines.append("* No strong HN evidence found in this run.")
        lines.append("")
        if idea.dev_links:
            lines.append("DEV.to reference articles:")
            lines.append("")
            lines.extend(
                f"* {_format_source_link(url, source_titles)}"
                for url in idea.dev_links[:4]
            )
            lines.append("")
        else:
            lines.append("DEV.to reference articles:")
            lines.append("")
            lines.append("* No specific DEV.to article matched this idea closely.")
            lines.append("")
        lines.extend([
            f"DEV supply gap: {idea.dev_gap}",
            "",
        ])
        if idea.outline:
            lines.append("Outline:")
            lines.append("")
            lines.extend(f"* {item}" for item in idea.outline[:6])
            lines.append("")

    return "\n".join(lines).strip() + "\n"
