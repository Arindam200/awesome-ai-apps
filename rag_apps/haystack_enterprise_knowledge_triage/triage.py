"""Enterprise knowledge triage agent built with Haystack pipelines.

Flow: ingest -> classify intent -> retrieve (BM25, intent-scoped) -> rerank ->
confidence gate -> cited answer (or fallback).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Optional

from haystack import Document, Pipeline, component
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.components.writers import DocumentWriter
from haystack.dataclasses import ChatMessage
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.utils import Secret

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_BASE = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"

# Intent -> source files that are authoritative for it.
INTENT_SOURCES = {
    "hr": ["hr_leave_policy.md"],
    "security": ["security_policy.md"],
    "operations": ["incident_runbook.md", "q3_report.md"],
    "finance": ["expense_faq.md"],
}
INTENT_KEYWORDS = {
    "hr": {"leave", "vacation", "sick", "parental", "holiday", "benefit", "hr"},
    "security": {"password", "mfa", "laptop", "encryption", "security", "device", "classification", "phishing"},
    "operations": {"incident", "sev1", "sev2", "sev3", "outage", "rollback", "deploy", "oncall", "postmortem", "availability", "csat", "support", "report", "q3"},
    "finance": {"expense", "expenses", "travel", "receipt", "reimbursement", "meal", "flight", "allowance"},
}
STOP = set("a an the of to is are do i my we in on for and or how what when does can be it with at by from as that this".split())


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


def keyword_intent(question: str) -> str:
    """Deterministic intent classifier, also used when no LLM is configured."""
    q = set(tokens(question))
    scores = {i: len(q & kw) for i, kw in INTENT_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


@component
class IntentScopedFilter:
    """Keep only chunks from sources that belong to the detected intent."""

    @component.output_types(documents=list[Document])
    def run(self, documents: list[Document], intent: str):
        allowed = INTENT_SOURCES.get(intent)
        if not allowed:
            return {"documents": documents}
        scoped = [d for d in documents if d.meta.get("source") in allowed]
        return {"documents": scoped or documents}


@component
class OverlapReranker:
    """Lightweight lexical reranker: query-term coverage + heading match.

    Keeps the example dependency-free (no model download). Swap in any Haystack
    ranker (e.g. SentenceTransformersSimilarityRanker) with the same I/O.
    """

    def __init__(self, top_k: int = 3):
        self.top_k = top_k

    @component.output_types(documents=list[Document])
    def run(self, documents: list[Document], query: str):
        q = set(tokens(query))
        scored = []
        for d in documents:
            body = set(tokens(d.content or ""))
            head = set(tokens(d.meta.get("heading", "")))
            coverage = len(q & body) / len(q) if q else 0.0
            heading = len(q & head) / len(q) if q else 0.0
            scored.append(replace(d, score=round(0.8 * coverage + 0.2 * heading, 4)))
        scored.sort(key=lambda d: d.score, reverse=True)
        return {"documents": scored[: self.top_k]}


def split_by_heading(text: str, source: str) -> list[Document]:
    """One chunk per markdown section so citations point at a heading."""
    docs, title, heading, buf = [], "", "", []

    def flush():
        body = "\n".join(buf).strip()
        if body:
            docs.append(Document(content=body, meta={"source": source, "title": title, "heading": heading or title}))

    for line in text.splitlines():
        if line.startswith("# "):
            flush(); buf.clear(); title = line[2:].strip(); heading = title
        elif line.startswith("## "):
            flush(); buf.clear(); heading = line[3:].strip()
        else:
            buf.append(line)
    flush()
    return docs


def build_ingestion(store: InMemoryDocumentStore) -> Pipeline:
    p = Pipeline()
    p.add_component("splitter", DocumentSplitter(split_by="word", split_length=120, split_overlap=0))
    p.add_component("writer", DocumentWriter(document_store=store))
    p.connect("splitter.documents", "writer.documents")
    return p


def ingest(store: InMemoryDocumentStore, data_dir: Path = DATA_DIR) -> int:
    chunks: list[Document] = []
    for path in sorted(Path(data_dir).glob("*.md")):
        chunks += split_by_heading(path.read_text(encoding="utf-8"), path.name)
    # Oversized sections get split further by the Haystack splitter pipeline.
    build_ingestion(store).run({"splitter": {"documents": chunks}})
    return store.count_documents()


@dataclass
class Answer:
    question: str
    intent: str
    answer: str
    confidence: float
    citations: list[str] = field(default_factory=list)
    fallback: bool = False


LlmFn = Callable[[list[ChatMessage]], str]


def nebius_llm() -> Optional[LlmFn]:
    key = os.getenv("NEBIUS_API_KEY")
    if not key:
        return None
    gen = OpenAIChatGenerator(
        api_key=Secret.from_token(key),
        api_base_url=os.getenv("NEBIUS_API_BASE", DEFAULT_BASE),
        model=os.getenv("TRIAGE_MODEL", DEFAULT_MODEL),
        generation_kwargs={"temperature": 0.1},
    )
    return lambda msgs: gen.run(messages=msgs)["replies"][0].text or ""


class TriageAgent:
    def __init__(self, store: InMemoryDocumentStore, llm: Optional[LlmFn] = None, min_confidence: Optional[float] = None):
        self.llm = llm
        self.min_confidence = float(os.getenv("TRIAGE_MIN_CONFIDENCE", "0.35")) if min_confidence is None else min_confidence
        self.pipeline = Pipeline()
        self.pipeline.add_component("retriever", InMemoryBM25Retriever(document_store=store, top_k=8))
        self.pipeline.add_component("scope", IntentScopedFilter())
        self.pipeline.add_component("reranker", OverlapReranker(top_k=3))
        self.pipeline.connect("retriever.documents", "scope.documents")
        self.pipeline.connect("scope.documents", "reranker.documents")

    def classify(self, question: str) -> str:
        if self.llm:
            prompt = (
                "Classify the question into exactly one of: hr, security, operations, finance, general. "
                'Reply with JSON like {"intent": "hr"}.\nQuestion: ' + question
            )
            try:
                raw = self.llm([ChatMessage.from_user(prompt)])
                intent = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))["intent"].strip().lower()
                if intent in INTENT_SOURCES or intent == "general":
                    return intent
            except Exception:
                pass
        return keyword_intent(question)

    def ask(self, question: str) -> Answer:
        intent = self.classify(question)
        out = self.pipeline.run({
            "retriever": {"query": question},
            "scope": {"intent": intent},
            "reranker": {"query": question},
        })
        docs = out["reranker"]["documents"]
        confidence = docs[0].score if docs else 0.0
        if not docs or confidence < self.min_confidence:
            return Answer(
                question, intent,
                "I couldn't find reliable evidence in the knowledge base for this question. "
                "Please contact the relevant team (HR, Security, Operations or Finance) directly.",
                confidence, [], fallback=True,
            )
        citations = [f"{d.meta['source']} § {d.meta['heading']}" for d in docs]
        if self.llm:
            ctx = "\n\n".join(f"[{i}] ({c})\n{d.content}" for i, (c, d) in enumerate(zip(citations, docs), 1))
            msgs = [
                ChatMessage.from_system(
                    "Answer using ONLY the numbered context. Cite sources inline like [1]. "
                    "If the context does not answer the question, say you don't know."
                ),
                ChatMessage.from_user(f"Context:\n{ctx}\n\nQuestion: {question}"),
            ]
            text = self.llm(msgs)
        else:
            text = f"{docs[0].content.strip()} [1]"
        return Answer(question, intent, text, confidence, citations)


def build_agent(llm: Optional[LlmFn] = None, data_dir: Path = DATA_DIR) -> TriageAgent:
    store = InMemoryDocumentStore()
    ingest(store, data_dir)
    return TriageAgent(store, llm if llm is not None else nebius_llm())
