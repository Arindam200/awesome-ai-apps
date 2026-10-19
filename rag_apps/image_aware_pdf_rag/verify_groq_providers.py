
"""Manual verification script: PDF -> ingestion -> Groq vision & chat."""

import logging
from pathlib import Path

from dotenv import load_dotenv

from ingestion import ingest_pdf
from providers.groq_chat import GroqChatModel
from providers.groq_vision import GroqVisionModel
from vision import describe_pdf_pages

load_dotenv()
logger = logging.getLogger(__name__)


def main() -> None:
    """Run manual verification interactively with a chosen PDF and Groq models."""
    pdf_path = Path(
        input("Enter the path to your PDF: ").strip().strip('"')
    )

    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Please select a PDF file.")

    # 1. Read the PDF.
    pdf_bytes = pdf_path.read_bytes()
    logger.info("Loaded PDF: %s", pdf_path.name)

    # 2. Extract text and render pages using your existing ingestion module.
    pages = ingest_pdf(pdf_bytes)
    logger.info("Pages ingested: %d", len(pages))

    # 3. Describe the rendered page images using Groq vision.
    vision_model = GroqVisionModel()
    descriptions = describe_pdf_pages(pages[:1], vision_model)

    for item in descriptions:
        logger.info("--- Page %s ---", item.page_number)
        logger.info("%s", item.description)

    # 4. Test Groq chat separately.
    chat_model = GroqChatModel()
    answer = chat_model.generate([
        {
            "role": "user",
            "content": (
                "Explain briefly why a PDF RAG system should preserve "
                "page numbers when indexing extracted text and visual "
                "descriptions."
            ),
        }
    ])

    logger.info("--- Groq chat test ---")
    logger.info("%s", answer)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
