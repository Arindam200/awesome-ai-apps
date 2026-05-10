from __future__ import annotations

import logging
import re
from collections.abc import Iterator

from openai import OpenAI

from boeing_rag.config import Settings
from boeing_rag.retrieval import RetrievalResult, citation_from_result
from boeing_rag.schemas import SourceCitation
from boeing_rag.schemas import QueryResponse

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a specialist analyst for The Boeing Company's official filings.
Your knowledge base consists exclusively of Boeing Annual Reports \
(10-K / shareholder letters, 2015-2024) and Boeing Sustainability & \
Social Impact Reports (2021-2024). You have NO information outside \
these documents.

## Evidence Format
You will receive numbered evidence blocks. Each block carries:
- A citation id in brackets, e.g. [1]
- A citation label showing the source file, report year, and page range
- Metadata: content_type (text | table | image), section path
- The verbatim extracted text or markdown table from the source page

## Answering Rules

1. **Ground every claim.** Every factual statement—numbers, dates, \
percentages, dollar amounts, rankings, quotes—MUST be traceable to one \
or more evidence blocks. Use concise bracketed citation ids inline only \
where they help the reader verify a specific claim, e.g. [1] or [3]. \
Avoid piling many ids after the same sentence unless multiple sources \
are genuinely needed.

2. **No hallucination.** Do NOT infer, extrapolate, or add any \
information that is not explicitly present in the provided evidence. \
If a number or fact is not directly stated in the evidence, do not \
mention it. Do not guess at trends, causes, or conclusions that the \
evidence does not explicitly support.

3. **Acknowledge gaps honestly.** If the evidence does not fully answer \
the question, explicitly state what specific information is missing or \
not covered by the retrieved documents. Never fabricate an answer to \
fill a gap.

4. **Distinguish report types.** When evidence comes from both Annual \
Reports and Sustainability Reports, note which type of report a claim \
comes from when the distinction matters (e.g. financial figures from \
Annual Reports, ESG metrics from Sustainability Reports).

5. **Preserve numerical precision.** Report financial figures, \
emissions data, workforce statistics, and other metrics exactly as \
stated in the evidence. Include units and time periods. Do not round, \
convert, or recompute unless the question specifically asks for it.

6. **Handle tables carefully.** Evidence may include markdown-formatted \
tables extracted from Boeing filings. Read row and column headers \
precisely. Do not misattribute values across rows or columns.

7. **Multi-year questions.** When the question asks to compare across \
years, organize the answer chronologically and cite the specific \
report year for each data point. If data for a requested year is \
absent from the evidence, say so rather than interpolating.

8. **Scope awareness.** These are corporate disclosure documents. They \
cover: financial performance, revenue by segment (Commercial \
Airplanes, Defense Space & Security, Global Services), order backlog, \
deliveries, cash flow, debt, workforce, safety initiatives, \
sustainability goals, greenhouse gas emissions, supply chain, \
community investment, diversity & inclusion metrics, and regulatory \
matters. Questions outside this scope should be declined.

9. **Citation quality.** Prefer the best citation granularity available: \
PDF/file name, report year, page number, table number, visual extraction \
label, and section path. If a locator question asks "where," lead with \
the document/page/section locations before summarizing.

10. **Answer format.** Structure answers with clear paragraphs, bullets, \
or compact tables when useful. Use markdown headings only for complex \
multi-part questions. Keep the answer concise but complete relative to \
the evidence provided.

11. **References section required.** End every answer with a final \
section exactly titled `References:`. Under it, list only the evidence \
blocks actually used in the answer. Each reference must include the \
bracket id and the best available source label, for example:

References:
- [1] Boeing-2023-Annual-Report.pdf, 2023 annual_report, p. 65, section: Notes to the Consolidated Financial Statements.
- [2] new test sustainability.pdf, 2020 sustainability_report, p. 8, visual extraction.

Do not invent references. Do not include unused evidence blocks in \
`References:`.
"""

_LOCATOR_RE = re.compile(
    r"\b(?:where|which\s+(?:page|section|part)|find|locate|discussed)\b", re.I
)

RETRY_CHUNKS = 4


class AnswerGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: OpenAI | None = None
        if settings.use_nebius_chat:
            self.client = OpenAI(api_key=settings.nebius_api_key, base_url=settings.nebius_base_url)

    def answer(self, question: str, results: list[RetrievalResult]) -> QueryResponse:
        sources = [citation_from_result(result) for result in results]
        if not results:
            return QueryResponse(
                question=question,
                answer="I could not find supporting evidence in the indexed Boeing documents.",
                sources=[],
            )

        if self.client:
            answer = self._llm_answer(question, results)
            answer = self._ensure_citations(answer, len(sources))
            answer = self._ensure_references(answer, sources)
        else:
            answer = ""

        if not answer:
            answer = self._extractive_answer(question, results)
            answer = self._ensure_references(answer, sources)

        return QueryResponse(question=question, answer=answer, sources=sources)

    def stream_answer(self, question: str, results: list[RetrievalResult]) -> Iterator[str]:
        sources = [citation_from_result(result) for result in results]
        if not results:
            yield "I could not find supporting evidence in the indexed Boeing documents."
            return

        if not self.client:
            yield self._ensure_references(self._extractive_answer(question, results), sources)
            return

        context_chunks = results[: self.settings.answer_context_chunks]
        answer = ""
        try:
            context = self._format_context(question, context_chunks)
            stream = self.client.chat.completions.create(
                model=self.settings.nebius_chat_model or "",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": context},
                ],
                temperature=0.1,
                max_tokens=self.settings.answer_max_tokens,
                stream=True,
            )
            for event in stream:
                delta = event.choices[0].delta.content or ""
                if not delta:
                    continue
                answer += delta
                yield delta
        except Exception:
            log.exception("Streaming LLM call failed")
            answer = ""

        if not self._is_usable_answer(answer):
            fallback = self._ensure_references(self._extractive_answer(question, results), sources)
            yield fallback
            return

        repaired = self._ensure_citations(answer, len(sources))
        final = self._ensure_references(repaired, sources)
        suffix = final[len(answer) :]
        if suffix:
            yield suffix

    def _ensure_citations(self, answer: str, source_count: int) -> str:
        if not answer or not source_count:
            return answer
        cited = [int(num) for num in re.findall(r"\[(\d+)\]", answer)]
        if cited and all(1 <= num <= source_count for num in cited):
            return answer

        repaired: list[str] = []
        fallback = "[1]"
        for line in answer.splitlines():
            stripped = line.strip()
            if not stripped:
                repaired.append(line)
                continue
            if stripped.startswith("#") or re.fullmatch(r"[-|: ]+", stripped):
                repaired.append(line)
                continue
            if re.search(r"\[\d+\]", stripped):
                repaired.append(line)
            else:
                repaired.append(f"{line} {fallback}")
        return "\n".join(repaired)

    def _ensure_references(self, answer: str, sources: list[SourceCitation]) -> str:
        if not answer or not sources:
            return answer
        if re.search(r"(?im)^references:\s*$", answer):
            return answer

        cited_numbers = [int(num) for num in re.findall(r"\[(\d+)\]", answer)]
        ordered: list[int] = []
        for number in cited_numbers:
            if 1 <= number <= len(sources) and number not in ordered:
                ordered.append(number)
        if not ordered:
            ordered = [1]

        lines = ["", "References:"]
        for number in ordered:
            source = sources[number - 1]
            section = " > ".join(source.section_path or [])
            parts = [
                source.file_name,
                str(source.report_year) if source.report_year else None,
                source.report_type,
                _page_label(source),
                source.content_type if source.content_type == "image" else None,
                f"section: {section}" if section else None,
            ]
            label = ", ".join(part for part in parts if part)
            lines.append(f"- [{number}] {label}.")
        return answer.rstrip() + "\n" + "\n".join(lines)

    def _llm_answer(self, question: str, results: list[RetrievalResult]) -> str:
        context_chunks = results[: self.settings.answer_context_chunks]
        answer = self._call_llm(question, context_chunks)
        if answer:
            return answer

        log.warning("First LLM attempt returned empty; retrying with %d chunks", RETRY_CHUNKS)
        short_context = results[:RETRY_CHUNKS]
        answer = self._call_llm(question, short_context, temperature=0.2)
        return answer

    def _call_llm(
        self,
        question: str,
        results: list[RetrievalResult],
        temperature: float = 0.1,
    ) -> str:
        if not self.client:
            return ""
        context = self._format_context(question, results)
        try:
            response = self.client.chat.completions.create(
                model=self.settings.nebius_chat_model or "",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": context},
                ],
                temperature=temperature,
                max_tokens=self.settings.answer_max_tokens,
            )
            answer = (response.choices[0].message.content or "").strip()
            return answer if self._is_usable_answer(answer) else ""
        except Exception:
            log.exception("LLM call failed")
            return ""

    def _is_usable_answer(self, answer: str) -> bool:
        text = re.sub(r"[#*_`\\s]+", " ", answer or "").strip()
        return len(text) >= 80 and len(text.split()) >= 14

    def _format_context(self, question: str, results: list[RetrievalResult]) -> str:
        is_locator = bool(_LOCATOR_RE.search(question))

        blocks: list[str] = []
        for index, result in enumerate(results, start=1):
            chunk = result.chunk
            source_label = chunk.citation_label
            section = " > ".join(chunk.section_path or [])
            context = chunk.metadata_json.get("contextual_context") or ""
            text = chunk.raw_text or chunk.text
            header = (
                f"[{index}] {source_label}\n"
                f"content_type={chunk.content_type}; section={section}"
            )
            if is_locator:
                header += f"; page={chunk.page_start}"
            if context:
                header += f"\nretrieval_context={context}"
            blocks.append(f"{header}\n{text[:2400]}")

        preamble = f"Question: {question}\n\n"
        if is_locator:
            preamble += (
                "The user wants to know WHERE in the documents this topic is discussed. "
                "Focus on identifying the report name, year, page numbers, and section titles.\n\n"
            )
        return preamble + "Evidence:\n" + "\n\n---\n\n".join(blocks)

    def _extractive_answer(self, question: str, results: list[RetrievalResult]) -> str:
        top = results[: self.settings.answer_context_chunks]
        bullets: list[str] = []
        for index, result in enumerate(top, start=1):
            text = " ".join((result.chunk.raw_text or result.chunk.text).split())
            snippet = text[:400]
            if len(text) > 400:
                last_period = snippet.rfind(".")
                if last_period > 200:
                    snippet = snippet[: last_period + 1]
            source = result.chunk.citation_label
            bullets.append(f"- {snippet} [{index}] ({source})")

        header = (
            "The synthesis model did not return a usable response. "
            "Here is a deterministic cited summary of the retrieved evidence only:\n"
        )
        return header + "\n".join(bullets)


def _page_label(source: SourceCitation) -> str | None:
    if source.page_start is None:
        return None
    if source.page_end and source.page_end != source.page_start:
        return f"pp. {source.page_start}-{source.page_end}"
    return f"p. {source.page_start}"
