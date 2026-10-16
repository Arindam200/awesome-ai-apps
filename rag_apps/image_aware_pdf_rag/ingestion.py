"""PDF ingestion: page-level text extraction and PNG rendering.

Page fields:
    page_number: one-based page number (1, 2, 3, …).
    text: extracted selectable text.
    image_png: rendered page image as PNG bytes.
    status: whether text was extracted, the page is image-only, or extraction failed.
    error: details when processing fails.

Use PyMuPDF (fitz) to extract text and render pages. It handles both operations
without requiring a separate PDF renderer.
"""

from dataclasses import dataclass

import pymupdf  # PyMuPDF   


class PDFIngestionError(ValueError):
    """Raised when a PDF cannot be opened or has no readable pages."""


@dataclass
class PageResult:
    page_number: int  # Always one-based
    text: str
    image_png: bytes | None
    status: str
    needs_ocr: bool
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "page_number": self.page_number,
            "text": self.text,
            "image_png": self.image_png,
            "status": self.status,
            "needs_ocr": self.needs_ocr,
            "error": self.error,
        }


def ingest_pdf(
    pdf_bytes: bytes | bytearray | memoryview, dpi: int = 150
) -> list[PageResult]:
    """Extract selectable text and render every PDF page to PNG bytes.

    Pages without selectable text are explicitly flagged for OCR.
    A PDF opening successfully does not imply that its text was extracted.

    Args:
        pdf_bytes: Raw PDF file bytes or another bytes-like object.
        dpi: Rendering resolution. Defaults to 150.

    Returns:
        One PageResult per PDF page, with one-based page numbers.

    Raises:
        PDFIngestionError: If the PDF is invalid, encrypted, empty,
            or cannot be opened.
        ValueError: If the input or DPI is invalid.
    """
    if not isinstance(pdf_bytes, (bytes, bytearray, memoryview)):
        raise ValueError("pdf_bytes must be a non-empty bytes-like object")
    pdf_bytes = bytes(pdf_bytes)
    if not pdf_bytes:
        raise ValueError("pdf_bytes must be a non-empty bytes-like object")

    if dpi <= 0:
        raise ValueError("dpi must be greater than zero")

    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise PDFIngestionError(f"Unable to open PDF: {exc}") from exc

    results: list[PageResult] = []

    try:
        if document.needs_pass:
            raise PDFIngestionError("PDF is password-protected")

        if document.page_count == 0:
            raise PDFIngestionError("PDF contains no pages")

        zoom = dpi / 72
        matrix = pymupdf.Matrix(zoom, zoom)

        for index in range(document.page_count):
            page_number = index + 1
            text = ""
            image_png = None
            error = None
            needs_ocr = False

            try:
                page = document.load_page(index)
                text = page.get_text("text").strip()

                # Render the page even when no text can be extracted.
                pixmap = page.get_pixmap(
                    matrix=matrix,
                    colorspace=pymupdf.csRGB,
                    alpha=False,
                )
                image_png = pixmap.tobytes("png")

                if text:
                    status = "text_extracted"
                else:
                    needs_ocr = True
                    if page.get_images(full=True):
                        status = "image_only_needs_ocr"
                    else:
                        status = "no_selectable_text_needs_review"

            except Exception as exc:
                # Keep the page number and make failures explicit.
                status = "processing_error"
                needs_ocr = not text
                error = f"{type(exc).__name__}: {exc}"

            results.append(
                PageResult(
                    page_number=page_number,
                    text=text,
                    image_png=image_png,
                    status=status,
                    needs_ocr=needs_ocr,
                    error=error,
                )
            )
    finally:
        document.close()

    return results
