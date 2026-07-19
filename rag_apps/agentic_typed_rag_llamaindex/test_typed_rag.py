#!/usr/bin/env python3
"""Deterministic tests for the typed agentic RAG example.

The suite uses a local hashing embedding, so it makes no Nebius requests.
"""

import asyncio
import hashlib
import json
import math
import os
import re
import unittest
from unittest.mock import patch

from llama_index.core.embeddings import BaseEmbedding

from rag import (
    KnowledgeBase,
    chunk_text,
    html_to_text,
    ingest_document,
    validate_public_url,
)
from agent import (
    Answer,
    Citation,
    RagDependencies,
    RetrievalEvidence,
    answer_question,
    build_agent,
    resolve_model_name,
    retrieve_evidence,
    validate_grounded_answer,
)


_STOP_WORDS = {"a", "an", "and", "are", "do", "how", "is", "of", "the", "what", "who"}


class HashingEmbedding(BaseEmbedding):
    """Offline embedding that maps normalized terms into a fixed vector."""

    dimensions: int = 512

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", text.casefold())
            if token not in _STOP_WORDS
        ]
        for term in tokens + [f"{a}:{b}" for a, b in zip(tokens, tokens[1:])]:
            digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
            position = int.from_bytes(digest, "big") % self.dimensions
            vector[position] += 1.0 if digest[0] & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._embed(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._embed(text)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._embed(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._embed(text)


class TypedRagTests(unittest.TestCase):
    def run_async(self, awaitable):
        return asyncio.run(awaitable)

    def make_kb(self):
        return KnowledgeBase(HashingEmbedding())

    def make_pdf(self, text):
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content = f"BT /F1 12 Tf 72 100 Td ({escaped}) Tj ET".encode("ascii")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
                b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ),
            b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        payload = b"%PDF-1.4\n"
        offsets = [0]
        for number, value in enumerate(objects, start=1):
            offsets.append(len(payload))
            payload += b"%d 0 obj\n" % number + value + b"\nendobj\n"
        xref_offset = len(payload)
        payload += b"xref\n0 6\n0000000000 65535 f \n"
        payload += b"".join(b"%010d 00000 n \n" % offset for offset in offsets[1:])
        payload += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        return payload + str(xref_offset).encode("ascii") + b"\n%%EOF\n"

    def test_chunk_text_produces_bounded_windows(self):
        text = " ".join(f"word{number}" for number in range(400))
        chunks = chunk_text(text, chunk_size=100, overlap=20)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.split()), 100)
        self.assertEqual(" ".join(c for c in chunks[:1])[:5], "word0")

    def test_knowledge_base_ranks_relevant_evidence(self):
        kb = self.make_kb()
        kb.add_document(
            "handbook.pdf",
            "Employees receive twelve weeks of paid parental leave after six months of service.",
        )
        kb.add_document(
            "astronomy.pdf",
            "Europa is an icy moon of Jupiter with a subsurface ocean.",
        )

        relevant = kb.search("How much parental leave do employees receive?")
        unrelated = kb.search("What is the production database password?")

        self.assertEqual("handbook.pdf", relevant[0].chunk.source)
        self.assertGreater(relevant[0].score, 0.2)
        self.assertLess(unrelated[0].score, 0.2)

    def test_retrieve_evidence_reports_threshold_decision(self):
        kb = self.make_kb()
        kb.add_document(
            "policy.pdf",
            "Expense reports must be submitted within thirty days of travel.",
        )
        deps = RagDependencies(kb=kb, min_relevance=0.2, top_k=3)

        grounded = retrieve_evidence(deps, "When are expense reports due?")
        missing = retrieve_evidence(deps, "Who won the 1978 World Cup?")

        self.assertTrue(grounded.enough_evidence)
        self.assertFalse(missing.enough_evidence)
        self.assertEqual("policy.pdf", grounded.chunks[0].source)

    def test_pdf_text_is_extracted_and_indexed(self):
        kb = self.make_kb()
        added = ingest_document(
            kb,
            "policy.pdf",
            self.make_pdf("Travel receipts are required within thirty days."),
        )
        results = kb.search("When are travel receipts required?")

        self.assertEqual(1, added)
        self.assertEqual("policy.pdf:p1:c1", results[0].chunk.chunk_id)
        self.assertGreater(results[0].score, 0.2)

    def test_answer_model_requires_citations_when_answered(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            Answer(text="Unsupported", citations=[], confidence=0.8, answered=True)

        with self.assertRaises(ValidationError):
            Answer(
                text="Too confident",
                citations=[Citation(source="x", chunk_id="x:c1", quoted_span="quote")],
                confidence=1.2,
                answered=True,
            )

    def test_refusal_discards_model_supplied_citations(self):
        refusal = Answer.model_validate(
            {
                "text": "The indexed sources do not contain enough evidence.",
                "citations": [
                    {
                        "source": "policy.pdf",
                        "chunk_id": "policy.pdf:p1:c1",
                        "quoted_span": "This quote must not survive a refusal.",
                    }
                ],
                "confidence": 0.4,
                "answered": False,
            }
        )

        self.assertFalse(refusal.answered)
        self.assertEqual([], refusal.citations)

    def test_refusal_discards_citations_when_answered_is_string_false(self):
        refusal = Answer.model_validate(
            {
                "text": "The indexed sources do not contain enough evidence.",
                "citations": [
                    {
                        "source": "policy.pdf",
                        "chunk_id": "policy.pdf:p1:c1",
                        "quoted_span": "This quote must not survive a refusal.",
                    }
                ],
                "confidence": 0.4,
                "answered": "false",
            }
        )

        self.assertFalse(refusal.answered)
        self.assertEqual([], refusal.citations)

    def test_refusal_fills_blank_text_from_structured_output(self):
        refusal = Answer.model_validate(
            {
                "text": "",
                "citations": [],
                "confidence": 0.48,
                "answered": False,
            }
        )

        self.assertFalse(refusal.answered)
        self.assertIn("enough evidence", refusal.text.lower())

    def test_refusal_accepts_direct_constructor_with_citations(self):
        refusal = Answer(
            text="The indexed sources do not contain enough evidence.",
            citations=[
                Citation(
                    source="policy.pdf",
                    chunk_id="policy.pdf:p1:c1",
                    quoted_span="This quote must not survive a refusal.",
                )
            ],
            confidence=0.4,
            answered=False,
        )

        self.assertFalse(refusal.answered)
        self.assertEqual([], refusal.citations)

    def test_out_of_corpus_question_refuses_without_model_request(self):
        kb = self.make_kb()
        kb.add_document(
            "benefits.pdf",
            "Dental coverage begins on the first day of employment.",
        )
        deps = RagDependencies(kb=kb, min_relevance=0.2, top_k=3)

        # No NEBIUS_API_KEY is set, so reaching the LLM would raise instead.
        with patch.dict(os.environ, {}, clear=True):
            answer = self.run_async(
                answer_question("How do I configure a Kubernetes ingress?", deps)
            )

        self.assertFalse(answer.answered)
        self.assertEqual([], answer.citations)
        self.assertIn("enough evidence", answer.text.lower())

    def test_retrieve_tool_returns_typed_evidence_and_logs_calls(self):
        from llama_index.core.llms import MockLLM

        kb = self.make_kb()
        kb.add_document(
            "atlas-handbook.pdf",
            "The Atlas handbook grants twelve weeks of paid parental leave.",
        )
        deps = RagDependencies(kb=kb, min_relevance=0.2, top_k=3)
        evidence_log = []
        agent = build_agent(
            deps,
            MockLLM(),
            evidence_log,
            "How much parental leave does Atlas grant?",
        )

        tool = next(t for t in agent.tools if t.metadata.name == "retrieve")
        payload = json.loads(tool.fn("How much parental leave does Atlas grant?"))
        evidence = RetrievalEvidence.model_validate(payload)

        self.assertEqual(1, len(evidence_log))
        self.assertTrue(evidence.enough_evidence)
        self.assertEqual("atlas-handbook.pdf", evidence.chunks[0].source)
        self.assertEqual(Answer, agent.output_cls)

    def test_valid_citation_survives_grounding_check(self):
        kb = self.make_kb()
        kb.add_document(
            "atlas-handbook.pdf",
            "The Atlas handbook grants twelve weeks of paid parental leave.",
        )
        chunk = kb.chunks[0]
        deps = RagDependencies(kb=kb, min_relevance=0.2, top_k=3)
        preflight = retrieve_evidence(deps, "How much parental leave does Atlas grant?")
        answer = Answer(
            text="Atlas grants twelve weeks of paid parental leave.",
            citations=[
                Citation(
                    source=chunk.source,
                    chunk_id=chunk.chunk_id,
                    quoted_span="twelve weeks of paid parental leave",
                )
            ],
            confidence=0.91,
            answered=True,
        )

        validated = validate_grounded_answer(
            answer, deps, preflight, used_retrieve=True
        )

        self.assertTrue(validated.answered)
        self.assertEqual("atlas-handbook.pdf", validated.citations[0].source)

    def test_forged_citation_forces_refusal(self):
        kb = self.make_kb()
        kb.add_document(
            "travel.pdf",
            "The meal allowance is seventy dollars per day.",
        )
        chunk = kb.chunks[0]
        deps = RagDependencies(kb=kb, min_relevance=0.2, top_k=3)
        preflight = retrieve_evidence(deps, "What is the daily meal allowance?")
        forged = Answer(
            text="The allowance is one hundred dollars.",
            citations=[
                Citation(
                    source=chunk.source,
                    chunk_id=chunk.chunk_id,
                    quoted_span="one hundred dollars per day",
                )
            ],
            confidence=0.95,
            answered=True,
        )

        answer = validate_grounded_answer(forged, deps, preflight, used_retrieve=True)
        skipped = validate_grounded_answer(
            forged, deps, preflight, used_retrieve=False
        )

        self.assertFalse(answer.answered)
        self.assertEqual([], answer.citations)
        self.assertFalse(skipped.answered)

    def test_model_resolution_honors_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                "MiniMaxAI/MiniMax-M3", resolve_model_name()
            )
        with patch.dict(os.environ, {"RAG_MODEL": "zai-org/GLM-4.5"}, clear=True):
            self.assertEqual("zai-org/GLM-4.5", resolve_model_name())

    def test_html_to_text_ignores_scripts_and_styles(self):
        html = """
        <html><head><style>.hidden { display: none; }</style></head>
        <body><h1>Policy</h1><p>Travel receipts are required.</p>
        <script>window.secret = 'ignore';</script></body></html>
        """
        text = html_to_text(html)

        self.assertIn("Policy", text)
        self.assertIn("Travel receipts are required.", text)
        self.assertNotIn("window.secret", text)
        self.assertNotIn("display: none", text)

    def test_private_docs_urls_are_rejected(self):
        private_urls = (
            "http://localhost/docs",
            "http://127.0.0.1/admin",
            "http://[::1]/admin",
            "http://169.254.169.254/latest/meta-data",
            "http://10.0.0.4/internal",
        )
        for url in private_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_public_url(url)


if __name__ == "__main__":
    unittest.main(verbosity=2)
