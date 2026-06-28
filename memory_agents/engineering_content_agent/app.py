"""
Developer Trend & DevRel Ideation Agent

Chat-first Streamlit app for developer trend digest and DevRel talk/blog ideation
from Hacker News, DEV.to, Engram Memory, and an Agno multi-agent team.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path

import streamlit as st

from agents import run_autonomous_content_team
from chat import (
    apply_prompt_context,
    conversational_response,
    followup_response,
    has_required_context,
    missing_fields,
    render_context_summary,
    wants_brief_run,
    wants_current_report_followup,
    wants_explicit_research_run,
    wants_memory_lookup,
)
from config import DEFAULT_MODEL, get_settings, load_project_env
from engram_memory import MemoryRecord, build_research_summary_preview, create_memory_store
from llm import build_model, make_agent, parse_json_object, run_agent
from models import CompanyContext


APP_DIR = Path(__file__).resolve().parent
load_project_env()

CONTEXT_EXTRACTOR_PROMPT = """
You extract and infer context for a chat-first developer trend and DevRel ideation agent.
Return only JSON with keys: company_name, product, audience, seed_keywords, competitors, existing_topics.

Use the user's natural language and current context. If the user asks for content ideas, talk/blog ideas,
trend research, or DevRel opportunities for a named product/domain, infer reasonable missing
product/category, audience, and search angles rather than demanding labels.

Do not invent a company if no company, product, or domain is mentioned.
"""

ROUTER_PROMPT = """
You route messages for a chat-first developer trend and DevRel ideation agent.
Return only JSON with keys: intent, requires_fresh_sources, reason.

Choose one intent:
- memory_lookup: asks what was discussed, researched, generated, remembered, or done before/in the past/lately, or asks for recommendations based on existing/past research.
- research_run: asks for fresh/new source research from HN, DEV.to, developer conversations, article supply, trends, topics, or DevRel opportunities.
- followup: asks about the current/latest report, evidence, summary, or refinements from the current report.
- chat: asks general questions or gives context without requesting research or memory lookup.

Important routing rules:
- If the user says "based on our research", "last few products", "so far", "what have we researched", or "what should we work on from previous research", choose memory_lookup even if they say suggest/recommend/articles.
- If the user asks "show evidence for idea 2", "make these more technical", "summarize the report", or "what did we find", choose followup when has_latest_report is true.
- Choose research_run only when the user wants fresh research, new HN/DEV/source collection, or a new trend digest/report.
- Do not choose research_run for memory or current-report follow-ups.
- requires_fresh_sources must be true only when HN/DEV/source APIs should be called now. It must be false for memory_lookup, followup, and chat.

Examples:
- "Based on our research of last few products, what could be the top 3 articles we should work on?" -> {"intent":"memory_lookup","requires_fresh_sources":false,"reason":"Uses existing research across past products."}
- "What products research have we done so far?" -> {"intent":"memory_lookup","requires_fresh_sources":false,"reason":"Asks about past research."}
- "Show evidence for idea 2" -> {"intent":"followup","requires_fresh_sources":false,"reason":"Asks about latest report evidence."}
- "Research HN and DEV and suggest blog ideas for this product" -> {"intent":"research_run","requires_fresh_sources":true,"reason":"Asks for fresh source research."}
"""

MEMORY_SUMMARIZER_PROMPT = """
You answer questions from Engram memories for a developer trend and DevRel ideation agent.
Return a concise natural-language answer, not JSON.

Rules:
- Answer the user's question directly.
- Speak like the app assistant, not like a memory debugger.
- Do not mention Engram, memory records, "what's known", "what's uncertain", confidence, or retrieval.
- Use first-person phrasing like "Yes, we have..." or "I don't see that we've...".
- Do not repeat the same sentence or paragraph.
- Extract concrete products, companies, trend topics, talk/blog ideas, or reports from memories.
- Ignore assistant meta chatter like "the user asked", missing-context reminders, or UI status.
- Ignore irrelevant memories that do not answer the question.
- Do not call older stored memories "latest", "current", or "recent"; say "previously researched" instead.
- If memories are noisy or weak, answer briefly and say what you can infer without sounding forensic.
"""

APP_NAME = "Developer Trend & DevRel Ideation Agent"
APP_WELCOME_VERSION = "devrel-ideation-v2"
ROUTER_TIMEOUT_SECONDS = 18

PIPELINE_STEPS: list[tuple[str, str]] = [
    ("planner", "Query Planner"),
    ("research_hn", "HN demand research"),
    ("research_dev", "DEV.to supply research"),
    ("research_engram", "Engram memory lookup"),
    ("writer", "DevRel Ideation Writer"),
    ("assembly", "Report assembly"),
]

STEP_ICON = {
    "pending": "○",
    "active": "◉",
    "done": "✓",
    "skipped": "–",
}

st.set_page_config(
    page_title=APP_NAME,
    layout="wide",
    initial_sidebar_state="expanded",
)


def _inline_png(path: Path, height: int) -> str:
    try:
        encoded = base64.b64encode(path.read_bytes()).decode()
    except Exception:
        return ""
    return (
        f"<img src='data:image/png;base64,{encoded}' "
        f"style='height:{height}px; width:auto; display:inline-block; "
        f"vertical-align:middle; margin:0 8px;' alt='{path.stem}'>"
    )


def _png_data_uri(path: Path) -> str:
    try:
        encoded = base64.b64encode(path.read_bytes()).decode()
    except Exception:
        return ""
    return f"data:image/png;base64,{encoded}"


def _inline_svg(path: Path, height: int) -> str:
    try:
        encoded = base64.b64encode(path.read_bytes()).decode()
    except Exception:
        return ""
    return (
        f"<img src='data:image/svg+xml;base64,{encoded}' "
        f"style='height:{height}px; width:auto; display:inline-block; "
        f"vertical-align:middle; margin:0 8px;' alt='{path.stem}'>"
    )


st.markdown(
    """
    <style>
      .stApp { background: #0B1020; color: #E5E7EB; }
      [data-testid="stAppViewContainer"] .main .block-container {
        max-width: 1580px;
        padding-top: 5.5rem;
        padding-left: 4.25rem;
        padding-right: 4.25rem;
      }
      [data-testid="stSidebar"] {
        background: #111827;
        min-width: 300px;
        max-width: 300px;
      }
      [data-testid="stSidebar"] * {
        font-size: 1rem;
      }
      [data-testid="stSidebar"] h3 {
        font-size: 1.15rem;
      }
      [data-testid="stSidebar"] .stCaptionContainer,
      [data-testid="stSidebar"] .stCaptionContainer p {
        font-size: 0.96rem;
        line-height: 1.45;
      }
      [data-testid="stChatMessage"] {
        background: rgba(31, 41, 55, 0.72);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 8px;
        padding: 1rem 1.1rem;
        max-width: 100%;
      }
      [data-testid="stChatMessage"] p,
      [data-testid="stChatMessage"] li {
        font-size: 1.06rem;
        line-height: 1.65;
      }
      [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
        max-width: 980px;
      }
      [data-testid="stCaptionContainer"] p {
        font-size: 1rem;
        line-height: 1.5;
      }
      [data-testid="stChatInput"] textarea {
        font-size: 1.02rem;
        line-height: 1.45;
      }
      .eca-provider-row {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        margin: 6px 0 4px;
      }
      .eca-provider-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border: 1px solid rgba(148, 163, 184, 0.28);
        background: rgba(15, 23, 42, 0.76);
        border-radius: 8px;
        padding: 5px 8px;
        font-size: 0.86rem;
        line-height: 1.1;
      }
      .eca-title {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 14px;
        margin: 0;
        padding: 0;
        font-size: 2.65rem;
        font-weight: 800;
        color: #F9FAFB;
        line-height: 1.15;
      }
      .eca-source-chip {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        white-space: nowrap;
      }
      .eca-source-chip img {
        height: 40px;
        width: auto;
        display: inline-block;
      }
      .eca-brand-card {
        width: 100%;
        height: 70px;
        border-radius: 8px;
        background: #FFFFFF;
        border: 1px solid rgba(255, 255, 255, 0.18);
        padding: 10px 14px;
        box-shadow: 0 8px 18px rgba(0, 0, 0, 0.18);
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 8px 0 10px;
      }
      .eca-brand-card img {
        display: block;
        height: 42px;
        width: 175px;
        object-fit: contain;
      }
      .eca-metric-row {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin: 6px 0 12px;
      }
      .eca-metric {
        display: inline-flex;
        align-items: center;
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 8px;
        background: rgba(15, 23, 42, 0.7);
        padding: 5px 9px;
        font-size: 0.92rem;
      }
      .eca-section-note {
        color: #AEB7C7;
        font-size: 0.98rem;
        line-height: 1.45;
        margin: 0.1rem 0 1rem;
      }
      @media (max-width: 900px) {
        [data-testid="stAppViewContainer"] .main .block-container {
          padding-left: 1rem;
          padding-right: 1rem;
        }
        .eca-title {
          font-size: 2rem;
        }
        .eca-source-chip img {
          height: 32px;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

hackernews_img_inline = _inline_svg(APP_DIR / "assets" / "hacker_news.svg", 40)
devto_img_inline = _inline_svg(APP_DIR / "assets" / "devto.svg", 40)
title_html = f"""
<div style='display:flex; align-items:center; width:100%; padding:8px 0;'>
  <h1 class='eca-title'>
    <span>{APP_NAME} with</span>
    <span class='eca-source-chip'>{hackernews_img_inline}<span>Hacker News</span></span>
    <span>and</span>
    <span class='eca-source-chip'>{devto_img_inline}<span>DEV.to</span></span>
  </h1>
</div>
"""
st.markdown(title_html, unsafe_allow_html=True)
st.caption(
    "Agno multi-agent research from Hacker News trends, DEV.to supply gaps, "
    "Engram memory, and GLM report writing."
)


def init_state() -> None:
    settings = get_settings(require_nebius=False)
    defaults = {
        "messages": [],
        "context": {
            "company_name": "",
            "product": "",
            "audience": "",
            "seed_keywords": [],
            "competitors": [],
            "existing_topics": [],
        },
        "limit": 8,
        "latest_result": None,
        "stage_messages": [],
        "pipeline_steps": {step_id: "pending" for step_id, _ in PIPELINE_STEPS},
        "memory_store": None,
        "is_running": False,
        "conversation_id": f"eca-{uuid.uuid4().hex[:10]}",
        "engram_user_id": settings.engram_user_id,
        "stored_context_fingerprint": "",
        "welcome_version": APP_WELCOME_VERSION,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    st.session_state.engram_user_id = settings.engram_user_id

    if st.session_state.get("welcome_version") != APP_WELCOME_VERSION:
        st.session_state.messages = []
        st.session_state.latest_result = None
        st.session_state.welcome_version = APP_WELCOME_VERSION


def reset_pipeline_steps() -> None:
    st.session_state.pipeline_steps = {step_id: "pending" for step_id, _ in PIPELINE_STEPS}


def update_pipeline_from_message(message: str) -> None:
    lowered = message.lower()
    steps = st.session_state.pipeline_steps

    def activate(step_id: str) -> None:
        for sid, _ in PIPELINE_STEPS:
            if sid == step_id:
                steps[sid] = "active"
            elif steps.get(sid) == "active":
                steps[sid] = "done"

    def complete(step_id: str) -> None:
        steps[step_id] = "done"

    if "query planner" in lowered:
        activate("planner")
        if "selected hn" in lowered:
            complete("planner")
    if "hn demand" in lowered or "search_hacker_news" in lowered or "hn fallback" in lowered or "completing hn" in lowered:
        activate("research_hn")
        if "returned" in lowered or "collected" in lowered or "finished search_hacker_news" in lowered:
            complete("research_hn")
    if "dev supply" in lowered or "search_dev_to" in lowered or "dev.to fallback" in lowered or "completing dev" in lowered:
        activate("research_dev")
        if "returned" in lowered or "collected" in lowered or "finished search_dev_to" in lowered:
            complete("research_dev")
    if "engram memory" in lowered:
        activate("research_engram")
        if "returned" in lowered or "found" in lowered or "no prior memories" in lowered:
            complete("research_engram")
    if "devrel ideation writer" in lowered or "ideation writer" in lowered:
        activate("writer")
        if "producing the report" in lowered:
            complete("writer")
    if "assembling report" in lowered or "storing research summary" in lowered or "research complete" in lowered:
        activate("assembly")
        complete("assembly")
        complete("planner")
        complete("writer")


def render_pipeline_stepper() -> str:
    lines = ["**Pipeline**"]
    for step_id, label in PIPELINE_STEPS:
        state = st.session_state.pipeline_steps.get(step_id, "pending")
        lines.append(f"{STEP_ICON.get(state, '○')} {label}")
    return "\n".join(lines)


def truncate_judge_note(note: str, limit: int = 320) -> str:
    cleaned = " ".join(note.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def assistant_prompt_for_missing() -> str:
    missing = missing_fields(st.session_state.context)
    if not missing:
        return (
            "I’ve got enough to work with. Ask me to find content ideas or a trend digest, and I’ll run the Agno team to "
            "research HN and DEV in parallel, check Engram memory, and return ranked trends plus talk/blog ideas."
        )
    if len(missing) == 1:
        return f"One thing I still need before I can run it: {missing[0]}."
    return "I’m close. I still need " + ", ".join(missing[:-1]) + f", and {missing[-1]}."


def persist_session_env(values: dict[str, str]) -> None:
    env_path = APP_DIR / ".env"
    existing: dict[str, str] = {}
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" not in raw_line or raw_line.strip().startswith("#"):
                continue
            key, value = raw_line.split("=", 1)
            existing[key] = value
    existing.update({key: value for key, value in values.items() if value})
    lines = [f"{key}={value}" for key, value in existing.items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run_brief(
    context: CompanyContext,
    limit: int,
    on_progress=None,
):
    settings = get_settings(require_nebius=True)
    if st.session_state.memory_store is None:
        st.session_state.memory_store = create_memory_store(
            settings.engram_api_key,
            settings.engram_namespace,
            settings.engram_conversation_id,
        )

    def on_stage(message: str) -> None:
        st.session_state.stage_messages.append(message)
        update_pipeline_from_message(message)
        if on_progress is not None:
            on_progress(message)

    return await run_autonomous_content_team(
        context=context,
        settings=settings,
        memory_store=st.session_state.memory_store,
        limit=limit,
        on_stage=on_stage,
        engram_user_id=st.session_state.engram_user_id,
        conversation_id=settings.engram_conversation_id or st.session_state.conversation_id,
    )


def render_progress_log(messages: list[str], max_lines: int = 14) -> str:
    recent = messages[-max_lines:]
    return "\n".join(f"- {message}" for message in recent)


def _merge_context_update(update: dict) -> bool:
    changed = False
    for field in (
        "company_name",
        "product",
        "audience",
        "seed_keywords",
        "competitors",
        "existing_topics",
    ):
        value = update.get(field)
        if value in (None, "", []):
            continue
        if field in {"seed_keywords", "competitors", "existing_topics"}:
            if isinstance(value, str):
                items = [item.strip() for item in value.split(",") if item.strip()]
            elif isinstance(value, list):
                items = [str(item).strip() for item in value if str(item).strip()]
            else:
                items = [str(value).strip()]
            if items and not st.session_state.context[field]:
                st.session_state.context[field] = items[:10]
                changed = True
        elif not st.session_state.context[field].strip():
            st.session_state.context[field] = str(value).strip()
            changed = True
    return changed


async def enrich_context_with_llm(prompt: str) -> bool:
    settings = get_settings(require_nebius=False)
    if not settings.nebius_api_key:
        return False
    model = build_model(settings)
    agent = make_agent(model, CONTEXT_EXTRACTOR_PROMPT, "context_extractor")
    request = {
        "user_message": prompt,
        "current_context": st.session_state.context,
        "recent_chat": st.session_state.messages[-6:],
    }
    try:
        payload = parse_json_object(await run_agent(agent, json.dumps(request, ensure_ascii=False)))
    except Exception:
        return False
    return _merge_context_update(payload)


async def route_prompt_with_llm(prompt: str) -> str:
    settings = get_settings(require_nebius=False)
    fallback_intent = "chat"
    if wants_current_report_followup(prompt) and st.session_state.latest_result is not None:
        fallback_intent = "followup"
    elif wants_memory_lookup(prompt):
        fallback_intent = "memory_lookup"
    elif wants_brief_run(prompt, st.session_state.context):
        fallback_intent = "research_run"
    elif st.session_state.latest_result is not None:
        fallback_intent = "followup"

    if not settings.nebius_api_key:
        return fallback_intent

    model = build_model(settings)
    agent = make_agent(model, ROUTER_PROMPT, "message_router")
    request = {
        "user_message": prompt,
        "current_context": st.session_state.context,
        "has_latest_report": st.session_state.latest_result is not None,
        "missing_required_context": missing_fields(st.session_state.context),
        "recent_chat": st.session_state.messages[-6:],
    }
    try:
        payload = parse_json_object(
            await asyncio.wait_for(
                run_agent(agent, json.dumps(request, ensure_ascii=False)),
                timeout=ROUTER_TIMEOUT_SECONDS,
            )
        )
    except Exception:
        return fallback_intent

    intent = str(payload.get("intent", "")).strip().lower()
    requires_fresh_sources = payload.get("requires_fresh_sources")
    if intent == "research_run" and requires_fresh_sources is False:
        return fallback_intent if fallback_intent != "chat" else "memory_lookup"
    if intent in {"memory_lookup", "research_run", "followup", "chat"}:
        return intent
    return fallback_intent


async def store_product_context_memory(context: CompanyContext) -> list[str]:
    fingerprint = product_context_fingerprint(context)
    if fingerprint == st.session_state.get("stored_context_fingerprint", ""):
        return []
    if st.session_state.memory_store is None:
        settings = get_settings(require_nebius=False)
        st.session_state.memory_store = create_memory_store(
            settings.engram_api_key,
            settings.engram_namespace,
            settings.engram_conversation_id,
        )
    notes = await st.session_state.memory_store.store_product_context(
        context=context,
        user_id=st.session_state.engram_user_id,
    )
    if any(note.startswith("Stored product context") for note in notes):
        st.session_state.stored_context_fingerprint = fingerprint
    return notes


def product_context_fingerprint(context: CompanyContext) -> str:
    payload = {
        "company_name": context.company_name,
        "product": context.product,
        "audience": context.audience,
        "seed_keywords": context.seed_keywords,
        "competitors": context.competitors,
        "existing_topics": context.existing_topics,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def search_memory_answer(prompt: str) -> str:
    settings = get_settings(require_nebius=False)
    if st.session_state.memory_store is None:
        st.session_state.memory_store = create_memory_store(
            settings.engram_api_key,
            settings.engram_namespace,
            settings.engram_conversation_id,
        )
    search_queries = _memory_lookup_queries(prompt)
    search_results = await asyncio.gather(
        *[
            st.session_state.memory_store.search(
                query=query,
                user_id=st.session_state.engram_user_id,
                limit=8 if index == 0 else 4,
            )
            for index, query in enumerate(search_queries)
        ]
    )
    memories = _merge_memory_records(search_results)
    if not memories:
        return current_research_context_answer(prompt) or "I don’t see prior useful research for that yet."

    cleaned_memories = [
        " ".join(memory.content.split())
        for memory in memories[:8]
        if _memory_content_is_useful(memory.content)
    ]
    if not cleaned_memories:
        return current_research_context_answer(prompt) or "I don’t see that we’ve researched a concrete product or topic for that yet."

    if settings.nebius_api_key:
        model = build_model(settings)
        agent = make_agent(model, MEMORY_SUMMARIZER_PROMPT, "memory_summarizer")
        request = {
            "user_question": prompt,
            "memories": cleaned_memories,
        }
        try:
            answer = await run_agent(agent, json.dumps(request, ensure_ascii=False))
            cleaned = answer.strip()
            if cleaned and "unknown model error" not in cleaned.lower():
                memory_answer = _clean_memory_answer(cleaned)
                current_answer = current_research_context_answer(prompt)
                if current_answer and current_answer.lower() not in memory_answer.lower():
                    memory_answer = _remove_current_context_conflicts(memory_answer)
                    return f"{current_answer}\n\nFrom older stored context: {memory_answer}"
                return memory_answer
        except Exception as exc:
            logging.warning("Memory summarizer LLM call failed: %s", exc)

    first = cleaned_memories[0][:240]
    current_answer = current_research_context_answer(prompt)
    if current_answer:
        return f"{current_answer}\n\nFrom older stored context, the clearest thing I found is: {first}"
    return f"Yes, we have some previous context. The clearest thing I found is: {first}"


MEMORY_QUERY_STOPWORDS = {
    "what",
    "which",
    "have",
    "has",
    "were",
    "was",
    "we",
    "you",
    "researched",
    "research",
    "before",
    "past",
    "previously",
    "previous",
    "recently",
    "lately",
    "include",
    "available",
    "products",
    "product",
    "topics",
    "topic",
    "ideas",
    "idea",
    "reports",
    "report",
    "and",
    "or",
    "if",
    "the",
    "for",
    "about",
    "related",
}


def _extract_memory_product_hints(prompt: str) -> list[str]:
    hints: list[str] = []
    for match in re.finditer(r"\b[a-zA-Z0-9][a-zA-Z0-9._-]{1,32}\b", prompt):
        token = match.group(0).strip(".,?!:;()[]{}")
        lowered = token.lower()
        if lowered in MEMORY_QUERY_STOPWORDS:
            continue
        if len(token) < 3 and not any(char.isdigit() for char in token):
            continue
        looks_product_like = (
            any(char.isdigit() for char in token)
            or "." in token
            or "-" in token
            or token[:1].isupper()
        )
        if looks_product_like and lowered not in {item.lower() for item in hints}:
            hints.append(token)
    return hints[:5]


def _memory_lookup_queries(prompt: str) -> list[str]:
    queries = [prompt]
    for hint in _extract_memory_product_hints(prompt):
        queries.extend(
            [
                f"Research summary for {hint}",
                f"Product context for {hint}",
                hint,
            ]
        )
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = " ".join(query.split()).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(query)
    return deduped[:12]


def _merge_memory_records(search_results: list[list[MemoryRecord]]) -> list[MemoryRecord]:
    merged: list[MemoryRecord] = []
    seen: set[str] = set()
    for result_set in search_results:
        for memory in result_set:
            normalized = " ".join(memory.content.split()).lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(memory)
    return merged


def current_research_context_answer(prompt: str) -> str | None:
    result = st.session_state.get("latest_result")
    if result is None:
        return None
    lowered = prompt.lower()
    if not any(term in lowered for term in ("product", "topic", "idea", "report", "researched", "suggested")):
        return None
    context = result.context
    company = context.company_name or result.report.company or context.product
    product = context.product or company
    if not company and not product:
        return None
    ideas = ", ".join(idea.title for idea in result.report.content_ideas[:3])
    if ideas:
        return f"In this session, we researched {company or product} ({product}) and suggested ideas like {ideas}."
    return f"In this session, we researched {company or product} ({product})."


def _clean_memory_answer(answer: str) -> str:
    cleaned = answer.strip()
    cleaned = cleaned.replace("Engram Memory", "prior research")
    cleaned = cleaned.replace("Engram memory", "prior research")
    cleaned = cleaned.replace("Engram", "prior research")
    cleaned = cleaned.replace("our latest one", "previously researched")
    cleaned = cleaned.replace("the latest one", "previously researched")
    cleaned = cleaned.replace("latest one", "previously researched")
    paragraphs: list[str] = []
    seen: set[str] = set()
    for paragraph in cleaned.split("\n\n"):
        normalized = " ".join(paragraph.split()).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        paragraphs.append(paragraph.strip())
    return "\n\n".join(paragraphs).strip()


def _remove_current_context_conflicts(answer: str) -> str:
    result = st.session_state.get("latest_result")
    if result is None:
        return answer
    context = result.context
    terms = [
        context.company_name,
        context.product.split(",", 1)[0],
        result.report.company,
    ]
    for name in (context.company_name, result.report.company):
        first_word = (name or "").strip().split(" ", 1)[0]
        if len(first_word) > 2:
            terms.append(first_word)
    terms = [term.lower().strip() for term in terms if term and len(term.strip()) > 2]
    if not terms:
        return answer

    stale_markers = (
        "don't see",
        "do not see",
        "haven't researched",
        "have not researched",
        "not researched",
        "no evidence",
        "not yet",
    )
    pieces = re.split(r"(?<=[.!?])\s+", answer)
    filtered = [
        piece
        for piece in pieces
        if not (
            any(term in piece.lower() for term in terms)
            and any(marker in piece.lower() for marker in stale_markers)
        )
    ]
    return " ".join(piece.strip() for piece in filtered if piece.strip()).strip()


def _memory_content_is_useful(content: str) -> bool:
    lowered = content.lower()
    noisy_patterns = (
        "i still need",
        "the user asked",
        "user requested assistance",
        "ask me to find",
        "researching recent",
        "generated the report below",
        "engram memory queued",
        "quality judge",
        "detailed reasoning",
        "publishing briefs",
        "publishing opportunities",
        "seo pages",
        "seo gap",
        "technical seo",
    )
    if any(pattern in lowered for pattern in noisy_patterns):
        return False
    useful_patterns = (
        "product context for",
        "research summary for",
        "top developer trends",
        "top talk/blog ideas",
        "key demand and supply gaps",
        "product/category",
        "seed keywords",
        "audience",
    )
    return any(pattern in lowered for pattern in useful_patterns)


def source_title_lookup(result) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in result.hn_items:
        if item.url and item.title:
            lookup[item.url] = item.title
    for article in result.dev_articles:
        if article.url and article.title:
            lookup[article.url] = article.title
    return lookup


def markdown_source_links(
    urls: list[str],
    lookup: dict[str, str],
    empty_text: str,
    limit: int = 4,
) -> str:
    if not urls:
        return f"- {empty_text}"
    lines = []
    for url in urls[:limit]:
        title = lookup.get(url, url)
        safe_title = title.replace("[", "(").replace("]", ")")
        lines.append(f"- [{safe_title}]({url})" if title != url else f"- {url}")
    return "\n".join(lines)


def render_metric_row(items: list[tuple[str, str | int]]) -> None:
    chips = "".join(
        f"<span class='eca-metric'><strong>{html.escape(str(label))}:</strong>&nbsp;{html.escape(str(value))}</span>"
        for label, value in items
    )
    st.markdown(f"<div class='eca-metric-row'>{chips}</div>", unsafe_allow_html=True)


def render_structured_report(result) -> None:
    lookup = source_title_lookup(result)
    report = result.report

    st.subheader("What to publish next")
    st.markdown(f"<p class='eca-section-note'>{html.escape(report.summary)}</p>", unsafe_allow_html=True)
    for index, idea in enumerate(report.content_ideas, 1):
        with st.container(border=True):
            st.markdown(f"### {index}. {idea.title}")
            render_metric_row(
                [
                    ("Score", idea.score),
                    ("Format", idea.format),
                    ("Confidence", idea.confidence),
                ]
            )
            st.markdown(f"**Audience fit:** {idea.angle}")
            st.markdown(f"**DEV supply gap:** {idea.dev_gap}")
            col_hn, col_dev = st.columns(2)
            with col_hn:
                st.markdown("**HN demand**")
                st.markdown(
                    markdown_source_links(
                        idea.hn_evidence,
                        lookup,
                        "No strong HN evidence found in this run.",
                    )
                )
            with col_dev:
                st.markdown("**DEV.to supply**")
                st.markdown(
                    markdown_source_links(
                        idea.dev_links,
                        lookup,
                        "No specific DEV.to article matched this idea closely.",
                    )
                )
            if idea.outline:
                st.markdown("**Suggested outline**")
                st.markdown("\n".join(f"- {item}" for item in idea.outline[:6]))

    st.subheader("Trend digest")
    for index, trend in enumerate(report.trend_digest, 1):
        with st.expander(f"{index}. {trend.topic} · intensity {trend.intensity_score}"):
            st.markdown(trend.why_trending)
            st.markdown(f"**DEV saturation:** {trend.dev_saturation}")
            col_hn, col_dev = st.columns(2)
            with col_hn:
                st.markdown("**HN links**")
                st.markdown(
                    markdown_source_links(
                        trend.hn_links,
                        lookup,
                        "No strong HN evidence found in this run.",
                    )
                )
            with col_dev:
                st.markdown("**DEV.to links**")
                st.markdown(
                    markdown_source_links(
                        trend.dev_links,
                        lookup,
                        "No specific DEV.to article matched this trend closely.",
                    )
                )


def render_grouped_evidence(result) -> None:
    lookup = source_title_lookup(result)
    st.markdown("Grouped by recommendation, so evidence can be checked against the exact idea it supports.")
    for index, idea in enumerate(result.report.content_ideas, 1):
        with st.expander(f"Idea {index}: {idea.title}", expanded=index == 1):
            col_hn, col_dev = st.columns(2)
            with col_hn:
                st.markdown("**HN demand evidence**")
                st.markdown(
                    markdown_source_links(
                        idea.hn_evidence,
                        lookup,
                        "No strong HN evidence found in this run.",
                    )
                )
            with col_dev:
                st.markdown("**DEV.to supply check**")
                st.markdown(
                    markdown_source_links(
                        idea.dev_links,
                        lookup,
                        "No specific DEV.to article matched this idea closely.",
                    )
                )
                st.caption(idea.dev_gap)

    with st.expander("All collected HN items"):
        for item in result.hn_items:
            meta = " · ".join(
                part
                for part in [
                    item.created_at,
                    f"{item.points} points" if item.points is not None else "",
                    f"{item.num_comments} comments" if item.num_comments is not None else "",
                ]
                if part
            )
            st.markdown(f"- [{item.title}]({item.url})" + (f" — {meta}" if meta else ""))
    with st.expander("All collected DEV.to articles"):
        for article in result.dev_articles:
            meta = " · ".join(
                part
                for part in [
                    article.published_at,
                    ", ".join(article.tags[:4]) if article.tags else "",
                ]
                if part
            )
            st.markdown(f"- [{article.title}]({article.url})" + (f" — {meta}" if meta else ""))
            if article.body_excerpt:
                st.caption(article.body_excerpt[:220])


init_state()

with st.sidebar:
    st.subheader("Credentials")
    st.markdown(
        f"""
        <div class="eca-brand-card">
          <img class="eca-sidebar-logo" src="{_png_data_uri(APP_DIR / "assets" / "Nebius.png")}" alt="Nebius" style="width:175px;height:42px;object-fit:contain;">
        </div>
        """,
        unsafe_allow_html=True,
    )
    load_project_env()
    nebius_key = st.text_input(
        "Nebius API Key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
        help="Required for Agno agents via Nebius Token Factory.",
    )
    st.markdown(
        f"""
        <div class="eca-brand-card">
          <img class="eca-sidebar-logo" src="{_png_data_uri(APP_DIR / "assets" / "Weaviate_long.png")}" alt="Weaviate" style="width:175px;height:42px;object-fit:contain;">
        </div>
        """,
        unsafe_allow_html=True,
    )
    engram_key = st.text_input(
        "Engram API Key",
        value=os.getenv("ENGRAM_API_KEY", ""),
        type="password",
        help="Optional. Enables persistent Weaviate Engram Memory.",
    )
    if st.button("Save API Keys", use_container_width=True):
        if nebius_key:
            os.environ["NEBIUS_API_KEY"] = nebius_key
        if engram_key:
            os.environ["ENGRAM_API_KEY"] = engram_key
        persist_session_env(
            {
                "NEBIUS_API_KEY": nebius_key,
                "NEBIUS_MODEL": os.getenv("NEBIUS_MODEL", DEFAULT_MODEL),
                "ENGRAM_API_KEY": engram_key,
            }
        )
        st.session_state.memory_store = None
        st.success("Saved for this session.")

    st.caption(f"Model: {os.getenv('NEBIUS_MODEL', DEFAULT_MODEL)}")
    st.caption("LLM API: Nebius Token Factory")
    st.caption("HN: no key")
    st.caption("DEV: public API")
    st.caption("Nebius detected" if os.getenv("NEBIUS_API_KEY") else "Nebius key missing")
    st.caption(
        "Engram Memory enabled"
        if os.getenv("ENGRAM_API_KEY")
        else "Engram missing; memory disabled"
    )

if not st.session_state.messages:
    welcome = (
        "Tell me about your product and audience, then ask for a **trend digest** and **talk/blog ideas**. "
        "The Agno agents will choose searches, gather Hacker News demand, DEV.to supply gaps, and Engram memory, then write a grounded report.\n\n"
        "Example:\n\n"
        "*I run raah.dev, a web analytics and network observability tool. My audience is backend engineers "
        "who care about latency, error rates, and user-side ISP behavior. "
        "Research what developers are discussing on HN, check DEV.to saturation, and suggest talk and blog ideas "
        "around debugging production services.*\n\n"
        "Follow-ups you can try after a report: *What did we find?* or *Show evidence for idea 1*."
    )
    st.session_state.messages.append({"role": "assistant", "content": welcome})

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

chat_placeholder = (
    "Research is running. Please wait for the current report..."
    if st.session_state.is_running
    else "Describe your product… or ask for a trend digest and talk/blog ideas…"
)
prompt = st.chat_input(chat_placeholder, disabled=st.session_state.is_running)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if st.session_state.is_running:
        response = "I’m still running the current report. I’ll be ready for follow-up questions as soon as it finishes."
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.stop()

    parsed_context = apply_prompt_context(prompt, st.session_state.context)
    try:
        prompt_intent = asyncio.run(route_prompt_with_llm(prompt))
        if prompt_intent == "followup" and st.session_state.latest_result is None:
            prompt_intent = "no_report_followup"
    except Exception:
        prompt_intent = (
            "research_run"
            if wants_explicit_research_run(prompt)
            else
            "followup"
            if wants_current_report_followup(prompt) and st.session_state.latest_result is not None
            else
            "no_report_followup"
            if wants_current_report_followup(prompt) and st.session_state.latest_result is None
            else
            "memory_lookup"
            if wants_memory_lookup(prompt)
            else "research_run"
            if wants_brief_run(prompt, st.session_state.context)
            else "chat"
        )
    wants_run = prompt_intent == "research_run"
    if wants_run:
        try:
            parsed_context = asyncio.run(enrich_context_with_llm(prompt)) or parsed_context
        except Exception:
            pass

    with st.chat_message("assistant"):
        followup = (
            followup_response(prompt, st.session_state.latest_result)
            if prompt_intent == "followup"
            else None
        )
        if prompt_intent == "followup" and followup:
            response = followup
            st.markdown(response)
        elif prompt_intent == "no_report_followup":
            response = (
                "I don’t have a generated report in this session yet, so there isn’t idea evidence to show. "
                "Tell me about the product and audience, then ask me to find trends or suggest talk/blog ideas."
            )
            st.markdown(response)
        elif prompt_intent == "memory_lookup":
            with st.spinner("Checking Engram Memory..."):
                response = asyncio.run(search_memory_answer(prompt))
            st.markdown(response)
        elif wants_run and missing_fields(st.session_state.context):
            response = conversational_response(
                prompt,
                st.session_state.context,
                st.session_state.latest_result,
            ) or assistant_prompt_for_missing()
            st.markdown(response)
        elif wants_run and not missing_fields(st.session_state.context):
            if not os.getenv("NEBIUS_API_KEY"):
                response = "I need a Nebius API key before I can run the autonomous agent team. Add it in the sidebar and click Save API Keys."
                st.warning(response)
            else:
                context = CompanyContext(**st.session_state.context)
                st.session_state.stage_messages = []
                reset_pipeline_steps()
                st.caption(
                    "Running Agno agents: GLM chooses HN/DEV searches, then HN, DEV.to, and Engram facts are gathered in parallel. "
                    "Live progress appears below."
                )
                started_at = time.time()
                st.session_state.is_running = True
                try:
                    with st.status(
                        f"Running {APP_NAME}...",
                        expanded=True,
                    ) as status:
                        pipeline_view = st.empty()
                        progress_log = st.empty()

                        def update_progress(message: str) -> None:
                            elapsed = int(time.time() - started_at)
                            status.update(
                                label=f"{message} ({elapsed}s elapsed)",
                                state="running",
                            )
                            pipeline_view.markdown(render_pipeline_stepper())
                            progress_log.markdown(
                                render_progress_log(st.session_state.stage_messages)
                            )

                        result = asyncio.run(
                            run_brief(
                                context,
                                st.session_state.limit,
                                on_progress=update_progress,
                            )
                        )
                        elapsed = int(time.time() - started_at)
                        status.update(
                            label=f"Research complete in {elapsed}s",
                            state="complete",
                        )
                        pipeline_view.markdown(render_pipeline_stepper())
                        progress_log.markdown(
                            render_progress_log(st.session_state.stage_messages)
                        )

                    st.session_state.latest_result = result
                    trends = result.report.trend_digest[:3]
                    ideas = result.report.content_ideas[:3]
                    summary_lines = [
                        f"Done. Found {len(result.report.trend_digest)} trends and "
                        f"{len(result.report.content_ideas)} talk/blog ideas."
                    ]
                    if trends:
                        summary_lines.append("")
                        summary_lines.append("Top trends:")
                        for i, trend in enumerate(trends, 1):
                            summary_lines.append(
                                f"{i}. **{trend.topic}** (intensity {trend.intensity_score})"
                            )
                    if ideas:
                        summary_lines.append("")
                        summary_lines.append("Top ideas:")
                        for i, idea in enumerate(ideas, 1):
                            summary_lines.append(
                                f"{i}. **{idea.title}** ({idea.format}, score {idea.score})"
                            )
                    summary_lines.append("")
                    summary_lines.append("See the full report below, or download as Markdown.")
                    response = "\n".join(summary_lines)
                    st.markdown(response)
                except Exception as exc:
                    response = f"Content report generation failed: {exc}"
                    st.error(response)
                finally:
                    st.session_state.is_running = False
        elif parsed_context:
            context_summary = render_context_summary(st.session_state.context)
            response = f"{context_summary}\n\n{assistant_prompt_for_missing()}"
            st.markdown(response)
        elif chat_response := conversational_response(
            prompt,
            st.session_state.context,
            st.session_state.latest_result,
        ):
            response = chat_response
            st.markdown(response)
        else:
            response = assistant_prompt_for_missing()
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if parsed_context and has_required_context(st.session_state.context):
            try:
                asyncio.run(
                    store_product_context_memory(CompanyContext(**st.session_state.context))
                )
            except Exception:
                pass

if st.session_state.latest_result:
    result = st.session_state.latest_result
    st.markdown("---")
    tab_brief, tab_evidence, tab_history = st.tabs(["Report", "Evidence", "Memory & Run History"])
    with tab_brief:
        render_structured_report(result)
        st.download_button(
            "Download Markdown",
            data=result.markdown,
            file_name="developer_trend_ideation_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with tab_evidence:
        render_grouped_evidence(result)
        with st.expander("Query plan", expanded=True):
            st.json(result.query_plan.to_dict())
    with tab_history:
        st.markdown("#### Engram Memory")
        st.caption(
            "Cross-session product research summaries stored in Weaviate Engram "
            f"(user: `{st.session_state.engram_user_id}`). "
            "Search is user-wide across old sessions in the same group; conversation id is stored only as metadata. "
            "Only compact trend and idea summaries are persisted, not agent run logs."
        )
        st.markdown(f"**Group:** `{get_settings(require_nebius=False).engram_namespace}`")
        st.markdown("**Old-session retrieval:** enabled through stable user/group search.")
        if result.memory_notes:
            for note in result.memory_notes:
                st.markdown(f"- {note}")
        else:
            st.info("No Engram store confirmation for this run.")
        preview = build_research_summary_preview(
            result.context,
            result.report,
            result.content_gaps,
        )
        if preview:
            st.markdown("**Stored summary preview**")
            st.markdown(preview)

        st.markdown("#### This run — Report checks")
        st.caption("Local formatting and evidence-link checks for this report only; Engram stores only compact memories.")
        if result.judge_score is not None:
            st.markdown(f"**Score:** {result.judge_score:.0f}/10")
        if result.judge_notes:
            for note in result.judge_notes:
                st.markdown(f"- {truncate_judge_note(note)}")
        elif result.judge_score is None:
            st.caption("No separate judge run recorded for this fast path.")

        st.markdown("#### This run — Agent progress")
        st.caption("Live pipeline log from the current Streamlit session.")
        if st.session_state.stage_messages:
            for stage in st.session_state.stage_messages:
                st.markdown(f"- {stage}")
        else:
            st.caption("No stage log captured for this run.")

        if result.team_member_responses:
            st.markdown("#### This run — Member responses")
            for note in result.team_member_responses:
                st.markdown(f"- {note}")

        st.markdown("#### Agno session trace")
        st.caption(
            "This is the current Streamlit session's agent progress log. "
            "Cross-session memory is stored only in Engram."
        )
        st.caption(f"Conversation scope: `{st.session_state.conversation_id}`")
