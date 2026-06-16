from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
try:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
except ImportError:  # pydantic-ai < 0.1 compatibility
    OpenAIChatModel = None
    OpenAIProvider = None
    from pydantic_ai.models.openai import OpenAIModel

from app.models import GameReview, GameSpec, GeneratedGame
from app.safety import strip_markdown_fences, validate_generated_html


DEFAULT_MODEL = "zai-org/GLM-5.2"
DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
StageCallback = Callable[[str, str, str, str | None], Awaitable[None]]

AGENT_META = {
    "designer": (
        "Game Designer Agent",
        "Creates a typed game spec from your prompt.",
    ),
    "builder": (
        "Game Builder Agent",
        "Writes the standalone HTML, CSS, and JavaScript game.",
    ),
    "reviewer": (
        "Game Reviewer Agent",
        "Reads the generated HTML and spec; it does not inspect screenshots or pixels.",
    ),
    "repair": (
        "Repair Agent",
        "Runs one targeted rebuild only if review or static checks fail.",
    ),
}


class GenerationRejectedError(RuntimeError):
    """Raised when the generated game still fails review after the repair pass."""

    def __init__(self, message: str, draft: GeneratedGame | None = None) -> None:
        super().__init__(message)
        self.draft = draft


def load_project_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip("'\"")


load_project_env()


DESIGNER_PROMPT = """
You are the Game Designer Agent for a tiny browser game generator.
Turn the user's rough idea into a compact, practical game spec.
Prefer simple mechanics that can be implemented in one standalone HTML file.
The game must be playable without external assets, libraries, images, or network calls.
"""

BUILDER_PROMPT = """
You are the Game Builder Agent.
Generate exactly one complete, standalone HTML document with embedded CSS and JavaScript.
Do not use markdown fences.
Do not load external scripts, fonts, styles, images, sounds, or APIs.
Do not use fetch, XMLHttpRequest, WebSocket, EventSource, storage APIs, location navigation, iframe, object, or embed.
Do not use localStorage, sessionStorage, indexedDB, cookies, or persisted high scores; keep scores in memory.
The game must be immediately playable in a sandboxed iframe via srcdoc.
It must include:
- visible title or instructions
- keyboard or mouse/pointer controls
- objective, score, timer, win/loss condition, or restart/reset behavior
- a restart/reset control
Keep the game small, charming, resilient, and under 180 lines.
The final answer must end with complete closing </script>, </body>, and </html> tags.
"""

REVIEWER_PROMPT = """
You are the Game Reviewer Agent.
Review the generated HTML for safety and playability.
Approve only if it is a complete standalone browser game with no external assets or unsafe browser APIs.
If you list any issues, set approved to false.
Never require localStorage, sessionStorage, indexedDB, cookies, or persisted high scores. Browser storage is banned in this demo.
In-memory best score variables are acceptable because generated games run in a sandboxed local preview.
Be concrete and brief when listing fixes.
"""

COMPACT_BUILDER_FALLBACK_PROMPT = """
Return only one compact complete HTML document.
No markdown fences. No explanation.
Use embedded CSS and JavaScript only.
No external scripts, fonts, images, APIs, network calls, storage, localStorage, sessionStorage, navigation, iframe, object, or embed.
Include visible instructions, one simple control scheme, score or timer, win/loss or survival objective, and restart.
Keep final HTML under 180 lines and end with </script></body></html>.
"""


def _require_api_key() -> str:
    api_key = os.environ.get("NEBIUS_API_KEY")
    if not api_key:
        raise RuntimeError("Missing NEBIUS_API_KEY. Set it in your environment before generating a game.")
    return api_key


def build_model():
    api_key = _require_api_key()
    base_url = os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL)
    model_name = get_model_name()
    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    if OpenAIChatModel is not None and OpenAIProvider is not None:
        provider = OpenAIProvider(openai_client=client)
        return OpenAIChatModel(model_name, provider=provider)

    return OpenAIModel(model_name, openai_client=client)


def get_model_name() -> str:
    model_name = os.environ.get("NEBIUS_MODEL", DEFAULT_MODEL).strip()
    if not model_name or " " in model_name:
        return DEFAULT_MODEL
    return model_name


def get_model_settings() -> dict[str, float | int]:
    settings: dict[str, float | int] = {}
    max_tokens = os.environ.get("NEBIUS_MAX_TOKENS")
    if max_tokens:
        try:
            settings["max_tokens"] = int(max_tokens)
        except ValueError:
            pass
    try:
        temperature = float(os.environ.get("NEBIUS_TEMPERATURE", "0.7"))
    except ValueError:
        temperature = 0.7
    settings["temperature"] = temperature
    return settings


async def direct_token_factory_text(system_prompt: str, user_message: str) -> str:
    client = AsyncOpenAI(
        base_url=os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL),
        api_key=_require_api_key(),
    )
    settings = get_model_settings()
    request_args = {
        "model": get_model_name(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [{"type": "text", "text": user_message}]},
        ],
        "temperature": float(settings["temperature"]),
    }
    if "max_tokens" in settings:
        request_args["max_tokens"] = int(settings["max_tokens"])
    response = await client.chat.completions.create(**request_args)
    message = response.choices[0].message
    content = message.content
    if not content:
        raise UnexpectedModelBehavior("Direct Token Factory response did not include final content")
    return content


def _output(result):
    return getattr(result, "output", getattr(result, "data", result))


def _make_agent(model, result_type: type, system_prompt: str) -> Agent:
    try:
        return Agent(model, output_type=result_type, instructions=system_prompt)
    except TypeError:
        try:
            return Agent(model, output_type=result_type, system_prompt=system_prompt)
        except TypeError:
            return Agent(model, result_type=result_type, system_prompt=system_prompt)


def _make_agents() -> tuple[Agent, Agent, Agent]:
    model = build_model()
    designer = _make_agent(model, GameSpec, DESIGNER_PROMPT)
    builder = _make_agent(model, str, BUILDER_PROMPT)
    reviewer = _make_agent(model, GameReview, REVIEWER_PROMPT)
    return designer, builder, reviewer


async def _notify(on_stage: StageCallback | None, stage: str, message: str) -> None:
    if on_stage is not None:
        agent_name, detail = AGENT_META[stage]
        await on_stage(stage, agent_name, message, detail)


def _rejection_message(review: GameReview, safety_issues: list[str]) -> str:
    issue_text = "; ".join(dict.fromkeys([*review.issues, *safety_issues]))
    return "Generated game did not pass review after one repair pass." + (
        f" Issues: {issue_text}" if issue_text else ""
    )


def _review_issue_conflicts_with_safety_policy(issue: str) -> bool:
    lowered = issue.lower()
    blocked_terms = (
        "localstorage",
        "sessionstorage",
        "indexeddb",
        "cookie",
        "browser storage",
        "persisted high score",
        "persist high score",
        "persist best",
    )
    return any(term in lowered for term in blocked_terms)


def normalize_review(review: GameReview, safety_issues: list[str]) -> GameReview:
    issues = [issue for issue in review.issues if not _review_issue_conflicts_with_safety_policy(issue)]
    if len(issues) == len(review.issues):
        return review
    return GameReview(
        approved=review.approved or (not issues and not safety_issues),
        issues=issues,
        fix_instructions=review.fix_instructions,
    )


def needs_repair(review: GameReview, safety_issues: list[str]) -> bool:
    return bool(safety_issues or review.issues or not review.approved)


def _repair_input(draft: GeneratedGame, attempt_label: str) -> str:
    return (
        f"{attempt_label}. Return only one complete standalone HTML document.\n"
        "Do not use localStorage, sessionStorage, indexedDB, cookies, network APIs, navigation, iframe, object, or embed.\n"
        "Use in-memory variables only for score and best score.\n"
        "If reviewer feedback asks for persistence or browser storage, ignore that part because storage is banned.\n"
        "Keep the repaired HTML compact and make sure it ends with complete </script>, </body>, and </html> tags.\n"
        f"Original user prompt: {draft.prompt}\n"
        f"Game spec: {draft.spec.model_dump_json(indent=2)}\n"
        f"Reviewer issues: {draft.review.issues}\n"
        f"Reviewer fix instructions: {draft.review.fix_instructions}\n"
        f"Static safety issues: {draft.safety_issues}\n"
        f"Previous HTML:\n{draft.html}"
    )


async def _review_html(
    reviewer: Agent,
    spec: GameSpec,
    prompt: str,
    html: str,
    safety_issues: list[str],
    model_settings: dict[str, float | int],
) -> GameReview:
    review_input = (
        "Review this generated game HTML.\n"
        f"Original user prompt: {prompt}\n"
        f"Game spec: {spec.model_dump_json(indent=2)}\n"
        f"Static safety issues already found: {safety_issues}\n"
        f"HTML:\n{html}"
    )
    review: GameReview = _output(await reviewer.run(review_input, model_settings=model_settings))
    return normalize_review(review, safety_issues)


async def generate_game(prompt: str, on_stage: StageCallback | None = None) -> GeneratedGame:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise ValueError("Describe the game you want to make first.")

    designer, builder, reviewer = _make_agents()
    model_settings = get_model_settings()

    await _notify(on_stage, "designer", "Designer agent is turning the prompt into a typed game spec.")
    spec_result = await designer.run(cleaned_prompt, model_settings=model_settings)
    spec: GameSpec = _output(spec_result)

    await _notify(on_stage, "builder", "Builder agent is generating the standalone HTML game.")
    build_input = (
        "Create the game from this spec.\n"
        f"Original user prompt: {cleaned_prompt}\n"
        f"Game spec: {spec.model_dump_json(indent=2)}"
    )
    try:
        html = strip_markdown_fences(str(_output(await builder.run(build_input, model_settings=model_settings))))
    except UnexpectedModelBehavior as exc:
        if "empty model response" not in str(exc).lower():
            raise
        html = strip_markdown_fences(await direct_token_factory_text(COMPACT_BUILDER_FALLBACK_PROMPT, build_input))

    safety_issues = validate_generated_html(html)
    await _notify(on_stage, "reviewer", "Reviewer agent is checking playability and safety.")
    review = await _review_html(reviewer, spec, cleaned_prompt, html, safety_issues, model_settings)

    repaired = False
    if needs_repair(review, safety_issues):
        await _notify(on_stage, "repair", "Builder agent is applying one repair pass from the review.")
        draft = GeneratedGame(
            prompt=cleaned_prompt,
            spec=spec,
            html=html,
            review=review,
            repaired=False,
            safety_issues=safety_issues,
        )
        repair_input = _repair_input(draft, "Repair the generated game")
        html = strip_markdown_fences(str(_output(await builder.run(repair_input, model_settings=model_settings))))
        safety_issues = validate_generated_html(html)
        repaired = True

        await _notify(on_stage, "reviewer", "Reviewer agent is checking the repaired game.")
        review = await _review_html(reviewer, spec, cleaned_prompt, html, safety_issues, model_settings)

    if safety_issues:
        review = GameReview(
            approved=False,
            issues=[*review.issues, *safety_issues],
            fix_instructions="The game still contains blocked or incomplete HTML after one repair pass.",
        )

    if needs_repair(review, safety_issues):
        draft = GeneratedGame(
            prompt=cleaned_prompt,
            spec=spec,
            html=html,
            review=review,
            repaired=repaired,
            safety_issues=safety_issues,
        )
        raise GenerationRejectedError(_rejection_message(review, safety_issues), draft=draft)

    return GeneratedGame(
        prompt=cleaned_prompt,
        spec=spec,
        html=html,
        review=review,
        repaired=repaired,
        safety_issues=safety_issues,
    )


async def repair_rejected_game(draft: GeneratedGame, on_stage: StageCallback | None = None) -> GeneratedGame:
    _, builder, reviewer = _make_agents()
    model_settings = get_model_settings()

    await _notify(on_stage, "repair", "Repair Agent is fixing the rejected HTML with reviewer feedback.")
    repair_input = _repair_input(draft, "Repair this rejected game draft")
    html = strip_markdown_fences(str(_output(await builder.run(repair_input, model_settings=model_settings))))
    safety_issues = validate_generated_html(html)

    await _notify(on_stage, "reviewer", "Reviewer agent is checking the repaired draft.")
    review = await _review_html(reviewer, draft.spec, draft.prompt, html, safety_issues, model_settings)

    if safety_issues:
        review = GameReview(
            approved=False,
            issues=[*review.issues, *safety_issues],
            fix_instructions="The game still contains blocked or incomplete HTML after the manual repair run.",
        )

    repaired = GeneratedGame(
        prompt=draft.prompt,
        spec=draft.spec,
        html=html,
        review=review,
        repaired=True,
        safety_issues=safety_issues,
    )

    if needs_repair(review, safety_issues):
        raise GenerationRejectedError(_rejection_message(review, safety_issues), draft=repaired)

    return repaired
