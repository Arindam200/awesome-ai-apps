"""Load a paper from arXiv or a PDF: full text plus renders of the figure-heavy pages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import defusedxml.ElementTree as ET
import httpx
import pymupdf

ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
MAX_TEXT_CHARS = 600_000  # ~150k tokens, well inside Kimi's 1M context
MAX_FIGURE_PAGES = 8
USER_AGENT = "paper-to-interactive-explainer/0.1 (awesome-ai-apps demo)"


@dataclass
class Paper:
    title: str
    authors: list[str]
    abstract: str
    source_url: str
    text: str
    page_count: int
    figures: list[tuple[int, bytes]] = field(default_factory=list)  # (page number, JPEG)

    @property
    def citation(self) -> str:
        who = ", ".join(self.authors[:3]) + (" et al." if len(self.authors) > 3 else "")
        return f"{self.title} ({who})" if who else self.title


def parse_arxiv_id(text: str) -> str | None:
    m = ARXIV_ID.search(text or "")
    return m.group(0) if m else None


def fetch_arxiv(arxiv_id: str) -> Paper:
    base = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
    with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as http:
        meta = {"title": "", "authors": [], "abstract": ""}
        try:
            feed = http.get("https://export.arxiv.org/api/query", params={"id_list": base}).text
            ns = {"a": "http://www.w3.org/2005/Atom"}
            entry = ET.fromstring(feed).find("a:entry", ns)
            if entry is not None:
                meta["title"] = " ".join((entry.findtext("a:title", "", ns) or "").split())
                meta["abstract"] = " ".join((entry.findtext("a:summary", "", ns) or "").split())
                meta["authors"] = [a.findtext("a:name", "", ns) for a in entry.findall("a:author", ns)]
        except Exception:
            pass  # metadata is a nicety; the PDF is what matters
        pdf = http.get(f"https://arxiv.org/pdf/{arxiv_id}")
        pdf.raise_for_status()
    return load_pdf(pdf.content, source_url=f"https://arxiv.org/abs/{arxiv_id}", **meta)


def load_pdf(pdf_bytes: bytes, source_url: str = "", title: str = "", authors: list[str] | None = None, abstract: str = "") -> Paper:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages_text, scores = [], []
    for i, page in enumerate(doc):
        pages_text.append(f"[page {i + 1}]\n{page.get_text()}")
        # Figures are either raster images or lots of vector drawing ops.
        score = 5 * len(page.get_images()) + min(len(page.get_drawings()), 400) / 20
        if re.search(r"\b(Figure|Fig\.)\s*\d", page.get_text()):
            score += 3
        scores.append((score, i))

    text = "\n\n".join(pages_text)[:MAX_TEXT_CHARS]
    picked = sorted(i for s, i in sorted(scores, reverse=True)[:MAX_FIGURE_PAGES] if s >= 4)
    figures = []
    for i in picked:
        pix = doc[i].get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4))
        figures.append((i + 1, pix.tobytes("jpeg", jpg_quality=82)))

    if not title:
        title = (doc.metadata or {}).get("title") or next((ln.strip() for ln in doc[0].get_text().splitlines() if len(ln.strip()) > 8), "Untitled paper")
    page_count = len(doc)
    doc.close()
    return Paper(title=title, authors=authors or [], abstract=abstract, source_url=source_url,
                 text=text, page_count=page_count, figures=figures)
