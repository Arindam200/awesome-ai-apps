
from io import BytesIO

import pymupdf  # PyMuPDF
from PIL import Image, ImageDraw

from ingestion import PDFIngestionError, ingest_pdf


def make_text_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Selectable text: Hello PDF")
    data = doc.tobytes()
    doc.close()
    return data


def make_scanned_pdf() -> bytes:
    # Create a page image containing visible text, not PDF text.
    image = Image.new("RGB", (600, 800), "white")
    draw = ImageDraw.Draw(image)
    draw.text((50, 80), "Scanned document content", fill="black")

    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG")

    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    page.insert_image(page.rect, stream=image_buffer.getvalue())

    data = doc.tobytes()
    doc.close()
    return data


def test_selectable_text_pdf():
    results = ingest_pdf(make_text_pdf())

    assert len(results) == 1
    page = results[0]

    assert page.page_number == 1
    assert "Selectable text: Hello PDF" in page.text
    assert page.image_png.startswith(b"\x89PNG\r\n\x1a\n")
    assert page.status == "text_extracted"
    assert page.needs_ocr is False


def test_bytes_like_pdf_inputs_are_accepted():
    pdf_bytes = make_text_pdf()

    for input_bytes in (bytearray(pdf_bytes), memoryview(pdf_bytes)):
        results = ingest_pdf(input_bytes)

        assert len(results) == 1
        assert "Selectable text: Hello PDF" in results[0].text


def test_scanned_pdf_is_not_silently_accepted():
    results = ingest_pdf(make_scanned_pdf())

    assert len(results) == 1
    page = results[0]

    assert page.page_number == 1
    assert page.text == ""
    assert page.image_png.startswith(b"\x89PNG\r\n\x1a\n")
    assert page.status == "image_only_needs_ocr"
    assert page.needs_ocr is True


def test_page_numbers_are_one_based():
    doc = pymupdf.open()

    for number in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {number + 1}")

    pdf_bytes = doc.tobytes()
    doc.close()

    results = ingest_pdf(pdf_bytes)

    assert [page.page_number for page in results] == [1, 2, 3]


def test_invalid_pdf_is_rejected():
    try:
        ingest_pdf(b"not a PDF")
    except PDFIngestionError:
        pass
    else:
        raise AssertionError("Expected PDFIngestionError")


def test_empty_input_is_rejected():
    try:
        ingest_pdf(b"")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_unsupported_input_type_is_rejected():
    try:
        ingest_pdf("not PDF bytes")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_inline_raster_image_detected():
    """Verify pages with inline raster images (BI...ID...EI) are flagged with has_visuals=True."""
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length 72 >>\nstream\n"
        b"q 50 0 0 50 20 20 cm\n"
        b"BI\n/W 2\n/H 2\n/CS /DeviceRGB\n/BPC 8\nID\n"
        b"\xff\x00\x00\x00\xff\x00\x00\x00\xff\xff\xff\xff\nEI\nQ\n"
        b"endstream\nendobj\n"
        b"xref\n0 5\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000202 00000 n \n"
        b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n326\n%%EOF\n"
    )

    results = ingest_pdf(pdf_content)
    assert len(results) == 1
    page = results[0]
    assert page.has_visuals is True
