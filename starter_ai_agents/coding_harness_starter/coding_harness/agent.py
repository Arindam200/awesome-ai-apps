"""OpenAI Agents SDK adapter with a deliberately read-only tool surface."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .models import PatchProposal
from .testing import TestResult


SYSTEM_INSTRUCTIONS = """You are the planning half of a small coding harness.
Inspect the supplied workspace only through the three read-only tools.  Return a
PatchProposal with a concise plan and the smallest set of file operations needed
for the user's task.  Never suggest shell commands, never claim to have edited a
file, and never use an absolute path.  Your proposal is untrusted and will be
locally validated and shown to a human before it can be applied.

Every FileOperation.path is a POSIX-style path relative to the locked workspace
root, not to its parent directory.  Call list_files first and use the returned
relative paths exactly as your guide.  Do not prefix paths with a workspace name
such as fixture_repo/.  A create operation may use only a parent directory that
already exists in the listed workspace; the harness will not create directories.

For update operations, expected_old_text must be an exact unique substring of the
current file. Add or adjust unittest tests when behaviour changes.

Return exactly one JSON object, either as raw JSON or inside a single `json` code
fence. Do not add prose or any other Markdown. The top-level object must have plan
and operations. plan must include task_understanding, files_to_modify, steps,
tests, and risks_and_assumptions. Every operations item must include operation,
path, and reason; create also needs content, and update also needs content and
expected_old_text."""

DEFAULT_MODEL_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL_NAME = "gpt-4.1-mini"


class ProposalProvider(Protocol):
    """Small injection seam used by the runner's offline unit tests."""

    async def propose(
        self,
        task: str,
        workspace: object,
        test_result: TestResult | None = None,
        preparation_feedback: str | None = None,
    ) -> PatchProposal: ...


@dataclass(frozen=True)
class ModelConfig:
    api_key: str
    base_url: str
    model_name: str

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> "ModelConfig":
        env = os.environ if environ is None else environ
        api_key = env.get("MODEL_API_KEY", "").strip()
        base_url = (
            env.get("MODEL_BASE_URL", DEFAULT_MODEL_BASE_URL).strip()
            or DEFAULT_MODEL_BASE_URL
        )
        model_name = (
            env.get("MODEL_NAME", DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME
        )
        if not api_key:
            # Deliberately name only variables; never include their values.
            raise ValueError(
                "Missing model configuration: MODEL_API_KEY. "
                "Set it in your environment or .env file."
            )
        return cls(api_key=api_key, base_url=base_url, model_name=model_name)


class CodingAgent:
    """A real proposal provider; imports optional network dependencies lazily."""

    def __init__(self, config: ModelConfig | None = None) -> None:
        self._config = config

    async def propose(
        self,
        task: str,
        workspace: object,
        test_result: TestResult | None = None,
        preparation_feedback: str | None = None,
    ) -> PatchProposal:
        config = self._config or ModelConfig.from_environment()
        (
            Agent,
            Runner,
            OpenAIChatCompletionsModel,
            AsyncOpenAI,
            function_tool,
            set_tracing_disabled,
        ) = _load_agents_dependencies()

        # These closures are the complete capability set exposed to the model.
        # Workspace performs a separate path/text-policy check on every call.
        @function_tool
        def list_files() -> list[str]:
            """List permitted relative UTF-8 text-file paths in the workspace."""
            return workspace.list_files()

        @function_tool
        def read_file(path: str) -> str:
            """Read one permitted UTF-8 text file by its relative path."""
            return workspace.read_file(path)

        @function_tool
        def search_text(query: str) -> list[dict[str, Any]]:
            """Search permitted text files for a literal string, returning bounded matches."""
            return workspace.search_text(query)

        prompt = _build_prompt(task, test_result, preparation_feedback)
        set_tracing_disabled(disabled=True)
        client = AsyncOpenAI(base_url=config.base_url, api_key=config.api_key)
        try:
            model = OpenAIChatCompletionsModel(
                model=config.model_name,
                openai_client=client,
            )
            # Some OpenAI-compatible endpoints ignore JSON-schema response formats.
            # Keep the SDK's tool loop, then validate its plain-text final output
            # locally as one strict PatchProposal before any patch can be prepared.
            agent = Agent(
                name="Coding harness planner",
                instructions=SYSTEM_INSTRUCTIONS,
                model=model,
                tools=[list_files, read_file, search_text],
            )
            result = await Runner.run(agent, prompt)
            return _coerce_proposal(result.final_output)
        finally:
            await client.close()


def _build_prompt(
    task: str,
    test_result: TestResult | None,
    preparation_feedback: str | None = None,
) -> str:
    prompt = f"Coding task:\n{task.strip()}"
    if preparation_feedback:
        prompt += (
            "\n\nYour previous proposal was rejected before approval; no files were "
            "changed. Return a complete replacement proposal that corrects this "
            f"validation feedback:\n{preparation_feedback}"
        )
    if test_result is None:
        return prompt
    return (
        f"{prompt}\n\nThe previous approved patch was applied, but its fixed unittest run "
        f"failed (exit_code={test_result.exit_code}, timed_out={test_result.timed_out}). "
        "Inspect the current workspace and propose only the next minimal correction. "
        f"Bounded test output:\n{test_result.error_summary()}"
    )


def _coerce_proposal(value: Any) -> PatchProposal:
    if isinstance(value, PatchProposal):
        return value
    if isinstance(value, str):
        json_object = _extract_json_object(value)
        if hasattr(PatchProposal, "model_validate_json"):
            return PatchProposal.model_validate_json(json_object)
        return PatchProposal.parse_raw(json_object)
    if hasattr(PatchProposal, "model_validate"):
        return PatchProposal.model_validate(value)
    return PatchProposal.parse_obj(value)


def _extract_json_object(output: str) -> str:
    """Accept exactly one JSON object, optionally in one ``json`` code fence.

    Compatibility endpoints sometimes ignore the SDK's JSON-schema response
    format.  This deliberately small parser permits neither explanatory prose
    nor partial/multiple JSON values before strict Pydantic validation.
    """

    candidate = output.strip()
    fenced = re.fullmatch(
        r"```json[ \t]*\r?\n(?P<object>.*)\r?\n```", candidate, flags=re.DOTALL
    )
    if fenced:
        candidate = fenced.group("object").strip()
    elif candidate.startswith("```"):
        raise ValueError("model output must use a single ```json fenced object")
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise ValueError(
            "model output must be one complete JSON object with no surrounding prose"
        ) from error
    if not isinstance(parsed, dict):
        raise ValueError("model output must be a JSON object")
    return candidate


def _load_agents_dependencies() -> tuple[Any, Any, Any, Any, Any, Any]:
    """Load SDKs only for a real model call, keeping local tests network-free."""
    try:
        from agents import (
            Agent,
            OpenAIChatCompletionsModel,
            Runner,
            function_tool,
            set_tracing_disabled,
        )
        from openai import AsyncOpenAI
    except ImportError as error:
        raise RuntimeError(
            "OpenAI Agents SDK dependencies are unavailable. Install this project's "
            "dependencies (for example: pip install -e .) before running the CLI."
        ) from error
    return (
        Agent,
        Runner,
        OpenAIChatCompletionsModel,
        AsyncOpenAI,
        function_tool,
        set_tracing_disabled,
    )
