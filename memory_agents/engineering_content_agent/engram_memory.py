"""Weaviate Engram Memory adapter."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from models import CompanyContext, ContentGap, IdeationReport

logger = logging.getLogger(__name__)


@dataclass
class MemoryRecord:
    content: str
    score: float = 1.0


@dataclass
class MemoryStoreResult:
    ok: bool
    run_id: str | None = None
    status: str | None = None
    error: str | None = None
    created_count: int = 0
    updated_count: int = 0


class MemoryStore:
    persistent: bool = False
    group: str = "default"

    async def search(self, query: str, user_id: str, limit: int = 5) -> list[MemoryRecord]:
        raise NotImplementedError

    async def store_research_summary(
        self,
        context: CompanyContext,
        report: IdeationReport,
        content_gaps: list[ContentGap],
        user_id: str,
    ) -> list[str]:
        raise NotImplementedError

    async def store_product_context(self, context: CompanyContext, user_id: str) -> list[str]:
        raise NotImplementedError


class DisabledMemoryStore(MemoryStore):
    """No local memory fallback; used only when Engram is not configured."""

    persistent = False
    group = "disabled"

    async def search(self, query: str, user_id: str, limit: int = 5) -> list[MemoryRecord]:
        return []

    async def store_research_summary(
        self,
        context: CompanyContext,
        report: IdeationReport,
        content_gaps: list[ContentGap],
        user_id: str,
    ) -> list[str]:
        return ["Engram Memory disabled; no research summary stored."]

    async def store_product_context(self, context: CompanyContext, user_id: str) -> list[str]:
        return []


def _format_list(items: list[str], limit: int = 6) -> str:
    cleaned = [item.strip() for item in items if item.strip()]
    if not cleaned:
        return "none recorded"
    return ", ".join(cleaned[:limit])


def build_product_context_memory(context: CompanyContext) -> str:
    company = context.company_name or context.product or "Unknown company"
    product = context.product or company
    lines = [
        f"Product context for {company}.",
        f"Product/category: {product}.",
        f"Audience: {context.audience or 'not specified'}.",
        f"Seed keywords: {_format_list(context.seed_keywords)}.",
    ]
    if context.competitors:
        lines.append(f"Competitors/alternatives: {_format_list(context.competitors)}.")
    if context.existing_topics:
        lines.append(f"Existing topics: {_format_list(context.existing_topics)}.")
    return " ".join(lines)


def build_research_summary_memory(
    context: CompanyContext,
    report: IdeationReport,
    content_gaps: list[ContentGap],
) -> str:
    company = report.company or context.company_name or context.product or "Unknown company"
    product = context.product or company
    summary_text = " ".join(report.summary.split())
    if len(summary_text) > 220:
        summary_text = summary_text[:217].rstrip() + "..."

    lines = [
        f"Research summary for {company} ({product}).",
        f"Audience: {context.audience or 'not specified'}.",
        f"Seed keywords: {_format_list(context.seed_keywords)}.",
        f"Report summary: {summary_text}",
    ]

    if report.trend_digest:
        lines.append("Top developer trends:")
        for index, trend in enumerate(report.trend_digest[:3], 1):
            topic = trend.topic[:100]
            lines.append(f"{index}. {topic} (intensity {trend.intensity_score}).")

    if report.content_ideas:
        lines.append("Top talk/blog ideas:")
        for index, idea in enumerate(report.content_ideas[:3], 1):
            title = idea.title[:100]
            lines.append(f"{index}. {title} ({idea.format}, score {idea.score}).")

    if content_gaps:
        lines.append("Key demand and supply gaps:")
        for gap in content_gaps[:3]:
            topic = gap.topic[:80]
            lines.append(
                f"- {topic}: demand {gap.demand_score}, supply gap {gap.supply_gap_score}."
            )

    content = " ".join(lines)
    if len(content) > 1800:
        content = content[:1797].rstrip() + "..."
    return content


def build_research_summary_preview(
    context: CompanyContext,
    report: IdeationReport,
    content_gaps: list[ContentGap],
) -> str:
    """Short markdown preview of what was stored in Engram (not the full record)."""
    lines: list[str] = []
    if report.trend_digest:
        lines.append("**Trends stored:**")
        for trend in report.trend_digest[:3]:
            lines.append(f"- {trend.topic} (intensity {trend.intensity_score})")
    if report.content_ideas:
        if lines:
            lines.append("")
        lines.append("**Ideas stored:**")
        for idea in report.content_ideas[:3]:
            lines.append(f"- {idea.title} ({idea.format}, score {idea.score})")
    if content_gaps and not report.trend_digest:
        if lines:
            lines.append("")
        lines.append("**Gap topics stored:**")
        for gap in content_gaps[:3]:
            lines.append(f"- {gap.topic}")
    if not lines:
        lines.append(f"Summary for {report.company or context.company_name or context.product}.")
    return "\n".join(lines)


class EngramMemoryStore(MemoryStore):
    persistent = True

    def __init__(
        self,
        api_key: str,
        group: str = "default",
        conversation_id: str | None = None,
    ) -> None:
        from engram import AsyncEngramClient, HybridRetrieval, PreExtractedInput, PreExtractedItem

        self.api_key = api_key
        self.client_factory = AsyncEngramClient
        self.retrieval_factory = HybridRetrieval
        self.preextracted_input_factory = PreExtractedInput
        self.preextracted_item_factory = PreExtractedItem
        self.group = group or "default"
        self.conversation_id = conversation_id
        self._client: Any | None = None
        self._client_loop_id: int | None = None

    def _get_client(self) -> Any:
        loop_id = id(asyncio.get_running_loop())
        if self._client is None or self._client_loop_id != loop_id:
            self._client = self.client_factory(api_key=self.api_key)
            self._client_loop_id = loop_id
        return self._client

    def _properties(self) -> dict[str, str] | None:
        if self.conversation_id:
            return {"conversation_id": self.conversation_id}
        return None

    async def _add_memory(self, content: str, user_id: str) -> MemoryStoreResult:
        kwargs: dict[str, Any] = {}
        properties = self._properties()
        if properties:
            kwargs["properties"] = properties
        try:
            client = self._get_client()
            input_data = self.preextracted_input_factory(
                items=[
                    self.preextracted_item_factory(
                        content=content,
                        topic="UserKnowledge",
                    )
                ]
            )
            run = await client.memories.add(
                input_data,
                user_id=user_id,
                group=self.group,
                **kwargs,
            )
            run_id = getattr(run, "run_id", None)
            status = getattr(run, "status", None)
            if run_id:
                try:
                    run_status = await client.runs.wait(run_id, timeout=20.0, interval=1.0)
                    status = getattr(run_status, "status", status)
                    error = getattr(run_status, "error", None)
                    return MemoryStoreResult(
                        ok=not error and str(status).lower() not in {"failed", "error"},
                        run_id=run_id,
                        status=status,
                        error=error,
                        created_count=len(getattr(run_status, "memories_created", []) or []),
                        updated_count=len(getattr(run_status, "memories_updated", []) or []),
                    )
                except Exception as wait_exc:
                    logger.info("Engram Memory run %s still processing or unavailable: %s", run_id, wait_exc)
                    return MemoryStoreResult(ok=True, run_id=run_id, status=status or "queued")
            return MemoryStoreResult(ok=True, status=status)
        except Exception as exc:
            logger.warning("Engram Memory store failed for user %s: %s", user_id, exc)
            return MemoryStoreResult(ok=False, error=str(exc))

    async def search(self, query: str, user_id: str, limit: int = 5) -> list[MemoryRecord]:
        try:
            client = self._get_client()
            results = await client.memories.search(
                query=query,
                user_id=user_id,
                group=self.group,
                retrieval_config=self.retrieval_factory(limit=limit),
            )
        except Exception as exc:
            logger.warning("Engram Memory search unavailable for user %s: %s", user_id, exc)
            return []
        return [
            MemoryRecord(
                content=getattr(memory, "content", str(memory)),
                score=float(getattr(memory, "score", 1.0) or 1.0),
            )
            for memory in results
        ]

    async def store_research_summary(
        self,
        context: CompanyContext,
        report: IdeationReport,
        content_gaps: list[ContentGap],
        user_id: str,
    ) -> list[str]:
        content = build_research_summary_memory(context, report, content_gaps)
        company = report.company or context.company_name or context.product or "this company"
        result = await self._add_memory(content, user_id)
        if result.ok:
            detail = f"Engram run `{result.run_id}`" if result.run_id else "Engram run queued"
            status = f", status `{result.status}`" if result.status else ""
            counts = ""
            if result.created_count or result.updated_count:
                counts = f", created {result.created_count}, updated {result.updated_count}"
            return [f"Stored research summary for {company} ({detail}{status}{counts})."]
        error = f" {result.error}" if result.error else ""
        return [f"Could not store research summary for {company}.{error}"]

    async def store_product_context(self, context: CompanyContext, user_id: str) -> list[str]:
        if not context.company_name.strip() and not context.product.strip():
            return []
        content = build_product_context_memory(context)
        company = context.company_name or context.product
        result = await self._add_memory(content, user_id)
        if result.ok:
            detail = f"Engram run `{result.run_id}`" if result.run_id else "Engram run queued"
            status = f", status `{result.status}`" if result.status else ""
            return [f"Stored product context for {company} ({detail}{status})."]
        error = f" {result.error}" if result.error else ""
        return [f"Could not store product context for {company}.{error}"]


def create_memory_store(
    api_key: str | None,
    namespace: str = "default",
    conversation_id: str | None = None,
) -> MemoryStore:
    if not api_key:
        logger.warning("ENGRAM_API_KEY missing; Engram Memory disabled.")
        return DisabledMemoryStore()
    return EngramMemoryStore(
        api_key=api_key,
        group=namespace,
        conversation_id=conversation_id,
    )
