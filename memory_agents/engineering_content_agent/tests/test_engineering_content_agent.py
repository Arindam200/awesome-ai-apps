import asyncio
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from agents import (
    _normalize_report_payload,
    _repair_report_links,
    build_source_title_lookup,
    fallback_content_gaps,
    fallback_hn_signals,
    fallback_ideation_report,
    render_markdown,
    report_needs_repair,
    write_report_with_llm,
)
from app import _memory_lookup_queries
from chat import (
    apply_prompt_context,
    followup_response,
    missing_fields,
    wants_brief_run,
    wants_current_report_followup,
    wants_explicit_research_run,
    wants_memory_lookup,
)
from config import DEFAULT_ENGRAM_USER_ID, Settings
from engram_memory import EngramMemoryStore
from llm import build_model
from models import (
    CompanyContext,
    ContentGap,
    HNItem,
    IdeationReport,
)
from sources import (
    SOURCE_LOOKBACK_DAYS,
    DEVArticle,
    filter_dev_articles,
    normalize_dev_article,
    search_dev_articles,
    search_hn,
)


class FakeHybridRetrieval:
    def __init__(self, limit):
        self.limit = limit


class FakeRun:
    run_id = "run-123"
    status = "queued"


class FakeRunStatus:
    run_id = "run-123"
    status = "completed"
    error = None
    memories_created = ["mem-1"]
    memories_updated = []


class FakeRuns:
    def __init__(self):
        self.wait_calls = []

    async def wait(self, run_id, **kwargs):
        self.wait_calls.append((run_id, kwargs))
        return FakeRunStatus()


class FakeMemories:
    def __init__(self):
        self.search_calls = []
        self.add_calls = []

    async def search(self, **kwargs):
        self.search_calls.append(kwargs)
        return []

    async def add(self, *args, **kwargs):
        self.add_calls.append((args, kwargs))
        return FakeRun()


class FakePreExtractedItem:
    def __init__(self, content, topic):
        self.content = content
        self.topic = topic


class FakePreExtractedInput:
    def __init__(self, items):
        self.items = items


class FakeAsyncEngramClient:
    instances = []

    def __init__(self, api_key):
        self.api_key = api_key
        self.memories = FakeMemories()
        self.runs = FakeRuns()
        FakeAsyncEngramClient.instances.append(self)


def install_fake_engram(monkeypatch):
    FakeAsyncEngramClient.instances = []
    monkeypatch.setitem(
        sys.modules,
        "engram",
        types.SimpleNamespace(
            AsyncEngramClient=FakeAsyncEngramClient,
            HybridRetrieval=FakeHybridRetrieval,
            PreExtractedInput=FakePreExtractedInput,
            PreExtractedItem=FakePreExtractedItem,
        ),
    )


def test_natural_raah_prompt_extracts_context_and_keywords():
    context = {
        "company_name": "",
        "product": "",
        "audience": "",
        "seed_keywords": [],
        "competitors": [],
        "existing_topics": [],
    }

    changed = apply_prompt_context(
        (
            "I run raah.dev, a web analytics and network observability tool. "
            "My audience is backend engineers who care about latency, error rates, "
            "and user-side ISP behavior. Research what developers are discussing on HN, "
            "check DEV.to saturation, and suggest talk and blog ideas around debugging production services."
        ),
        context,
    )

    assert changed is True
    assert context["company_name"] == "raah.dev"
    assert context["product"] == "web analytics and network observability tool"
    assert context["audience"].startswith("backend engineers")
    assert "latency" in context["seed_keywords"]
    assert "error rates" in context["seed_keywords"]
    assert missing_fields(context) == []


def test_natural_pgvector_prompt_extracts_company_and_product_category():
    context = {
        "company_name": "",
        "product": "",
        "audience": "",
        "seed_keywords": [],
        "competitors": [],
        "existing_topics": [],
    }

    changed = apply_prompt_context(
        (
            "I lead DevRel for pgvector, a Postgres extension for vector search and AI retrieval. "
            "Our audience is backend engineers and platform teams building RAG systems who care about "
            "indexing, query latency, hybrid search, embeddings, migrations, and production debugging."
        ),
        context,
    )

    assert changed is True
    assert context["company_name"] == "pgvector"
    assert context["product"] == "Postgres extension for vector search and AI retrieval"
    assert context["audience"].startswith("backend engineers")
    assert "query latency" in context["seed_keywords"]
    assert missing_fields(context) == []


def test_prompt_routing_memory_vs_research():
    context = {
        "company_name": "raah.dev",
        "product": "web analytics and network observability tool",
        "audience": "backend engineers",
        "seed_keywords": ["latency", "error rates"],
        "competitors": [],
        "existing_topics": [],
    }

    assert wants_memory_lookup("what products have we researched before?") is True
    assert wants_brief_run("what products have we researched before?", context) is False
    assert wants_memory_lookup("what topics were suggested recently? and related to raah") is True
    assert wants_current_report_followup("what topics were suggested recently? and related to raah") is True
    assert wants_brief_run("what topics were suggested recently? and related to raah", context) is False
    historical_prompt = "Based on our research of last few products, what could be the top 3 articles we should work on? suggest"
    assert wants_memory_lookup(historical_prompt) is True
    assert wants_brief_run(historical_prompt, context) is False
    assert wants_brief_run("research trends and suggest talk/blog ideas", context) is True
    assert wants_brief_run("please suggest new ideas", context) is True


def test_memory_lookup_queries_search_named_products_separately():
    queries = _memory_lookup_queries(
        "what products have we researched before? include n8n and Velt if available"
    )

    joined = "\n".join(queries).lower()
    assert "research summary for n8n" in joined
    assert "product context for n8n" in joined
    assert "research summary for velt" in joined
    assert "product context for velt" in joined


def test_explicit_pgvector_research_prompt_routes_to_research_not_memory():
    context = {
        "company_name": "pgvector",
        "product": "Postgres extension for vector search and AI retrieval",
        "audience": "backend engineers and platform teams building RAG systems",
        "seed_keywords": ["indexing", "query latency", "hybrid search"],
        "competitors": [],
        "existing_topics": [],
    }
    prompt = (
        "I lead DevRel for pgvector, a Postgres extension for vector search and AI retrieval. "
        "Our audience is backend engineers and platform teams building RAG systems who care about "
        "indexing, query latency, hybrid search, embeddings, migrations, and production debugging. "
        "Research developer conversations and DEV.to article saturation, then recommend technical "
        "blog and talk ideas we should publish next."
    )

    assert wants_explicit_research_run(prompt) is True
    assert wants_memory_lookup(prompt) is False
    assert wants_brief_run(prompt, context) is True


def test_followup_answers_recent_topics_from_latest_report():
    report = IdeationReport(
        company="raah.dev",
        summary="Latest Raah report summary.",
        trend_digest=[
            {
                "topic": "Debugging API latency from user sessions",
                "why_trending": "Developers are asking how to debug latency by user context.",
                "intensity_score": 82,
                "dev_saturation": "Limited coverage.",
            }
        ],
        content_ideas=[
            {
                "title": "How to debug API latency from user sessions",
                "format": "tutorial",
                "angle": "Show a Raah debugging workflow.",
                "outline": ["Trace slow requests"],
                "score": 88,
                "confidence": "High",
                "dev_gap": "DEV articles miss user-session debugging.",
            }
        ],
    )

    answer = followup_response(
        "what topics were suggested recently? and related to raah",
        types.SimpleNamespace(report=report),
    )

    assert answer is not None
    assert "Top trends from the latest report" in answer
    assert "Debugging API latency from user sessions" in answer
    assert "How to debug API latency from user sessions" in answer


def test_app_does_not_force_deterministic_research_intent_override():
    app_source = (APP_ROOT / "app.py").read_text(encoding="utf-8")

    assert "deterministic_run_intent" not in app_source
    assert "route_prompt_with_llm" in app_source
    assert '"no_report_followup"' in app_source
    assert "asyncio.wait_for" in app_source
    assert "requires_fresh_sources" in app_source


def test_hn_fallback_synthesizes_topics_not_raw_comments():
    item = HNItem(
        title="Some unrelated HN thread",
        text=(
            "> I cannot debug this.<p>Our API latency spikes only for some users "
            "on a specific ISP and the gateway timing is invisible."
        ),
        url="https://news.ycombinator.com/item?id=123",
        source_type="comment",
    )

    signals = fallback_hn_signals([item])

    assert signals
    assert signals[0].topic == "Debugging API latency from user sessions"
    assert "<p>" not in signals[0].topic
    assert not signals[0].topic.startswith(">")


def test_hn_fallback_deduplicates_topics_and_merges_urls():
    items = [
        HNItem(
            title="API latency debugging",
            text="API latency spikes by ISP",
            url="https://news.ycombinator.com/item?id=1",
            source_type="story",
            points=20,
            num_comments=5,
        ),
        HNItem(
            title="Gateway timeout debugging",
            text="Slow API requests are invisible from normal server logs",
            url="https://news.ycombinator.com/item?id=2",
            source_type="comment",
            points=10,
            num_comments=2,
        ),
    ]

    signals = fallback_hn_signals(items)

    assert len(signals) == 1
    assert signals[0].topic == "Debugging API latency from user sessions"
    assert signals[0].source_urls == [
        "https://news.ycombinator.com/item?id=1",
        "https://news.ycombinator.com/item?id=2",
    ]


def test_report_repair_rejects_raw_hn_fragments_even_with_evidence():
    context = CompanyContext(
        company_name="raah.dev",
        product="web analytics and network observability tool",
        audience="backend engineers",
        seed_keywords=["api latency"],
    )
    report = IdeationReport(
        company="raah.dev",
        summary="summary",
        trend_digest=[],
        content_ideas=[
            {
                "title": "> I cannot debug this<p>because the gateway is opaque",
                "format": "blog",
                "angle": "angle",
                "outline": ["one"],
                "score": 80,
                "confidence": "High",
                "hn_evidence": ["https://news.ycombinator.com/item?id=123"],
                "dev_gap": "gap",
            }
        ],
    )

    assert report_needs_repair(report, context) is True


def test_final_writer_repairs_malformed_json(monkeypatch):
    context = CompanyContext(
        company_name="assetsnip",
        product="website asset extractor chrome extension",
        audience="frontend developers and designers",
        seed_keywords=["svg", "fonts"],
    )
    settings = Settings(nebius_api_key="test")
    calls: list[str] = []

    async def fake_run_agent(agent, prompt):
        calls.append(agent.name)
        if agent.name == "final_report_writer":
            return '{"company":"assetsnip","summary":"bad "quote","trend_digest":[],"content_ideas":[],"memory_notes":[]}'
        return """
        {
          "company": "assetsnip",
          "summary": "Repaired report.",
          "trend_digest": [
            {
              "topic": "Extracting SVG and font assets from websites",
              "why_trending": "Developers want faster asset extraction workflows.",
              "intensity_score": 70,
              "dev_saturation": "Limited practical coverage.",
              "hn_links": [],
              "dev_links": []
            }
          ],
          "content_ideas": [
            {
              "title": "How to extract SVG and font assets from websites",
              "format": "tutorial",
              "angle": "Show a frontend workflow for assetsnip.",
              "outline": ["Find assets", "Export assets", "Organize design handoff"],
              "score": 72,
              "confidence": "Medium",
              "hn_evidence": [],
              "dev_gap": "DEV coverage is shallow.",
              "dev_links": []
            }
          ],
          "memory_notes": []
        }
        """

    monkeypatch.setattr("agents.run_agent", fake_run_agent)

    report = asyncio.run(
        write_report_with_llm(
            context=context,
            query_plan=types.SimpleNamespace(to_dict=lambda: {}),
            hn_items=[],
            dev_articles=[],
            memories=[],
            settings=settings,
        )
    )

    assert calls == ["final_report_writer", "json_repair"]
    assert report.company == "assetsnip"
    assert report.content_ideas[0].title == "How to extract SVG and font assets from websites"


def test_fallback_report_uses_natural_titles_and_dedupes_ideas():
    context = CompanyContext(
        company_name="raah.dev",
        product="web analytics and network observability tool",
        audience="backend engineers",
        seed_keywords=["error rates", "api latency"],
    )
    signals = [
        HNItem(
            title="Production error rates",
            text="Error rates and incidents are hard to debug in production",
            url="https://news.ycombinator.com/item?id=1",
            source_type="story",
        ),
        HNItem(
            title="Incident debugging",
            text="Production crash reports and outage debugging workflows",
            url="https://news.ycombinator.com/item?id=2",
            source_type="comment",
        ),
    ]
    hn_signals = fallback_hn_signals(signals)
    gaps = [
        ContentGap(
            topic="Production error-rate monitoring and incident debugging",
            demand_score=85,
            supply_gap_score=80,
            memory_novelty_score=100,
            total_score=88,
            why_it_matters="HN developers ask about incidents.",
            supply_gap="DEV articles miss production workflows.",
            recommended_asset_type="tutorial",
            demand_evidence=["https://news.ycombinator.com/item?id=1"],
        ),
        ContentGap(
            topic="Production error-rate monitoring and incident debugging",
            demand_score=84,
            supply_gap_score=80,
            memory_novelty_score=100,
            total_score=87,
            why_it_matters="HN developers ask about incidents.",
            supply_gap="DEV articles miss production workflows.",
            recommended_asset_type="tutorial",
            demand_evidence=["https://news.ycombinator.com/item?id=2"],
        ),
    ]

    report = fallback_ideation_report(context, hn_signals, gaps, [])

    assert [idea.title for idea in report.content_ideas] == [
        "How to monitor production error rates and debug incidents"
    ]
    assert "How to Production" not in report.content_ideas[0].title
    assert len(report.trend_digest) == 1


def test_report_repair_requires_product_or_seed_connection():
    context = CompanyContext(
        company_name="raah.dev",
        product="web analytics and network observability tool",
        audience="backend engineers",
        seed_keywords=["api latency"],
    )
    report = IdeationReport(
        company="raah.dev",
        summary="summary",
        trend_digest=[],
        content_ideas=[
            {
                "title": "Understanding experimental archaeology in teams",
                "format": "blog",
                "angle": "angle",
                "outline": ["one"],
                "score": 80,
                "confidence": "High",
                "hn_evidence": ["https://news.ycombinator.com/item?id=123"],
                "dev_gap": "gap",
            }
        ],
    )

    assert report_needs_repair(report, context) is True


def test_report_repair_rejects_stale_vector_topic_for_raah_context():
    context = CompanyContext(
        company_name="raah.dev",
        product="web analytics and network observability tool",
        audience="backend engineers",
        seed_keywords=["api latency", "error rates"],
    )
    report = IdeationReport(
        company="raah.dev",
        summary="summary",
        trend_digest=[],
        content_ideas=[
            {
                "title": "How to debug vector query latency in production",
                "format": "tutorial",
                "angle": "Explain pgvector query plans and HNSW indexes.",
                "outline": ["Tune vector indexes"],
                "score": 80,
                "confidence": "High",
                "hn_evidence": ["https://news.ycombinator.com/item?id=123"],
                "dev_gap": "gap",
            }
        ],
    )

    assert report_needs_repair(report, context) is True


def test_hn_evidence_repair_drops_unrelated_sources():
    context = CompanyContext(
        company_name="raah.dev",
        product="web analytics and network observability tool",
        audience="backend engineers",
        seed_keywords=["api latency", "error rates"],
    )
    report = IdeationReport(
        company="raah.dev",
        summary="summary",
        trend_digest=[],
        content_ideas=[
            {
                "title": "How to debug API latency from user sessions",
                "format": "tutorial",
                "angle": "Show user-session latency debugging for Raah.",
                "outline": ["Trace slow API requests by user session"],
                "score": 80,
                "confidence": "High",
                "hn_evidence": ["https://news.ycombinator.com/item?id=old"],
                "dev_gap": "gap",
            }
        ],
    )
    hn_items = [
        HNItem(
            title="Vector search indexing in Postgres",
            text="pgvector HNSW indexes and RAG query latency",
            url="https://news.ycombinator.com/item?id=vector",
            source_type="story",
        )
    ]

    _repair_report_links(report, hn_items, [], context)

    assert report.content_ideas[0].hn_evidence == []


def test_engram_search_uses_user_group_hybrid_without_conversation_filter(monkeypatch):
    install_fake_engram(monkeypatch)
    store = EngramMemoryStore("eng_test", group="default", conversation_id="conv-1")

    asyncio.run(store.search("prior topics", user_id="stable-user", limit=8))

    memories = FakeAsyncEngramClient.instances[0].memories
    call = memories.search_calls[0]
    assert call["user_id"] == "stable-user"
    assert call["group"] == "default"
    assert "properties" not in call
    assert isinstance(call["retrieval_config"], FakeHybridRetrieval)
    assert call["retrieval_config"].limit == 8


def test_engram_store_uses_user_group_and_optional_conversation_properties(monkeypatch):
    install_fake_engram(monkeypatch)
    store = EngramMemoryStore("eng_test", group="default", conversation_id="conv-1")
    context = CompanyContext(
        company_name="raah.dev",
        product="web analytics and network observability tool",
        audience="backend engineers",
        seed_keywords=["api latency"],
    )

    notes = asyncio.run(store.store_product_context(context, user_id="stable-user"))

    memories = FakeAsyncEngramClient.instances[0].memories
    args, kwargs = memories.add_calls[0]
    assert notes == ["Stored product context for raah.dev (Engram run `run-123`, status `completed`)."]
    assert args[0].items[0].topic == "UserKnowledge"
    assert "Product context for raah.dev" in args[0].items[0].content
    assert kwargs["user_id"] == "stable-user"
    assert kwargs["group"] == "default"
    assert kwargs["properties"] == {"conversation_id": "conv-1"}
    assert FakeAsyncEngramClient.instances[0].runs.wait_calls[0][0] == "run-123"


def test_settings_default_engram_user_id_is_stable():
    assert Settings(nebius_api_key="test").engram_user_id == DEFAULT_ENGRAM_USER_ID


def test_hn_search_filters_last_year_and_sorts_newest(monkeypatch):
    now = datetime.now(UTC)
    newest = (now - timedelta(days=3)).isoformat().replace("+00:00", "Z")
    older = (now - timedelta(days=20)).isoformat().replace("+00:00", "Z")
    too_old = (now - timedelta(days=SOURCE_LOOKBACK_DAYS + 2)).isoformat().replace("+00:00", "Z")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "hits": [
                    {"title": "Older API latency debugging", "objectID": "older", "created_at": older},
                    {"title": "Ask HN: Who wants to be hired? (April 2026)", "objectID": "noise", "created_at": newest},
                    {"title": "Newest API latency debugging", "objectID": "new", "created_at": newest},
                    {"title": "Old API latency debugging", "objectID": "old", "created_at": too_old},
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params):
            return FakeResponse()

    monkeypatch.setattr("sources.httpx.AsyncClient", FakeClient)

    items = asyncio.run(search_hn(["API latency"], lookback_days=SOURCE_LOOKBACK_DAYS))

    assert [item.title for item in items] == [
        "Newest API latency debugging",
        "Older API latency debugging",
    ]


def test_dev_search_filters_last_year_and_sorts_newest(monkeypatch):
    now = datetime.now(UTC)
    newest = (now - timedelta(days=3)).isoformat().replace("+00:00", "Z")
    older = (now - timedelta(days=20)).isoformat().replace("+00:00", "Z")
    too_old = (now - timedelta(days=SOURCE_LOOKBACK_DAYS + 2)).isoformat().replace("+00:00", "Z")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"title": "Older API latency debugging", "url": "https://dev.to/older", "published_at": older, "tag_list": ["api", "performance"]},
                {"title": "Too old API latency debugging", "url": "https://dev.to/old", "published_at": too_old, "tag_list": ["api", "performance"]},
                {"title": "Newest API latency debugging", "url": "https://dev.to/new", "published_at": newest, "tag_list": ["api", "performance"]},
            ]

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params):
            return FakeResponse()

    monkeypatch.setattr("sources.httpx.AsyncClient", FakeClient)

    articles = asyncio.run(search_dev_articles(["API latency"], ["api"], lookback_days=SOURCE_LOOKBACK_DAYS))

    assert [article.url for article in articles] == ["https://dev.to/new", "https://dev.to/older"]


def test_dev_article_detail_normalization_includes_body_excerpt():
    article = normalize_dev_article(
        {
            "id": 123,
            "path": "/author/debugging-api-latency",
            "title": "Debugging API latency in production",
            "url": "https://dev.to/api-latency",
            "body_markdown": "# Debugging API latency\n\nUse traces, request timing, and ISP checks.",
            "tag_list": ["api", "performance"],
        }
    )

    assert article.id == 123
    assert article.path == "/author/debugging-api-latency"
    assert article.body_excerpt == "Debugging API latency Use traces, request timing, and ISP checks."


def test_dev_filter_requires_meaningful_overlap():
    articles = [
        DEVArticle(title="Generic web app ideas", url="https://dev.to/web", tags=["webdev"]),
        DEVArticle(
            title="Debugging API latency in production",
            url="https://dev.to/api",
            tags=["api", "performance"],
        ),
    ]

    filtered = filter_dev_articles(articles, ["API latency"], ["api"])

    assert [article.url for article in filtered] == ["https://dev.to/api"]


def test_fallback_report_uses_topic_specific_dev_links_without_repeating_all_links():
    context = CompanyContext(
        company_name="raah.dev",
        product="web analytics and network observability tool",
        audience="backend engineers",
        seed_keywords=["api latency", "core web vitals"],
    )
    hn_signals = [
        *fallback_hn_signals(
            [
                HNItem(
                    title="API latency debugging",
                    text="API latency spikes by ISP",
                    url="https://news.ycombinator.com/item?id=1",
                    source_type="story",
                ),
                HNItem(
                    title="Core Web Vitals monitoring",
                    text="LCP and INP regressions are hard to debug in production",
                    url="https://news.ycombinator.com/item?id=2",
                    source_type="story",
                ),
            ]
        )
    ]
    gaps = [
        ContentGap(
            topic="Debugging API latency from user sessions",
            demand_score=90,
            supply_gap_score=80,
            memory_novelty_score=100,
            total_score=88,
            why_it_matters="HN developers ask about API latency debugging.",
            supply_gap="DEV articles miss user-session debugging.",
            recommended_asset_type="tutorial",
            demand_evidence=["https://news.ycombinator.com/item?id=1"],
        ),
        ContentGap(
            topic="Core Web Vitals debugging and performance monitoring",
            demand_score=85,
            supply_gap_score=80,
            memory_novelty_score=100,
            total_score=84,
            why_it_matters="HN developers ask about Core Web Vitals.",
            supply_gap="DEV articles miss production monitoring.",
            recommended_asset_type="tutorial",
            demand_evidence=["https://news.ycombinator.com/item?id=2"],
        ),
    ]
    dev_articles = [
        DEVArticle(
            title="Debugging API latency in production",
            url="https://dev.to/api-latency",
            tags=["api", "performance"],
            description="Trace slow requests and latency spikes by user session.",
        ),
        DEVArticle(
            title="Core Web Vitals monitoring for production sites",
            url="https://dev.to/core-web-vitals",
            tags=["webperf", "performance"],
            description="Monitor LCP, CLS, and INP regressions in production.",
        ),
    ]

    report = fallback_ideation_report(context, hn_signals, gaps, [], dev_articles)

    assert report.content_ideas[0].dev_links == ["https://dev.to/api-latency"]
    assert report.content_ideas[1].dev_links == ["https://dev.to/core-web-vitals"]
    assert report.content_ideas[0].dev_links != report.content_ideas[1].dev_links


def test_pgvector_fallback_stays_on_vector_search_topics():
    context = CompanyContext(
        company_name="pgvector",
        product="Postgres extension for vector search and AI retrieval",
        audience="backend engineers and platform teams building RAG systems",
        seed_keywords=[
            "indexing",
            "query latency",
            "hybrid search",
            "embeddings",
            "migrations",
            "production debugging",
        ],
    )
    hn_items = [
        HNItem(
            title="Core Web Vitals monitoring",
            text="LCP and INP regressions are hard to debug",
            url="https://news.ycombinator.com/item?id=web",
            source_type="story",
        ),
        HNItem(
            title="Vector search indexing in Postgres",
            text="pgvector HNSW indexing and query latency are hard in production RAG systems",
            url="https://news.ycombinator.com/item?id=vector",
            source_type="story",
        ),
    ]
    hn_signals = fallback_hn_signals(hn_items)
    content_gaps = fallback_content_gaps(
        hn_signals,
        [],
        [],
        seed_keywords=context.seed_keywords,
    )
    report = fallback_ideation_report(
        context,
        hn_signals,
        content_gaps,
        [],
        [
            DEVArticle(
                title="pgvector HNSW indexing guide",
                url="https://dev.to/pgvector-indexing",
                tags=["postgres", "ai"],
                description="Tune HNSW indexes and query latency for vector search.",
            )
        ],
    )

    titles = " ".join(idea.title.lower() for idea in report.content_ideas)
    assert "core web vitals" not in titles
    assert len(report.content_ideas) == 5
    assert any(
        term in titles
        for term in ("vector search", "rag retrieval", "query latency", "hybrid search", "migration")
    )


def test_raah_fallback_does_not_include_stale_pgvector_topics():
    context = CompanyContext(
        company_name="raah.dev",
        product="web analytics and network observability tool",
        audience="backend engineers",
        seed_keywords=["api latency", "error rates", "network debugging"],
    )
    gaps = [
        ContentGap(
            topic="Debugging vector query latency in production",
            demand_score=90,
            supply_gap_score=80,
            memory_novelty_score=100,
            total_score=90,
            why_it_matters="Old pgvector memory.",
            supply_gap="Old vector supply gap.",
            recommended_asset_type="tutorial",
        ),
        ContentGap(
            topic="Debugging API latency from user sessions",
            demand_score=85,
            supply_gap_score=80,
            memory_novelty_score=100,
            total_score=86,
            why_it_matters="Raah-relevant latency debugging.",
            supply_gap="DEV articles miss user-session debugging.",
            recommended_asset_type="tutorial",
        ),
    ]

    report = fallback_ideation_report(context, [], gaps, [])

    titles = " ".join(idea.title.lower() for idea in report.content_ideas)
    assert "vector query" not in titles
    assert "api latency" in titles


def test_markdown_report_includes_evidence_links_and_not_full_article():
    context = CompanyContext(
        company_name="raah.dev",
        product="web analytics and network observability tool",
        audience="backend engineers",
        seed_keywords=["api latency"],
    )
    hn_signal = HNItem(
        title="API latency debugging",
        text="API latency spikes by ISP",
        url="https://news.ycombinator.com/item?id=123",
        source_type="story",
    )
    signals = fallback_hn_signals([hn_signal])
    gaps = [
        ContentGap(
            topic="Debugging API latency from user sessions",
            demand_score=90,
            supply_gap_score=80,
            memory_novelty_score=100,
            total_score=88,
            why_it_matters="HN developers ask about API latency debugging.",
            supply_gap="DEV articles miss operational workflows.",
            recommended_asset_type="tutorial",
            demand_evidence=["https://news.ycombinator.com/item?id=123"],
        )
    ]
    dev_article = DEVArticle(
        title="Debugging API latency in production",
        url="https://dev.to/api-latency",
        tags=["api", "performance"],
        description="Trace slow requests and latency spikes by user session.",
    )
    report = fallback_ideation_report(context, signals, gaps, [], [dev_article])

    markdown = render_markdown(
        report,
        build_source_title_lookup([hn_signal], [dev_article]),
    )

    assert "Developer Trend Digest" in markdown
    assert "Recommended Talk & Blog Ideas" in markdown
    assert "[API latency debugging](https://news.ycombinator.com/item?id=123)" in markdown
    assert "[Debugging API latency in production](https://dev.to/api-latency)" in markdown
    assert "## Full article" not in markdown
    assert len(markdown) < 12000


def test_report_payload_normalization_ignores_extra_llm_fields():
    payload = {
        "company": "Acme",
        "summary": "Evidence-backed report.",
        "trend_digest": [
            {
                "rank": 1,
                "topic": "Speculative decoding",
                "why_trending": "HN discussion",
                "intensity_score": 80,
                "dev_saturation": "Sparse",
                "unexpected": "ignored",
            }
        ],
        "content_ideas": [
            {
                "rank": 1,
                "title": "How to evaluate draft models",
                "format": "tutorial",
                "angle": "Show evaluation workflow.",
                "outline": ["Problem", "Demo"],
                "score": 82,
                "confidence": "High",
                "extra": "ignored",
            }
        ],
    }

    normalized = _normalize_report_payload(payload)

    assert "rank" not in normalized["content_ideas"][0]
    assert "extra" not in normalized["content_ideas"][0]
    assert "unexpected" not in normalized["trend_digest"][0]


def test_report_payload_normalization_accepts_nested_report_and_recommendations():
    payload = {
        "report": {
            "company": "Velt",
            "summary": "Collaboration SDK opportunities.",
            "recommendations": [
                {
                    "rank": 1,
                    "topic": "React collaboration comments",
                    "format": "tutorial",
                    "rationale": "Developers need implementation detail.",
                    "sections": ["Model permissions", "Wire comments"],
                    "priority_score": 78,
                    "dev_supply_gap": "Few production guides.",
                }
            ],
        }
    }

    normalized = _normalize_report_payload(payload)

    assert normalized["company"] == "Velt"
    assert normalized["content_ideas"][0]["title"] == "React collaboration comments"
    assert normalized["content_ideas"][0]["outline"] == ["Model permissions", "Wire comments"]
    assert normalized["trend_digest"][0]["topic"] == "React collaboration comments"


def test_nebius_provider_uses_agno_nebius():
    model = build_model(
        Settings(
            nebius_api_key="test-key",
            nebius_model="zai-org/GLM-5.2",
            nebius_base_url="https://api.tokenfactory.nebius.com/v1/",
        )
    )

    assert model.__class__.__name__ == "Nebius"
    assert model.id == "zai-org/GLM-5.2"
