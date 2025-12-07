"""
Example ingestion script for the original Studio1 Customer Support demo.

Today, the recommended way to ingest docs is via the **Streamlit sidebar**
(paste URLs and click "Extract & store to Memori"). This script is kept as a
convenience for rebuilding the Studio1 knowledge base from its public
docs/marketing site.

It uses Firecrawl to crawl https://www.studio1hq.com/ and ingests the content
into Memori v3 as a searchable knowledge base.
"""

import os
from typing import List

from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from memori import Memori
from openai import OpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


load_dotenv()

# Primary docs site root used for broad crawling
STUDIO1_URL = "https://docs.studio1hq.com/"

# High-value pages we always want to ingest explicitly, even if the crawler
# misses them due to depth/links. This includes services, legal, and marketing
# "About" pages.
STUDIO1_STATIC_URLS = [
    "https://docs.studio1hq.com/about-us",
    "https://docs.studio1hq.com/faq",
    "https://docs.studio1hq.com/services/technical-content",
    "https://docs.studio1hq.com/services/developer-advocacy",
    "https://docs.studio1hq.com/services/tech-video-production",
    "https://docs.studio1hq.com/services/audit-services",
    "https://docs.studio1hq.com/services/organic-campaign",
    "https://docs.studio1hq.com/services/product-launch",
    "https://docs.studio1hq.com/services/influencer-management",
    "https://docs.studio1hq.com/terms-of-use",
    "https://docs.studio1hq.com/privacy-policy",
    "https://www.studio1hq.com/about-us",
]


def _init_memori() -> tuple[Memori, OpenAI]:
    """Initialize Memori v3 with SQLAlchemy + OpenAI, mirroring ai_consultant_agent.

    Returns (Memori instance, OpenAI client) so we can use the registered
    OpenAI client to drive Memori's automatic ingestion.
    """
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    db_path = os.getenv("SQLITE_DB_PATH", "./memori.sqlite")
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False},
    )

    # Optional connectivity check
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    client = OpenAI(api_key=openai_key)
    mem = Memori(conn=SessionLocal).openai.register(client)
    mem.attribution(entity_id="studio1-support-kb", process_id="studio1-ingest")
    mem.config.storage.build()
    return mem, client


def _crawl_studio1() -> List[dict]:
    """Use Firecrawl to crawl the Studio1 docs site and return extracted pages."""
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "")
    if not firecrawl_key:
        raise RuntimeError("FIRECRAWL_API_KEY is not set.")

    app = FirecrawlApp(api_key=firecrawl_key)

    # Basic crawl config; this can be tuned later.
    # Modern Firecrawl Python SDK exposes a `crawl(url, *, limit, scrape_options, ...)`
    # signature and returns a Pydantic model (e.g. CrawlStatus / CrawlJob).
    limit = 50
    # Firecrawl v2 expects `scrape_options.formats` to be a ScrapeFormats model
    # or a list of *supported* format literals. "text" is not a valid format,
    # so we just request markdown + HTML and derive plain text ourselves later.
    scrape_options = {
        "formats": ["markdown", "html"],
        "onlyMainContent": True,
    }

    if hasattr(app, "crawl_url"):
        # Some SDK variants expose `crawl_url`; keep this for backwards-compat.
        job = app.crawl_url(
            url=STUDIO1_URL,
            limit=limit,
            scrape_options=scrape_options,
        )
    elif hasattr(app, "crawl"):
        # Preferred modern API, matching docs.firecrawl.dev.
        job = app.crawl(
            STUDIO1_URL,
            limit=limit,
            scrape_options=scrape_options,
        )
    else:
        raise RuntimeError(
            "Installed Firecrawl client has neither `crawl_url` nor `crawl` method. "
            "Please check your `firecrawl-py` version and docs."
        )

    # Normalize Firecrawl response into a list of page dicts.
    # - Newer SDKs return a Pydantic model (e.g. CrawlJob / CrawlStatus)
    # - Older SDKs may return a plain dict with a 'data' key
    if isinstance(job, dict):
        pages = job.get("data") or job.get("pages") or job
    else:
        # Pydantic models don't support `.get`, but do support attributes and `.model_dump()`.
        pages = (
            getattr(job, "data", None)
            or getattr(job, "pages", None)
            or getattr(job, "results", None)
        )
        if pages is None:
            if hasattr(job, "model_dump"):
                # Pydantic v2
                data = job.model_dump()
            elif hasattr(job, "dict"):
                # Backwards compat with Pydantic v1
                data = job.dict()
            else:
                raise RuntimeError(
                    f"Unexpected Firecrawl response type (no data/pages/results): {type(job)}"
                )
            pages = data.get("data") or data.get("pages") or data.get("results") or data

    if not isinstance(pages, list):
        raise RuntimeError(f"Unexpected Firecrawl response format: {type(pages)}")
    return pages


def _scrape_static_pages() -> List[dict]:
    """Use Firecrawl to scrape a fixed list of high-value Studio1 URLs."""
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "")
    if not firecrawl_key:
        raise RuntimeError("FIRECRAWL_API_KEY is not set.")

    app = FirecrawlApp(api_key=firecrawl_key)
    results: List[dict] = []

    for url in STUDIO1_STATIC_URLS:
        try:
            if hasattr(app, "scrape"):
                doc = app.scrape(
                    url=url,
                    formats=["markdown", "html"],
                    onlyMainContent=True,
                )
            elif hasattr(app, "scrape_url"):
                # Backwards-compat for older SDKs
                doc = app.scrape_url(
                    url=url,
                    scrape_options={
                        "formats": ["markdown", "html"],
                        "onlyMainContent": True,
                    },
                )
            else:
                raise RuntimeError(
                    "Installed Firecrawl client has neither `scrape` nor `scrape_url`."
                )

            # Normalise into a dict similar to crawl results
            if isinstance(doc, dict):
                data = doc.get("data") or doc
            else:
                if hasattr(doc, "model_dump"):
                    data = doc.model_dump()
                elif hasattr(doc, "dict"):
                    data = doc.dict()
                else:
                    data = doc

            # Some SDKs wrap the page document under "data"
            if isinstance(data, dict) and "markdown" in data or "html" in data:
                page = data
            elif isinstance(data, dict) and isinstance(data.get("data"), dict):
                page = data["data"]
            else:
                # Fallback – if it's already shaped like a page list, skip here
                if isinstance(data, list):
                    # Append each if we somehow got multiple docs back
                    for p in data:
                        if isinstance(p, dict):
                            results.append(p)
                    continue
                page = data

            if isinstance(page, dict):
                # Ensure URL is set for deduplication later
                page.setdefault("url", url)
                results.append(page)
        except Exception as e:
            print(f"[Firecrawl] Warning: could not scrape {url}: {e}")

    return results


def ingest():
    mem, client = _init_memori()
    crawled_pages = _crawl_studio1()
    static_pages = _scrape_static_pages()

    # Deduplicate by URL to avoid double-ingesting the same page from crawl+scrape
    pages: List[dict] = []
    seen_urls = set()

    def _add_pages(src_pages: List[dict]):
        for p in src_pages:
            url = None
            if isinstance(p, dict):
                meta = p.get("metadata") or {}
                url = p.get("url") or meta.get("sourceURL")
            if not url:
                # Fallback to id of object to prevent accidental merge
                key = id(p)
            else:
                key = url
            if key in seen_urls:
                continue
            seen_urls.add(key)
            pages.append(p)

    _add_pages(crawled_pages)
    _add_pages(static_pages)

    print(f"Fetched {len(pages)} pages from Studio1 docs + static URLs")

    for idx, page in enumerate(pages, start=1):
        # Firecrawl v2 returns Pydantic models (e.g. Document) rather than plain dicts.
        # Normalize each item into a dict first.
        if isinstance(page, dict):
            page_dict = page
        else:
            if hasattr(page, "model_dump"):
                page_dict = page.model_dump()
            elif hasattr(page, "dict"):
                page_dict = page.dict()
            else:
                raise RuntimeError(f"Unexpected page type from Firecrawl: {type(page)}")

        metadata = page_dict.get("metadata") or {}
        url = page_dict.get("url") or metadata.get("sourceURL") or STUDIO1_URL

        markdown = (
            page_dict.get("markdown")
            or page_dict.get("text")
            or page_dict.get("content")
            or ""
        )
        if not markdown:
            continue

        title = page_dict.get("title") or metadata.get("title") or f"Studio1 Page {idx}"

        doc_text = f"""Studio1 Documentation Page
Title: {title}
URL: {url}

Content:
{markdown}
"""
        print(f"Ingesting page {idx}: {url}")

        # Use the registered OpenAI client so Memori can automatically
        # capture this as a "conversation" / memory. We keep the prompt
        # lightweight and ask the model to simply acknowledge storage.
        try:
            _ = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Store the following Studio1 documentation page in "
                            "memory for future retrieval. Respond with a short "
                            "acknowledgement only.\n\n"
                            f"{doc_text}"
                        ),
                    }
                ],
            )
        except Exception as record_err:
            # Don't abort ingestion if a single record fails; just log it.
            print(f"[Memori] Could not index page {idx} ({url}): {record_err}")

    # Ensure any buffered writes are flushed to the backing store.
    try:
        adapter = getattr(mem.config.storage, "adapter", None)
        if adapter is not None:
            adapter.commit()
            adapter.close()
    except Exception as final_err:
        print(
            f"[Memori] Warning: issue committing/closing storage adapter: {final_err}"
        )

    print("Ingestion complete.")


if __name__ == "__main__":
    ingest()
