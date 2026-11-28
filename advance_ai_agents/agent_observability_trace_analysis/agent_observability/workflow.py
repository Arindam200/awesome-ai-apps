"""A tiny support agent workflow instrumented with local spans."""

from __future__ import annotations

from dataclasses import dataclass

from .tracing import JsonlTraceRecorder

KNOWLEDGE_BASE = [
    "Password resets expire after 30 minutes and invalidate older reset links.",
    "Invoices are available from Settings > Billing > Invoices.",
    "Workspace owners can invite members from Settings > Members.",
]
STOP_WORDS = {"a", "an", "can", "do", "find", "how", "i", "is", "my", "the", "to", "where"}


def _keywords(text: str) -> set[str]:
    words = {word.strip(".,?!>").lower() for word in text.split()}
    return {word[:-1] if word.endswith("s") else word for word in words - STOP_WORDS}


@dataclass
class SupportAgentWorkflow:
    """Demonstrate agent, retrieval, tool, and model spans without requiring an API key."""

    recorder: JsonlTraceRecorder
    model_name: str = "offline-template-v1"

    def run(self, prompt: str, *, fail_tool: bool = False) -> str:
        with self.recorder.span(
            "support_agent.run",
            kind="agent",
            attributes={"prompt": prompt, "model": self.model_name},
        ) as agent_span:
            context = self._retrieve(prompt)
            ticket = self._lookup_ticket(prompt, fail=fail_tool)
            answer = self._generate(prompt, context, ticket)
            agent_span.set(output=answer, retrieved_context_count=len(context))
            return answer

    def _retrieve(self, query: str) -> list[str]:
        with self.recorder.span(
            "knowledge_base.search",
            kind="retrieval",
            attributes={"query": query},
        ) as span:
            query_words = _keywords(query)
            ranked = sorted(
                ((len(query_words & _keywords(item)), item) for item in KNOWLEDGE_BASE),
                reverse=True,
            )
            matches = [item for score, item in ranked if score]
            span.set(context=matches, result_count=len(matches))
            return matches

    def _lookup_ticket(self, query: str, *, fail: bool) -> dict[str, str]:
        with self.recorder.span(
            "ticket.lookup",
            kind="tool",
            attributes={"tool_input": {"query": query}},
        ) as span:
            if fail:
                raise RuntimeError("ticket service unavailable")
            result = {"ticket_id": "T-1042", "status": "open"}
            span.set(tool_output=result)
            return result

    def _generate(self, prompt: str, context: list[str], ticket: dict[str, str]) -> str:
        with self.recorder.span(
            "response.generate",
            kind="model",
            attributes={
                "provider": "offline",
                "model": self.model_name,
                "prompt": prompt,
                "context": context,
            },
        ) as span:
            evidence = context[0] if context else "No matching knowledge-base article was found."
            answer = f"Ticket {ticket['ticket_id']} is {ticket['status']}. {evidence}"
            span.set(output=answer)
            return answer
