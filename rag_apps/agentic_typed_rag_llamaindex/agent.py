"""LlamaIndex FunctionAgent, typed retrieval tool, and grounding guardrails."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.llms import LLM
from llama_index.core.tools import FunctionTool
from pydantic import BaseModel, Field, field_validator, model_validator

from rag import KnowledgeBase, nebius_api_base


DEFAULT_MIN_RELEVANCE = 0.3
DEFAULT_MODEL = "MiniMaxAI/MiniMax-M3"
REFUSAL_TEXT = (
    "I do not have enough evidence in the indexed sources to answer that question."
)


class Citation(BaseModel):
    """An exact quote that connects an answer to one stored chunk."""

    source: str = Field(description="Source document name or URL")
    chunk_id: str = Field(description="Stable identifier returned by retrieve")
    quoted_span: str = Field(description="Short verbatim quote from the chunk")

    @field_validator("source", "chunk_id", "quoted_span")
    @classmethod
    def values_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("citation values must not be blank")
        return value


def _coerce_answered(value) -> bool | None:
    """Normalize LLM booleans that may arrive as strings in tool calls."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"false", "0", "no"}:
            return False
        if normalized in {"true", "1", "yes"}:
            return True
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    return None


class Answer(BaseModel):
    """Validated output rendered by the Streamlit app."""

    text: str
    citations: list[Citation]
    confidence: float = Field(ge=0.0, le=1.0)
    answered: bool

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_payload(cls, value):
        """Coerce common malformed structured-output payloads from tool calls."""
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        answered = _coerce_answered(payload.get("answered"))
        if answered is not None:
            payload["answered"] = answered

        text = str(payload.get("text") or "").strip()
        if not text and answered is False:
            payload["text"] = REFUSAL_TEXT
        elif text:
            payload["text"] = text

        if payload.get("citations") is None:
            payload["citations"] = []
        if answered is False:
            payload["citations"] = []

        confidence = payload.get("confidence")
        if confidence is None:
            payload["confidence"] = 0.0
        else:
            try:
                payload["confidence"] = float(confidence)
            except (TypeError, ValueError):
                payload["confidence"] = 0.0

        return payload

    @model_validator(mode="after")
    def answer_and_citations_must_agree(self) -> "Answer":
        if self.answered and not self.citations:
            raise ValueError("answered responses require at least one citation")
        if not self.answered and self.citations:
            return self.model_copy(update={"citations": []})
        return self

    @classmethod
    def insufficient_evidence(cls, top_score: float = 0.0) -> "Answer":
        return cls(
            text=REFUSAL_TEXT,
            citations=[],
            confidence=round(min(max(top_score, 0.0), 1.0), 3),
            answered=False,
        )


class RetrievedChunk(BaseModel):
    """A serializable chunk returned by the retrieve tool."""

    source: str
    chunk_id: str
    text: str
    score: float = Field(ge=0.0, le=1.0)


class RetrievalEvidence(BaseModel):
    """The typed result of one vector search."""

    query: str
    enough_evidence: bool
    top_score: float = Field(ge=0.0, le=1.0)
    chunks: list[RetrievedChunk]


@dataclass
class RagDependencies:
    """Per-run resources shared by the preflight gate and the retrieve tool."""

    kb: KnowledgeBase
    min_relevance: float = DEFAULT_MIN_RELEVANCE
    top_k: int = 4


AGENT_INSTRUCTIONS = """
You answer questions only from evidence returned by the retrieve tool.

Rules:
1. Always call retrieve before producing the final output.
2. If retrieve returns enough_evidence=false, set answered=false, use no citations,
   and say that the indexed sources do not contain enough evidence.
3. If enough_evidence=true, answer from the returned chunks and set answered=true.
4. Include at least one citation for every answered response.
5. Every citation must copy source and chunk_id exactly from retrieve.
6. quoted_span must be a short verbatim substring of that chunk's text.
7. confidence is a number from 0 to 1. Lower it when evidence is partial.
8. Never use background knowledge to fill a gap in the sources.
""".strip()


def resolve_model_name() -> str:
    """Resolve the Nebius model from the environment, with a sane default."""
    return os.getenv("RAG_MODEL", "").strip() or DEFAULT_MODEL


def build_llm(model: str | None = None, api_key: str | None = None) -> LLM:
    """Create a Nebius Token Factory LLM with tool calling enabled."""
    from llama_index.llms.nebius import NebiusLLM

    api_key = api_key or os.getenv("NEBIUS_API_KEY", "")
    if not api_key:
        raise RuntimeError("Set NEBIUS_API_KEY before asking a question")
    return NebiusLLM(
        model=model or resolve_model_name(),
        api_key=api_key,
        api_base=nebius_api_base(),
        is_function_calling_model=True,
        temperature=0.0,
    )


def retrieve_evidence(deps: RagDependencies, query: str) -> RetrievalEvidence:
    """Search the knowledge base and expose the relevance decision as typed data."""
    results = deps.kb.search(query, limit=deps.top_k)
    top_score = results[0].score if results else 0.0
    return RetrievalEvidence(
        query=query,
        enough_evidence=bool(results and top_score >= deps.min_relevance),
        top_score=top_score,
        chunks=[
            RetrievedChunk(
                source=result.chunk.source,
                chunk_id=result.chunk.chunk_id,
                text=result.chunk.text,
                score=result.score,
            )
            for result in results
        ],
    )


def build_agent(
    deps: RagDependencies,
    llm: LLM,
    evidence_log: list[RetrievalEvidence],
    question: str,
) -> FunctionAgent:
    """Build a FunctionAgent whose retrieve tool records every search it runs."""

    def retrieve(query: str) -> str:
        """Retrieve source chunks relevant to the user's question."""
        del query  # Always search with the original user question for stable recall.
        evidence = retrieve_evidence(deps, question)
        evidence_log.append(evidence)
        return evidence.model_dump_json(indent=2)

    return FunctionAgent(
        tools=[FunctionTool.from_defaults(fn=retrieve, name="retrieve")],
        llm=llm,
        system_prompt=AGENT_INSTRUCTIONS,
        output_cls=Answer,
    )


def _normalize_quote(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip().casefold()
    value = re.sub(r"[|*_`~]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _quote_matches_chunk(quoted_span: str, chunk_text: str) -> bool:
    quote = _normalize_quote(quoted_span)
    body = _normalize_quote(chunk_text)
    if len(quote) < 6:
        return False
    if quote in body:
        return True

    quote_words = quote.split()
    if len(quote_words) < 2:
        return quote in body

    pattern = r"\s+".join(re.escape(word) for word in quote_words)
    return re.search(pattern, body) is not None


def _valid_citations(answer: Answer, deps: RagDependencies) -> list[Citation]:
    valid = []
    for citation in answer.citations:
        chunk = deps.kb.find_chunk(citation.source, citation.chunk_id)
        if chunk and _quote_matches_chunk(citation.quoted_span, chunk.text):
            valid.append(citation)
    return valid


def validate_grounded_answer(
    answer: Answer,
    deps: RagDependencies,
    preflight: RetrievalEvidence,
    *,
    used_retrieve: bool,
) -> Answer:
    """Refuse outputs that skipped retrieval or cite text outside the store."""
    if not answer.answered:
        return Answer.insufficient_evidence(preflight.top_score)
    if not used_retrieve:
        return Answer.insufficient_evidence(preflight.top_score)

    citations = _valid_citations(answer, deps)
    if not citations:
        return Answer.insufficient_evidence(preflight.top_score)
    return answer.model_copy(update={"citations": citations})


async def answer_question(
    question: str,
    deps: RagDependencies,
    model: str | None = None,
    llm: LLM | None = None,
) -> Answer:
    """Run the typed agent only after a deterministic retrieval gate."""
    question = question.strip()
    if not question:
        raise ValueError("question must not be empty")

    preflight = retrieve_evidence(deps, question)
    if not preflight.enough_evidence:
        return Answer.insufficient_evidence(preflight.top_score)

    evidence_log: list[RetrievalEvidence] = []
    agent = build_agent(deps, llm or build_llm(model), evidence_log, question)
    output = await agent.run(question)

    structured = output.structured_response
    if structured is None:
        return Answer.insufficient_evidence(preflight.top_score)
    answer = structured if isinstance(structured, Answer) else Answer.model_validate(structured)
    return validate_grounded_answer(
        answer,
        deps,
        preflight,
        used_retrieve=bool(evidence_log),
    )
