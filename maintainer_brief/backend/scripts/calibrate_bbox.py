"""Bbox calibration: verify which coordinate space Unsiloed bboxes use.

Generates a one-page PDF with a fake feature request placed at KNOWN
coordinates, runs it through /v2/extract with citations enabled, then draws
the returned bboxes onto the rendered page under both scaling hypotheses
(PDF points vs rendered pixels) and reports which one lands on the text.

Usage:
    cd backend && .venv/bin/python scripts/calibrate_bbox.py

Requires UNSILOED_API_KEY in ../.env or the environment.
Output: backend/data/calibration/{calibration.pdf, overlay_pt.png, overlay_px.png}
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # noqa: E402

from app.config import DATA_DIR, settings  # noqa: E402
from app.unsiloed.client import UnsiloedClient  # noqa: E402
from app.unsiloed.registry import get_schema  # noqa: E402

OUT_DIR = DATA_DIR / "calibration"
RENDER_SCALE = 2.0

# Known placement (PDF points, origin top-left in pymupdf)
TEXT_X, TEXT_Y = 72, 200
KNOWN_TEXT = "Feature request: add MCP server support to the gateway, urgency high."


def make_pdf() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "calibration.pdf"
    doc = fitz.open()
    page = doc.new_page()  # 612x792 pt letter
    page.insert_text((TEXT_X, 100), "Calibration Document", fontsize=20)
    page.insert_text((TEXT_X, TEXT_Y), KNOWN_TEXT, fontsize=12)
    page.insert_text(
        (TEXT_X, 400),
        "Unrelated filler text that should not be cited.",
        fontsize=12,
    )
    doc.save(path)
    doc.close()
    print(f"wrote {path} (page is 612x792 pt; target text at y={TEXT_Y}pt)")
    return path


def draw_overlay(pdf_path: Path, bboxes: list, space: str) -> Path:
    doc = fitz.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE))
    img_path = OUT_DIR / f"overlay_{space}.png"
    pix.save(img_path)

    import struct  # draw with pymupdf instead of pillow: re-open as new doc
    _ = struct  # (no pillow dependency; draw rects on the pdf and re-render)

    page_w_pt, page_h_pt = page.rect.width, page.rect.height
    for bbox in bboxes:
        if isinstance(bbox, dict):
            x, y, w, h = bbox["left"], bbox["top"], bbox["width"], bbox["height"]
        else:
            x, y, w, h = bbox[:4]
        if space == "pt":
            rect = fitz.Rect(x, y, x + w, y + h)
        else:  # px hypothesis: scale from rendered px back to pt
            sx, sy = page_w_pt / pix.width, page_h_pt / pix.height
            rect = fitz.Rect(x * sx, y * sy, (x + w) * sx, (y + h) * sy)
        page.draw_rect(rect, color=(0.7, 0.31, 0.18), width=2)

    pix2 = page.get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE))
    pix2.save(img_path)
    doc.close()
    return img_path


def main():
    if not settings.unsiloed_api_key:
        sys.exit("UNSILOED_API_KEY is not set — add it to .env first.")

    pdf_path = make_pdf()
    client = UnsiloedClient()
    print("submitting to /v2/extract (feature_request schema, citations on)...")
    job_id = client.submit_extract(pdf_path, get_schema("feature_request"))
    print(f"job {job_id}, polling...")
    result = client.wait("extract", job_id, deadline_s=300)

    raw_path = OUT_DIR / "raw_response.json"
    raw_path.write_text(json.dumps(result, indent=2, default=str))
    print(f"full response saved to {raw_path}")

    if result.get("status") != "Succeeded":
        sys.exit(f"extraction failed: {result}")

    # Collect every bbox in the response
    bboxes = []

    def walk(node):
        if isinstance(node, dict):
            if "bboxes" in node and node.get("bboxes"):
                for b in node["bboxes"]:
                    bboxes.append(b)
                print(
                    f"  field value={str(node.get('value'))[:60]!r} "
                    f"page={node.get('page_no')} bboxes={node['bboxes']}"
                )
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(result)
    if not bboxes:
        sys.exit("no bboxes in response — check enable_citations / response shape above")

    for space in ("pt", "px"):
        path = draw_overlay(pdf_path, bboxes, space)
        print(f"overlay ({space} hypothesis): {path}")

    print(
        f"\nThe target text sits at y≈{TEXT_Y}pt of 792pt (about 25% down the page)."
        "\nOpen both overlays — the hypothesis whose rectangles sit ON the feature-"
        "\nrequest line is the correct bbox space. Set it as the default in"
        "\nfrontend/src/components/CitationViewer.tsx (bboxSpace useState)."
    )


if __name__ == "__main__":
    main()
