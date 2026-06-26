"""Render document pages to PNG with pymupdf for the citation viewer.

Stores both pixel dims (rendered) and point dims (native PDF) per page —
the frontend scales Unsiloed bboxes using whichever space they turn out to
be in (see bbox calibration note in the README).
"""

import logging
import subprocess
from pathlib import Path

import fitz  # pymupdf
from sqlalchemy.orm import Session

from app.config import PAGES_DIR
from app.models import Document, DocumentPage

logger = logging.getLogger(__name__)

RENDER_SCALE = 2.0  # ~144 DPI

CONVERTIBLE = {".pptx", ".ppt", ".docx", ".doc", ".xlsx", ".xls"}


def _ensure_pdf(doc: Document) -> Path | None:
    """Return a path pymupdf can open. Office formats get converted via
    LibreOffice if available; otherwise skip (demo prefers PDF exports)."""
    path = Path(doc.file_path)
    if path.suffix.lower() not in CONVERTIBLE:
        return path
    converted = path.with_suffix(".pdf")
    if converted.exists():
        return converted
    try:
        subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(path.parent), str(path)],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return converted if converted.exists() else None
    except (FileNotFoundError, subprocess.SubprocessError):
        logger.warning("LibreOffice unavailable — cannot render pages for %s", path.name)
        return None


def render_pages(db: Session, doc: Document) -> int:
    """Render every page of the document to PNG; idempotent."""
    existing = {p.page_no for p in doc.pages}
    pdf_path = _ensure_pdf(doc)
    if pdf_path is None:
        return 0

    try:
        pdf = fitz.open(pdf_path)
    except Exception:
        logger.exception("cannot open %s for page rendering", pdf_path)
        return 0

    out_dir = PAGES_DIR / str(doc.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered = 0
    for i, page in enumerate(pdf):
        page_no = i + 1  # 1-based, matching Unsiloed
        if page_no in existing:
            continue
        pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE))
        image_path = out_dir / f"{page_no}.png"
        pix.save(image_path)
        db.add(
            DocumentPage(
                document_id=doc.id,
                page_no=page_no,
                image_path=str(image_path),
                width_px=pix.width,
                height_px=pix.height,
                width_pt=page.rect.width,
                height_pt=page.rect.height,
            )
        )
        rendered += 1

    doc.page_count = pdf.page_count
    pdf.close()
    db.commit()
    return rendered
