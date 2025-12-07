"""
Customer Support Voice Agent with Memori v3

Streamlit app:
- Single chat interface for customer support on top of your own docs/FAQs.
- Uses Memori v3 + OpenAI GPT-4o for grounded answers.
- Uses OpenAI TTS for optional voice responses.

Prereqs:
- Set OPENAI_API_KEY (and optional SQLITE_DB_PATH, e.g. ./memori.sqlite).
- Set FIRECRAWL_API_KEY to ingest documentation URLs into Memori.
"""

import base64
import os
from io import BytesIO
from typing import Optional

import streamlit as st
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from memori import Memori
from openai import OpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


load_dotenv()


def _load_inline_image(path: str, height_px: int) -> str:
    """Return an inline <img> tag for a local PNG, or empty string on failure."""
    try:
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        return (
            f"<img src='data:image/png;base64,{encoded}' "
            f"style='height:{height_px}px; width:auto; display:inline-block; "
            f"vertical-align:middle; margin:0 8px;' alt='Logo'>"
        )
    except Exception:
        return ""


def _init_memori_with_openai() -> Optional[Memori]:
    """Initialize Memori v3 + OpenAI client, mirroring ai_consultant_agent."""
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        st.warning("OPENAI_API_KEY is not set – Memori v3 will not be active.")
        return None

    try:
        db_path = os.getenv("SQLITE_DB_PATH", "./memori.sqlite")
        database_url = f"sqlite:///{db_path}"
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )

        # Optional DB connectivity check
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        client = OpenAI(api_key=openai_key)
        mem = Memori(conn=SessionLocal).openai.register(client)
        # Generic attribution for customer-support use-cases
        mem.attribution(
            entity_id="customer-support-user", process_id="customer-support"
        )
        mem.config.storage.build()

        st.session_state.memori = mem
        st.session_state.openai_client = client
        return mem
    except Exception as e:
        st.warning(f"Memori v3 initialization note: {e}")
        return None


def _synth_audio(text: str, client: OpenAI) -> Optional[BytesIO]:
    """Call OpenAI TTS to synthesize speech for the given text."""
    try:
        # Using audio.speech.create (high-level helper) if available
        result = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=text,
        )
        audio_bytes = result.read() if hasattr(result, "read") else result
        if isinstance(audio_bytes, bytes):
            return BytesIO(audio_bytes)
        return None
    except Exception as e:
        st.warning(f"TTS error: {e}")
        return None


def _ingest_urls_with_firecrawl(mem: Memori, client: OpenAI, urls: list[str]) -> int:
    """Ingest one or more documentation base URLs into Memori using Firecrawl."""
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "")
    if not firecrawl_key:
        raise RuntimeError("FIRECRAWL_API_KEY is not set – cannot ingest docs.")

    app = FirecrawlApp(api_key=firecrawl_key)
    all_pages = []

    for base_url in urls:
        try:
            job = app.crawl(
                base_url,
                limit=50,
                scrape_options={
                    "formats": ["markdown", "html"],
                    "onlyMainContent": True,
                },
            )

            # Normalize Firecrawl response into a list of page dicts (mirrors ingest_studio1).
            if isinstance(job, dict):
                pages = job.get("data") or job.get("pages") or job
            else:
                pages = (
                    getattr(job, "data", None)
                    or getattr(job, "pages", None)
                    or getattr(job, "results", None)
                )
                if pages is None:
                    if hasattr(job, "model_dump"):
                        data = job.model_dump()
                    elif hasattr(job, "dict"):
                        data = job.dict()
                    else:
                        data = job
                    pages = (
                        data.get("data")
                        or data.get("pages")
                        or data.get("results")
                        or data
                    )

            if isinstance(pages, list):
                all_pages.extend(pages)
            elif isinstance(pages, dict):
                all_pages.append(pages)
        except Exception as e:
            st.warning(f"Firecrawl issue while crawling {base_url}: {e}")

    # Deduplicate by URL
    dedup_pages = []
    seen_urls = set()
    for page in all_pages:
        url = None
        if isinstance(page, dict):
            meta = page.get("metadata") or {}
            url = page.get("url") or meta.get("sourceURL")
        key = url or id(page)
        if key in seen_urls:
            continue
        seen_urls.add(key)
        dedup_pages.append(page)

    company_name = st.session_state.get("company_name") or "the company"

    # Ingest pages into Memori by sending them through the registered OpenAI client.
    ingested = 0
    for idx, page in enumerate(dedup_pages, start=1):
        if isinstance(page, dict):
            page_dict = page
        else:
            if hasattr(page, "model_dump"):
                page_dict = page.model_dump()
            elif hasattr(page, "dict"):
                page_dict = page.dict()
            else:
                continue

        metadata = page_dict.get("metadata") or {}
        url = page_dict.get("url") or metadata.get("sourceURL") or urls[0]

        markdown = (
            page_dict.get("markdown")
            or page_dict.get("text")
            or page_dict.get("content")
            or ""
        )
        if not markdown:
            continue

        title = page_dict.get("title") or metadata.get("title") or f"Page {idx}"

        doc_text = f"""{company_name} Documentation Page
Title: {title}
URL: {url}

Content:
{markdown}
"""

        try:
            _ = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Store the following documentation page in memory for "
                            "future customer-support conversations. Respond with a "
                            "short acknowledgement only.\n\n"
                            f"{doc_text}"
                        ),
                    }
                ],
            )
            ingested += 1
        except Exception as e:
            st.warning(f"Memori/OpenAI issue ingesting {url}: {e}")

    # Flush writes to storage without closing the adapter (app keeps running).
    try:
        adapter = getattr(mem.config.storage, "adapter", None)
        if adapter is not None:
            adapter.commit()
    except Exception as e:
        st.warning(f"Memori commit note: {e}")

    return ingested


def main():
    # Page config
    st.set_page_config(
        page_title="Customer Support Voice Agent",
        layout="wide",
    )

    # Initialize session state
    if "memori" not in st.session_state or "openai_client" not in st.session_state:
        _init_memori_with_openai()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "company_name" not in st.session_state:
        st.session_state.company_name = ""

    # Inline title logos (reuse existing assets from other agents)
    memori_img_inline = _load_inline_image(
        "../job_search_agent/assets/Memori_Logo.png", height_px=90
    )

    title_html = f"""
<div style='display:flex; align-items:center; width:120%; padding:8px 0;'>
  <h1 style='margin:0; padding:0; font-size:2.2rem; font-weight:800; display:flex; align-items:center; gap:10px;'>
    <span>Customer Support Voice Agent with</span>
    {memori_img_inline}
  </h1>
</div>
"""
    st.markdown(title_html, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.subheader("🔑 API & Storage")

        firecrawl_api_key_input = st.text_input(
            "Firecrawl API Key",
            value=os.getenv("FIRECRAWL_API_KEY", ""),
            type="password",
            help="Used to crawl/scrape your documentation URLs into Memori.",
        )

        memori_api_key_input = st.text_input(
            "Memori API Key (optional)",
            value=os.getenv("MEMORI_API_KEY", ""),
            type="password",
            help="Used for Memori Advanced Augmentation and higher quotas.",
        )

        openai_api_key_input = st.text_input(
            "OpenAI API Key",
            value=os.getenv("OPENAI_API_KEY", ""),
            type="password",
            help="Your OpenAI API key for GPT-4o and TTS.",
        )

        company_name_input = st.text_input(
            "Company Name (optional)",
            value=st.session_state.company_name,
            help="Used to personalize prompts and titles.",
        )
        st.session_state.company_name = company_name_input.strip()

        if st.button("Save Settings"):
            if openai_api_key_input:
                os.environ["OPENAI_API_KEY"] = openai_api_key_input
            if firecrawl_api_key_input:
                os.environ["FIRECRAWL_API_KEY"] = firecrawl_api_key_input
            if memori_api_key_input:
                os.environ["MEMORI_API_KEY"] = memori_api_key_input
            st.success("✅ Settings saved for this session. Re-initializing Memori...")
            _init_memori_with_openai()

        st.markdown("---")
        st.markdown("### 📚 Ingest Docs into Memori")
        ingest_urls_text = st.text_area(
            "Documentation URLs (one per line)",
            placeholder="https://docs.yourcompany.com\nhttps://yourcompany.com/help",
            height=140,
        )
        if st.button("Extract & store to Memori"):
            urls = [u.strip() for u in ingest_urls_text.splitlines() if u.strip()]
            if not urls:
                st.warning("Please enter at least one URL to ingest.")
            elif (
                "memori" not in st.session_state
                or "openai_client" not in st.session_state
            ):
                st.warning(
                    "Memori / OpenAI client not initialized yet – check your API key above."
                )
            else:
                try:
                    count = _ingest_urls_with_firecrawl(
                        st.session_state.memori,
                        st.session_state.openai_client,
                        urls,
                    )
                    st.success(
                        f"✅ Ingested {count} documentation page(s) into Memori."
                    )
                except Exception as e:
                    st.error(f"❌ Ingestion error: {e}")

        st.markdown("---")
        st.markdown("### 💡 About the Agent")
        st.markdown(
            """
            This agent answers customer-support questions for **your own product or company**:
            - Docs, FAQs, services, pricing, and onboarding flows  
            - Product capabilities and common troubleshooting steps  

            Knowledge is built from whatever documentation URLs you ingest
            (e.g. `https://docs.yourcompany.com`) via **Firecrawl** and stored in **Memori v3**.

            Responses are powered by **OpenAI GPT-4o** and can optionally be read aloud using **OpenAI TTS**.
            """
        )

    if "openai_client" not in st.session_state:
        st.warning(
            "⚠️ OPENAI_API_KEY missing or Memori v3 failed to initialize – "
            "LLM responses will not work."
        )
        st.stop()

    client: OpenAI = st.session_state.openai_client
    mem: Memori = st.session_state.memori

    # Toggle for voice output
    col_voice, _ = st.columns([1, 3])
    with col_voice:
        enable_voice = st.checkbox("🔊 Enable voice responses", value=True)

    # Chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("Ask a customer-support question…")

    if user_input:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Assistant response
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking with your ingested knowledge…"):
                try:
                    # (Optional) Use Memori search to fetch relevant Studio1 context
                    kb_snippets = []
                    try:
                        # Only call .search if this Memori instance actually exposes it.
                        if hasattr(mem, "search"):
                            # Limit to most relevant 5 items
                            kb_snippets = mem.search(user_input, limit=5) or []
                    except Exception as search_err:
                        # Non-fatal – the assistant can still answer without KB snippets.
                        st.warning(f"Memori search issue: {search_err}")

                    kb_context = ""
                    if kb_snippets:
                        kb_context = "Here are some relevant snippets from the company knowledge base:\n"
                        for snip in kb_snippets:
                            kb_context += f"- {snip}\n"

                    # Resolve company name for this request
                    company_name = (
                        st.session_state.get("company_name") or "your company"
                    )

                    system_prompt = f"""You are a helpful customer support assistant for {company_name}.

Use ONLY the company's documentation and prior stored content in Memori to answer.
If something is unclear or not covered, say that it isn't in the docs instead of hallucinating.

Context from the knowledge base (may be partial):
{kb_context}
"""

                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_input},
                        ],
                    )
                    answer = response.choices[0].message.content or ""

                    st.session_state.messages.append(
                        {"role": "assistant", "content": answer}
                    )
                    st.markdown(answer)

                    # Optional voice output
                    if enable_voice and answer.strip():
                        audio_buf = _synth_audio(answer, client)
                        if audio_buf is not None:
                            audio_bytes = audio_buf.getvalue()
                            st.audio(audio_bytes, format="audio/mp3")
                except Exception as e:
                    err = f"❌ Error generating answer: {e}"
                    st.session_state.messages.append(
                        {"role": "assistant", "content": err}
                    )
                    st.error(err)


if __name__ == "__main__":
    main()
