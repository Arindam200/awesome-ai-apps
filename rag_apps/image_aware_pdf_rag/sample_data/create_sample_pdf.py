"""Create a synthetic sample PDF with text, a raster bar chart, and a table."""

import io
import logging
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)


def _make_bar_chart_png(width: int = 400, height: int = 260) -> bytes:
    """Draw a simple bar chart using only the standard library and return PNG bytes.

    Uses PyMuPDF's in-memory document trick so we keep the dependency list short
    (no matplotlib or Pillow needed beyond what's already installed).
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return b""

    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Chart data: quarterly revenue
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    values = [18, 22, 15, 27]  # $ millions
    bar_color = (79, 70, 229)  # indigo
    max_val = 30

    margin_left, margin_bottom = 50, 40
    chart_w = width - margin_left - 20
    chart_h = height - margin_bottom - 30

    # Axes
    draw.line(
        [(margin_left, 20), (margin_left, height - margin_bottom)],
        fill=(30, 30, 30),
        width=2,
    )
    draw.line(
        [(margin_left, height - margin_bottom), (width - 10, height - margin_bottom)],
        fill=(30, 30, 30),
        width=2,
    )

    bar_w = chart_w // (len(values) * 2)
    for i, (q, v) in enumerate(zip(quarters, values)):
        bar_h = int((v / max_val) * chart_h)
        x0 = margin_left + i * (bar_w * 2) + bar_w // 2
        y0 = height - margin_bottom - bar_h
        x1 = x0 + bar_w
        y1 = height - margin_bottom
        draw.rectangle([x0, y0, x1, y1], fill=bar_color)
        # Value label above bar
        draw.text((x0 + 2, y0 - 14), f"${v}M", fill=(30, 30, 30))
        # Quarter label below axis
        draw.text((x0 + 2, height - margin_bottom + 4), q, fill=(30, 30, 30))

    # Y-axis labels
    for tick in [0, 10, 20, 30]:
        y = height - margin_bottom - int((tick / max_val) * chart_h)
        draw.line([(margin_left - 4, y), (margin_left, y)], fill=(30, 30, 30), width=1)
        draw.text((2, y - 7), f"{tick}", fill=(80, 80, 80))

    # Title
    draw.text((margin_left, 4), "Quarterly Revenue ($ millions)", fill=(30, 30, 30))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_sample_pdf(output_path: str = "sample_document.pdf") -> str:
    """Generate a sample 3-page PDF with text, a raster bar chart, and a table."""
    doc = pymupdf.open()

    # Page 1: Paper Overview & Contributions
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text(
        (50, 70),
        "Multimodal Architecture & Distributed Intelligence",
        fontsize=18,
        color=(0.1, 0.1, 0.3),
    )
    p1.insert_text(
        (50, 110),
        "Abstract and Key Contributions:\n"
        "1. Unified embedding representation across unstructured prose, tabular data, and visual regions.\n"
        "2. Zero-shot visual question answering pipeline with grounded page-level source attribution.\n"
        "3. Real-time document routing architecture with sub-second retrieval latency.\n\n"
        "The primary contribution of this paper is demonstrating that page-level vision descriptions\n"
        "indexed alongside dense text chunks prevent retrieval drift on document charts.",
        fontsize=11,
    )

    # Page 2: Raster Bar Chart (embedded PNG)
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text(
        (50, 50),
        "Figure 1 — Quarterly Revenue ($ millions)",
        fontsize=14,
        color=(0.1, 0.1, 0.3),
    )

    chart_png = _make_bar_chart_png()
    if chart_png:
        rect = pymupdf.Rect(80, 80, 480, 340)
        p2.insert_image(rect, stream=chart_png)

    p2.insert_text(
        (50, 360),
        "Chart Notes:\n"
        "Q4 posted the highest quarterly revenue at $27M, driven by enterprise contract renewals.\n"
        "Q3 was the weakest quarter at $15M due to summer seasonality. Q1 and Q2 show steady\n"
        "growth from $18M to $22M as the product reached general availability.",
        fontsize=11,
    )

    # Page 3: Benchmark Results Table
    p3 = doc.new_page(width=595, height=842)
    p3.insert_text(
        (50, 70),
        "Empirical Evaluation & Performance Results",
        fontsize=16,
        color=(0.1, 0.1, 0.3),
    )
    p3.insert_text(
        (50, 110),
        "Table 1: Benchmark Accuracy on Complex Visual QA Documents\n"
        "----------------------------------------------------------------------\n"
        "Pipeline Mode              Retrieval MRR@5    VQA Accuracy (%)   Latency\n"
        "----------------------------------------------------------------------\n"
        "Text-Only Baseline             0.612               54.2%          120ms\n"
        "Vision-Only Baseline           0.584               63.8%          850ms\n"
        "Multimodal PDF RAG (Ours)      0.894               91.6%          340ms\n"
        "----------------------------------------------------------------------\n\n"
        "Key Findings:\n"
        "- Multimodal PDF RAG improves accuracy by 37.4 percentage points over\n"
        "  text-only baselines on documents containing diagrams, charts, and dense\n"
        "  numerical tables.",
        fontsize=10,
        fontname="Courier",
    )

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(target))
    doc.close()
    return str(target)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    output_path = Path(__file__).resolve().parent / "sample_document.pdf"
    out = generate_sample_pdf(str(output_path))
    logger.info("Generated sample PDF at: %s", out)
