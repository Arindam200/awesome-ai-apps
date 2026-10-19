"""Create a synthetic sample PDF with text, tables, and a diagram."""

import logging
from pathlib import Path
import pymupdf

logger = logging.getLogger(__name__)


def generate_sample_pdf(output_path: str = "sample_document.pdf") -> str:
    """Generate a sample 3-page PDF with text, a table, and a vector diagram."""
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

    # Page 2: System Architecture Diagram (drawn vector shapes)
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text(
        (50, 70),
        "System Architecture & Flow Diagram",
        fontsize=16,
        color=(0.1, 0.1, 0.3),
    )
    p2.draw_rect(pymupdf.Rect(50, 100, 200, 160), color=(0.4, 0.2, 0.8), fill=(0.95, 0.93, 1.0))
    p2.insert_text((70, 135), "1. PDF Ingestion\n(PyMuPDF / Pixmaps)", fontsize=10)

    p2.draw_line(pymupdf.Point(200, 130), pymupdf.Point(260, 130), color=(0.4, 0.2, 0.8), width=2)

    p2.draw_rect(pymupdf.Rect(260, 100, 410, 160), color=(0.4, 0.2, 0.8), fill=(0.95, 0.93, 1.0))
    p2.insert_text((275, 135), "2. Dual Pipeline\n(Text + Vision LLM)", fontsize=10)

    p2.draw_line(pymupdf.Point(410, 130), pymupdf.Point(470, 130), color=(0.4, 0.2, 0.8), width=2)

    p2.draw_rect(pymupdf.Rect(470, 100, 560, 160), color=(0.4, 0.2, 0.8), fill=(0.95, 0.93, 1.0))
    p2.insert_text((485, 135), "3. FAISS Store\n(Dense Index)", fontsize=10)

    p2.insert_text(
        (50, 200),
        "Diagram Notes:\n"
        "The architecture consists of three sequential pipeline stages connected via high-throughput\n"
        "message channels. Ingestion passes rendered page images to the vision model and raw UTF-8\n"
        "to the sentence chunker before unifying in the FAISS vector index.",
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
        "- Multimodal PDF RAG improves accuracy by +37.4% over text-only baselines on documents\n"
        "  containing diagrams, charts, and dense numerical tables.",
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
    out = generate_sample_pdf("rag_apps/image_aware_pdf_rag/sample_data/sample_document.pdf")
    logger.info("Generated sample PDF at: %s", out)
