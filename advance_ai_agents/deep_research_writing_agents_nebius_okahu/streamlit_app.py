"""Streamlit chat UI orchestrating the Deep Research + LinkedIn Writer MCP servers.

Mirrors the logic of the `/research-and-write` skill but inline in Python:
- Decompose a topic into N research queries (one Nebius/LangChain call with a Pydantic schema).
- Run `deep_research` per query against the research MCP server (live counter).
- Run `compile_research` to produce `research.md`.
- Run `generate_post` against the writing MCP server, polling intermediate
  `post_*.md` + `.memory/reviews_*.json` files for live evaluator-optimizer
  progress (the server itself doesn't stream progress — we infer it from the
  artifacts it writes).
- Run `generate_image` and render the result.

Run with:
    make run-ui
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import streamlit as st
from fastmcp import Client
from pydantic import BaseModel, Field

# Make the `writing` package importable so we can borrow Settings (loads .env).
REPO_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(REPO_ROOT / "src"))

from writing.config.settings import get_settings  # noqa: E402
from writing.utils.llm import call_llm  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESEARCH_SERVER = str(REPO_ROOT / "src" / "research" / "server.py")
WRITING_SERVER = str(REPO_ROOT / "src" / "writing" / "server.py")
OUTPUTS_DIR = REPO_ROOT / "outputs"

DECOMPOSE_PROMPT = """\
You are planning a deep research session for a LinkedIn post.

Given the topic below, break it into 3 to 5 specific, distinct research queries.
Each query must be a standalone question that web search could answer.
Avoid redundancy — each query should cover a different angle.

<topic>
{topic}
</topic>
"""

GUIDELINE_PROMPT = """\
You are drafting a guideline for a LinkedIn post on the topic below.

Produce a markdown guideline with these sections (use H2):
- Topic
- Angle
- Target Audience
- Key Points (3-5 bullets)
- Tone

Keep it under 200 words. Return ONLY the markdown — no preamble.

<topic>
{topic}
</topic>
"""

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Indeterminate progress bar (CSS keyframe shimmer)
# ---------------------------------------------------------------------------
# Injected once at app startup; each stage just writes a small label+bar HTML
# fragment into its st.empty() slot while work is in flight, then clears it.
# Used for stages where the MCP server gives us no progress signal — the
# evaluator-optimizer loop and image generation both return only at the end.

INDETERMINATE_BAR_CSS = """
<style>
@keyframes ry-indeterminate {
  0%   { left: -40%; }
  100% { left: 100%; }
}
.ry-indet-bar {
  position: relative;
  width: 100%;
  height: 6px;
  background: rgba(250, 250, 250, 0.08);
  border-radius: 3px;
  overflow: hidden;
  margin: 0.35rem 0 0.6rem 0;
}
.ry-indet-fill {
  position: absolute;
  top: 0;
  left: -40%;
  width: 40%;
  height: 100%;
  background: linear-gradient(90deg, transparent, #ff6b35, transparent);
  animation: ry-indeterminate 1.4s linear infinite;
  border-radius: 3px;
}
.ry-indet-label {
  font-size: 0.9rem;
  color: rgba(250, 250, 250, 0.85);
  margin-bottom: 0.1rem;
}
</style>
"""


def indeterminate_bar_html(label: str) -> str:
    return (
        f'<div class="ry-indet-label">{label}</div>'
        '<div class="ry-indet-bar"><div class="ry-indet-fill"></div></div>'
    )


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ResearchQueries(BaseModel):
    queries: list[str] = Field(min_length=2, max_length=6)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len] or "research").rstrip("-")


def unwrap(result: Any) -> Any:
    """FastMCP Client.call_tool returns an object with `.data`; tolerate both."""
    return getattr(result, "data", result)


# ---------------------------------------------------------------------------
# Stage controllers — own their st.empty placeholders, write progress live
# ---------------------------------------------------------------------------


@dataclass
class ResearchStageView:
    container: Any  # st.container
    queries: list[str] = field(default_factory=list)
    status_per_query: list[str] = field(
        default_factory=list
    )  # "pending"|"running"|"done"
    sources_per_query: list[int] = field(default_factory=list)
    counter_slot: Any = None
    rows_slot: Any = None
    compile_slot: Any = None

    def render_init(self, queries: list[str]) -> None:
        self.queries = queries
        self.status_per_query = ["pending"] * len(queries)
        self.sources_per_query = [0] * len(queries)
        with self.container:
            st.markdown("### 🔎 Deep research")
            self.counter_slot = st.empty()
            self.rows_slot = st.empty()
            self.compile_slot = st.empty()
        self._redraw()

    def update(self, idx: int, *, status: str, sources: int = 0) -> None:
        self.status_per_query[idx] = status
        if sources:
            self.sources_per_query[idx] = sources
        self._redraw()

    def _redraw(self) -> None:
        done = sum(1 for s in self.status_per_query if s == "done")
        total = len(self.queries)
        self.counter_slot.markdown(
            f"**{done} / {total} searches done** &nbsp;·&nbsp; "
            f"{sum(self.sources_per_query)} sources collected"
        )
        lines = []
        for q, s, src in zip(
            self.queries, self.status_per_query, self.sources_per_query
        ):
            icon = {"pending": "⚪️", "running": "🟡", "done": "🟢"}[s]
            tail = f" — {src} sources" if s == "done" else ""
            lines.append(f"- {icon} {q}{tail}")
        self.rows_slot.markdown("\n".join(lines))

    def compile_running(self) -> None:
        self.compile_slot.markdown("📚 _Compiling `research.md`..._")

    def compile_done(self, output_path: str) -> None:
        try:
            size = Path(output_path).stat().st_size
            self.compile_slot.success(f"✅ `research.md` generated ({size:,} bytes)")
        except OSError:
            self.compile_slot.success("✅ `research.md` generated")


@dataclass
class WritingStageView:
    container: Any
    progress_slot: Any = None
    post_slot: Any = None
    image_running_slot: Any = None
    image_slot: Any = None
    num_reviews: int = 0

    def render_init(self, num_reviews: int) -> None:
        # The MCP server's `generate_post` is one-shot — every intermediate file
        # is flushed to disk only after the entire evaluator-optimizer loop ends.
        # So we can't show iteration counts; we render an indeterminate bar.
        self.num_reviews = num_reviews
        with self.container:
            st.markdown("### ✍️ Writing workflow")
            st.caption(
                f"Evaluator-optimizer loop · up to {num_reviews} review/edit iterations"
            )
            self.progress_slot = st.empty()
            self.post_slot = st.empty()
            self.image_running_slot = st.empty()
            self.image_slot = st.empty()
        self.writing_running()

    def writing_running(self) -> None:
        self.progress_slot.markdown(
            indeterminate_bar_html("Running evaluator-optimizer loop..."),
            unsafe_allow_html=True,
        )

    def writing_done(self, post_text: str, post_path: str) -> None:
        self.progress_slot.success(f"✅ Post finalized · saved to `{post_path}`")
        with self.post_slot.container():
            with st.expander("📝 Final post", expanded=True):
                st.markdown(post_text)

    def image_running(self) -> None:
        self.image_running_slot.markdown(
            indeterminate_bar_html("Generating image with Gemini Image..."),
            unsafe_allow_html=True,
        )

    def image_done(self, image_path: str) -> None:
        self.image_running_slot.empty()
        with self.image_slot.container():
            st.markdown("### 🖼️ Generated image")
            if Path(image_path).exists():
                st.image(image_path, width=520)
            st.caption(f"Saved to `{image_path}`")

    def image_skipped(self) -> None:
        self.image_running_slot.markdown("⏭️ Image generation skipped.")

    def image_failed(self, error: Exception) -> None:
        self.image_running_slot.error(f"Image generation failed: {error}")


# ---------------------------------------------------------------------------
# Async pipeline
# ---------------------------------------------------------------------------


async def decompose_topic(topic: str) -> list[str]:
    settings = get_settings()
    response = await call_llm(
        DECOMPOSE_PROMPT.format(topic=topic),
        model=settings.writer_model,
        response_schema=ResearchQueries,
    )
    queries = ResearchQueries.model_validate_json(response).queries
    return queries


async def synthesize_guideline(topic: str) -> str:
    settings = get_settings()
    response = await call_llm(
        GUIDELINE_PROMPT.format(topic=topic),
        model=settings.writer_model,
    )
    return response or ""


async def run_research_pipeline(
    working_dir: Path,
    queries: list[str],
    view: ResearchStageView,
) -> None:
    async with Client(RESEARCH_SERVER) as client:
        for i, q in enumerate(queries):
            view.update(i, status="running")
            res = await client.call_tool(
                "deep_research",
                {"working_dir": str(working_dir), "query": q},
            )
            data = unwrap(res)
            sources = data.get("total_sources", 0) if isinstance(data, dict) else 0
            view.update(i, status="done", sources=sources)

        view.compile_running()
        res = await client.call_tool(
            "compile_research", {"working_dir": str(working_dir)}
        )
        data = unwrap(res)
        out = data.get("output_path", "") if isinstance(data, dict) else ""
        view.compile_done(out)


async def fetch_num_reviews(client: Client) -> int:
    """Read `config://settings` from the writing server. Fall back to local default."""
    try:
        res = await client.read_resource("config://settings")
        # FastMCP returns a list of resource contents; the JSON is in `.text`.
        text = getattr(res[0], "text", None) if res else None
        if text:
            cfg = json.loads(text)
            return int(cfg.get("num_reviews", get_settings().num_reviews))
    except Exception:
        pass
    return get_settings().num_reviews


async def run_writing_pipeline(
    working_dir: Path,
    skip_image: bool,
    view: WritingStageView,
) -> None:
    async with Client(WRITING_SERVER) as client:
        num_reviews = await fetch_num_reviews(client)
        view.render_init(num_reviews)

        # The MCP `generate_post` tool is one-shot — the entire evaluator-
        # optimizer loop runs in memory and intermediate `post_*.md` /
        # `.memory/reviews_*.json` files are flushed only after the call
        # returns. There is no observable progress signal mid-call, so we
        # show an indeterminate bar and just await.
        result = unwrap(
            await client.call_tool(
                "generate_post",
                {"working_dir": str(working_dir), "delete_iterations": False},
            )
        )
        post_text = result.get("post", "") if isinstance(result, dict) else ""
        post_path = result.get("output_path", "") if isinstance(result, dict) else ""
        view.writing_done(post_text, post_path)

        if skip_image:
            view.image_skipped()
            return

        view.image_running()
        try:
            res = await client.call_tool(
                "generate_image", {"working_dir": str(working_dir)}
            )
            data = unwrap(res)
            image_path = data.get("image_path", "") if isinstance(data, dict) else ""
            view.image_done(image_path)
        except Exception as exc:
            view.image_failed(exc)


async def run_pipeline(
    topic: str,
    research_view: ResearchStageView,
    writing_view: WritingStageView,
) -> dict[str, str]:
    """End-to-end: decompose → research → compile → write → image."""
    slug = slugify(topic.splitlines()[0] if topic else "session")
    working_dir = OUTPUTS_DIR / slug
    working_dir.mkdir(parents=True, exist_ok=True)

    (working_dir / "seed.md").write_text(topic, encoding="utf-8")

    synthesized = await synthesize_guideline(topic)
    (working_dir / "guideline.md").write_text(synthesized, encoding="utf-8")

    queries = await decompose_topic(topic)
    research_view.render_init(queries)
    await run_research_pipeline(working_dir, queries, research_view)

    await run_writing_pipeline(working_dir, skip_image=False, view=writing_view)

    return {
        "working_dir": str(working_dir),
        "research": str(working_dir / "research.md"),
        "post": str(working_dir / "post.md"),
        "image": str(working_dir / "post_image.png"),
    }


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------


st.set_page_config(
    page_title="Research → Writer",
    page_icon="✍️",
    layout="wide",
)

# Inject the indeterminate-bar keyframes once per page load
st.markdown(INDETERMINATE_BAR_CSS, unsafe_allow_html=True)

st.title("✍️ Research → Writer")
st.caption(
    "End-to-end pipeline: deep research → LinkedIn post → image. "
    "Drives the `deep-research` and `linkedin-writer` MCP servers via FastMCP."
)

# --- Session state -----------------------------------------------------------

if "run_count" not in st.session_state:
    st.session_state.run_count = 0
if "processed_seed_file_id" not in st.session_state:
    st.session_state.processed_seed_file_id = None

# --- Main area --------------------------------------------------------------

# Suggestion pills before first run
SUGGESTIONS = {
    "Why single agents beat multi-agent setups": (
        "Why most AI teams over-engineer with multi-agent setups when a single "
        "agent with good tools wins. Cover the spectrum: workflows → "
        "single-agent + tools → multi-agent."
    ),
    "Harness engineering for reliable AI agents": (
        "Harness engineering: the environment around the model — tools, "
        "permissions, state, evals, retries, guardrails. Why prompt engineering "
        "alone isn't enough."
    ),
    "Context engineering vs. context rot": (
        "Context engineering goes beyond prompt engineering. What 'context rot' "
        "is and why agents degrade past 10-20 tools."
    ),
}

if st.session_state.run_count == 0:
    selected = st.pills(
        "Try a topic:",
        list(SUGGESTIONS.keys()),
        label_visibility="collapsed",
    )
    if selected:
        st.session_state.prefill = SUGGESTIONS[selected]

# Two ways to kick off: type a topic in the chat input, OR upload a seed file
# (the file uploader auto-triggers a rerun, so the pipeline starts immediately
# without the user having to type or submit anything).
seed_col, upload_col = st.columns([4, 1])
with seed_col:
    prompt = st.chat_input("Paste a topic / seed text...")
with upload_col:
    seed_file = st.file_uploader(
        "...or upload a seed file",
        type=["md", "txt"],
        label_visibility="collapsed",
        key="seed_file_uploader",
    )

# Resolve the topic source for this rerun, in priority order:
# 1. Pill selection from session_state (one-shot)
# 2. Typed chat input
# 3. A freshly-uploaded seed file (deduped via file_id)
topic_text: str | None = None

if st.session_state.get("prefill"):
    topic_text = st.session_state.pop("prefill")
elif prompt:
    topic_text = (prompt or "").strip()
elif (
    seed_file is not None
    and seed_file.file_id != st.session_state.processed_seed_file_id
):
    st.session_state.processed_seed_file_id = seed_file.file_id
    topic_text = seed_file.read().decode("utf-8").strip()

if topic_text is not None:
    if not topic_text:
        st.warning("Please provide a topic (text or file).")
    else:
        st.session_state.run_count += 1

        with st.chat_message("user"):
            with st.expander("Seed / topic", expanded=False):
                st.markdown(topic_text)

        with st.chat_message("assistant", avatar=":material/auto_awesome:"):
            research_container = st.container()
            writing_container = st.container()
            footer = st.empty()

            research_view = ResearchStageView(container=research_container)
            writing_view = WritingStageView(container=writing_container)

            try:
                paths = asyncio.run(
                    run_pipeline(
                        topic=topic_text,
                        research_view=research_view,
                        writing_view=writing_view,
                    )
                )
                with footer.container():
                    st.markdown("---")
                    st.markdown("### 📁 Artifacts")
                    st.code(
                        "\n".join(f"{k:>14} : {v}" for k, v in paths.items()),
                        language="text",
                    )
            except Exception as e:  # noqa: BLE001
                logger.exception("Pipeline failed")
                footer.error(f"Pipeline failed: {e}")
