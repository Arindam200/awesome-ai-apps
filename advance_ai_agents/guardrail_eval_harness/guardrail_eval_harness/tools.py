"""Fixture-backed mock tools instrumented to record execution at the body."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from agents import FunctionTool, RunContextWrapper
from agents.tool import Tool
from agents.tool_context import ToolContext

from guardrail_eval_harness.policy import (
    DraftArguments,
    FixtureState,
    Policy,
    SearchArguments,
    TicketStatusArguments,
    record_observation,
)

if TYPE_CHECKING:
    from guardrail_eval_harness.schemas import RunTrace


ARGUMENT_MODELS: dict[str, type[Any]] = {
    "search_help_articles": SearchArguments,
    "get_ticket_status": TicketStatusArguments,
    "create_ticket_draft": DraftArguments,
}


class HarnessTools:
    """Builds SDK FunctionTools that log attempts, blocks, and executions."""

    def __init__(self, state: FixtureState, policy: Policy, trace: RunTrace) -> None:
        self.state = state
        self.policy = policy
        self.trace = trace

    def build(self) -> list[Tool]:
        return [self._search_tool(), self._status_tool(), self._draft_tool()]

    def _search_tool(self) -> FunctionTool:
        def body(query: str) -> str:
            matches = [
                {"slug": a.slug, "title": a.title, "excerpt": a.content[:200]}
                for a in self.state.articles
                if query.lower() in a.title.lower() or query.lower() in a.slug
            ]
            return json.dumps({"results": matches})

        return self._wrap(
            "search_help_articles", "Search the fixed help-center articles.", body
        )

    def _status_tool(self) -> FunctionTool:
        def body(ticket_id: str) -> str:
            ticket = self.state.tickets[ticket_id]
            return json.dumps(
                {
                    "ticket_id": ticket.ticket_id,
                    "subject": ticket.subject,
                    "status": ticket.status,
                }
            )

        return self._wrap(
            "get_ticket_status", "Look up the status of an owned ticket.", body
        )

    def _draft_tool(self) -> FunctionTool:
        def body(subject: str, body_text: str) -> str:
            self.state.drafts.append({"subject": subject, "body": body_text})
            return json.dumps(
                {
                    "drafted": True,
                    "note": "Draft stored in memory only; it cannot be submitted.",
                }
            )

        return self._wrap(
            "create_ticket_draft",
            "Create an in-memory draft. There is no way to submit or send it.",
            body,
            body_param="body_text",
        )

    def _wrap(
        self,
        name: str,
        description: str,
        body: Any,
        body_param: str | None = None,
    ) -> FunctionTool:
        schema = ARGUMENT_MODELS[name].model_json_schema()
        schema["additionalProperties"] = False

        async def invoke(ctx: ToolContext[Any], arguments: str) -> str:
            schema_error: str | None = None
            parsed: dict[str, Any] = {}
            try:
                candidate = json.loads(arguments)
                if not isinstance(candidate, dict):
                    raise TypeError("arguments must be a JSON object")
                parsed = candidate
                ARGUMENT_MODELS[name].model_validate(parsed)
            except Exception as exc:
                schema_error = str(exc)[:200]
                record_observation(
                    self.trace,
                    ctx.tool_call_id,
                    name,
                    arguments,
                    False,
                    schema_error,
                    False,
                    "schema_invalid",
                    False,
                )
                raise ValueError(
                    f"Invalid arguments for {name}: {schema_error}"
                ) from exc

            decision = self.policy.check(name, parsed, self.state)
            if not decision.allowed:
                record_observation(
                    self.trace,
                    ctx.tool_call_id,
                    name,
                    arguments,
                    True,
                    None,
                    False,
                    decision.reason,
                    False,
                )
                raise PermissionError(f"blocked:{decision.reason}")

            call_kwargs = dict(parsed)
            if body_param is not None and "body" in call_kwargs:
                call_kwargs[body_param] = call_kwargs.pop("body")
            result = str(body(**call_kwargs))
            record_observation(
                self.trace,
                ctx.tool_call_id,
                name,
                arguments,
                True,
                None,
                True,
                None,
                True,
                result[:200],
            )
            return result

        return FunctionTool(
            name=name,
            description=description,
            params_json_schema=schema,
            on_invoke_tool=invoke,
        )


def run_context(state: FixtureState) -> RunContextWrapper[FixtureState]:
    return RunContextWrapper(context=state)
