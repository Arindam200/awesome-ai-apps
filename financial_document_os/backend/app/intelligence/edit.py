"""Document editing via the Unsiloed PDF Edit API + impact analysis.

Edit API edits by COORDINATES. We already store each field's citation bbox, so
"change the company address everywhere" = find every citation whose value
matches, convert its bbox to the editor's {left,top,width,height} space, and
send one edit call per affected document.

Coordinate space is locked by the calibration test (scripts/calibrate_edit.py);
BBOX_SCALE controls the conversion: "as_is" sends citation corner coords
unchanged (they are already in PDF-point space, which is what the editor uses).
"""

import json
import logging
import time

import fitz
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import EDITED_DIR, settings
from app.models import Document, DocumentEdit, DocumentPage, EntityCitation

logger = logging.getLogger(__name__)

EDIT_ENDPOINT = "/api/v1/pdf-editor/edit/reparse"


def citation_to_edit_item(citation_bbox: dict, replacement_text: str) -> dict:
    """Convert a stored citation {bbox:[x0,y0,x1,y1], page, page_width, page_height}
    into an Edit API item. Calibration (2026-06-13) confirmed the editor uses
    the citation's own coordinate space, so corners pass through as-is."""
    x0, y0, x1, y1 = citation_bbox["bbox"][:4]
    return {
        "type": "text",
        "page_number": int(citation_bbox.get("page", 1)),
        "bbox": {"left": round(x0, 2), "top": round(y0, 2),
                 "width": round(x1 - x0, 2), "height": round(y1 - y0, 2)},
        "replacement_text": replacement_text,
    }


def submit_edit(file_path: str, items: list[dict]) -> dict:
    """Call the Unsiloed Edit API. Returns the parsed response."""
    url = settings.unsiloed_edit_base_url.rstrip("/") + EDIT_ENDPOINT
    with open(file_path, "rb") as f:
        resp = httpx.post(
            url,
            headers={"api-key": settings.unsiloed_api_key},
            data={"edit_request": json.dumps({"items": items}), "upload_to_storage": "true"},
            files={"file": (file_path.split("/")[-1], f, "application/pdf")},
            timeout=180.0,
        )
    resp.raise_for_status()
    return resp.json()


def download_pdf(pdf_url: str, dest_path) -> bool:
    try:
        r = httpx.get(pdf_url, timeout=120.0, follow_redirects=True)
        r.raise_for_status()
        dest_path.write_bytes(r.content)
        return True
    except Exception:
        logger.exception("failed to download edited pdf")
        return False


# ---------- impact analysis ----------

def _overlaps(a: list[float], b: list[float], tol: float = 6.0) -> bool:
    """True if two [x0,y0,x1,y1] boxes are roughly the same region."""
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def _normalized_dims(db: Session, document_id: int, page_no: int) -> tuple[float, float] | None:
    """Unsiloed's reported page space for this page, learned from any citation on it
    (Unsiloed normalizes letter->A4, so this differs from native PDF points)."""
    c = db.scalar(
        select(EntityCitation).where(
            EntityCitation.document_id == document_id, EntityCitation.page_no == page_no
        )
    )
    if c and c.bbox.get("page_width"):
        return float(c.bbox["page_width"]), float(c.bbox["page_height"])
    return None


def find_impact(db: Session, project, match_value: str, field_name: str | None = None) -> list[dict]:
    """Find every literal occurrence of `match_value` across all documents via
    full-text search (this is "replace this value everywhere"). Each occurrence
    carries an `edit_bbox` in the editor's coordinate space, and is annotated
    with the extracted field it corresponds to (if any) for display.
    """
    docs = db.scalars(select(Document).where(Document.project_id == project.id)).all()
    out = []
    for doc in docs:
        try:
            pdf = fitz.open(doc.file_path)
        except Exception:
            continue
        occs = []
        for i, page in enumerate(pdf):
            page_no = i + 1
            rects = page.search_for(match_value)
            if not rects:
                continue
            ndims = _normalized_dims(db, doc.id, page_no)
            sx = (ndims[0] / page.rect.width) if ndims else 1.0
            sy = (ndims[1] / page.rect.height) if ndims else 1.0
            # citations on this page, to label each match with its field
            cites = list(db.scalars(
                select(EntityCitation).where(
                    EntityCitation.document_id == doc.id, EntityCitation.page_no == page_no
                )
            ))
            for r in rects:
                corners = [r.x0 * sx, r.y0 * sy, r.x1 * sx, r.y1 * sy]
                label = "text"
                for c in cites:
                    if _overlaps(c.bbox.get("bbox", [0, 0, 0, 0]), corners):
                        label = c.field_name
                        break
                occs.append({
                    "field_name": label, "page_no": page_no, "snippet": match_value,
                    "edit_bbox": {"left": round(corners[0], 2), "top": round(corners[1], 2),
                                  "width": round(corners[2] - corners[0], 2),
                                  "height": round(corners[3] - corners[1], 2)},
                })
        pdf.close()
        if occs:
            out.append({"document_id": doc.id, "document_title": doc.title, "occurrences": occs})
    return out


def apply_edit(db: Session, project, match_value: str, replacement_text: str,
               field_name: str | None = None) -> dict:
    """Apply the replacement across every affected document via the Edit API."""
    impact = find_impact(db, project, match_value, field_name)
    results = []
    for doc_impact in impact:
        doc = db.get(Document, doc_impact["document_id"])
        items = [
            {"type": "text", "page_number": occ["page_no"],
             "bbox": occ["edit_bbox"], "replacement_text": replacement_text}
            for occ in doc_impact["occurrences"]
        ]
        edit = DocumentEdit(
            project_id=project.id, document_id=doc.id, field_name=field_name,
            old_value=match_value, new_value=replacement_text, items=items, status="pending",
        )
        db.add(edit)
        db.flush()
        try:
            resp = submit_edit(doc.file_path, items)
            edit.pdf_url = resp.get("pdf_url")
            edit.new_job_id = resp.get("new_job_id")
            edit.original_size = resp.get("original_size")
            edit.edited_size = resp.get("edited_size")
            edit.items_processed = resp.get("items_processed")
            edit.status = "succeeded" if resp.get("success") else "failed"
            if edit.pdf_url:
                dest = EDITED_DIR / f"edit_{edit.id}_{doc.id}.pdf"
                if download_pdf(edit.pdf_url, dest):
                    edit.edited_file_path = str(dest)
        except Exception as e:
            logger.exception("edit failed for doc %s", doc.id)
            edit.status = "failed"
            edit.new_value = f"{replacement_text}"
            results.append({"document_id": doc.id, "status": "failed", "error": str(e)[:200]})
            db.commit()
            continue
        results.append({
            "document_id": doc.id, "document_title": doc.title, "status": edit.status,
            "items_processed": edit.items_processed, "edit_id": edit.id,
            "pdf_url": edit.pdf_url,
        })
        db.commit()
        time.sleep(0.5)
    return {"edits": results, "documents_affected": len(impact)}
