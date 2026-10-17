
"""Integration test: PDF -> ingestion -> Groq vision."""

from pathlib import Path

from dotenv import load_dotenv

from ingestion import ingest_pdf
from providers.groq_chat import GroqChatModel
from providers.groq_vision import GroqVisionModel
from vision import describe_pdf_pages

load_dotenv()


def main():
    pdf_path = Path(
        input("Enter the path to your PDF: ").strip().strip('"')
    )

    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Please select a PDF file.")

    # 1. Read the PDF.
    pdf_bytes = pdf_path.read_bytes()
    print(f"\nLoaded PDF: {pdf_path.name}")

    # 2. Extract text and render pages using your existing ingestion module.
    pages = ingest_pdf(pdf_bytes)
    print(f"Pages ingested: {len(pages)}")

    # 3. Describe the rendered page images using Groq vision.
    vision_model = GroqVisionModel()
    descriptions = describe_pdf_pages(pages[:1], vision_model)

    for item in descriptions:
        print(f"\n--- Page {item.page_number} ---")
        print(item.description)

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

    print("\n--- Groq chat test ---")
    print(answer)


if __name__ == "__main__":
    main()
