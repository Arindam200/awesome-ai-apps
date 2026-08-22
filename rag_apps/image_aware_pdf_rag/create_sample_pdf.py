from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

SAMPLE_VISUAL_DESCRIPTIONS = {
    1: (
        "Executive summary callout: annual recurring revenue reached $12.4 million, "
        "up 18 percent year over year."
    ),
    2: (
        "Bar chart titled Quarterly activation rate. Q1 is 42 percent, Q2 is 55 "
        "percent, Q3 is 71 percent, and Q4 is 88 percent. Q4 is the highest bar."
    ),
    3: (
        "Regional retention table. North is 94 percent, South is 89 percent, and "
        "West is 92 percent. North has the highest retention."
    ),
}


def build_sample_pdf() -> bytes:
    """Create a small, license-compatible report for offline testing."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    _draw_header(pdf, "Acme Cloud 2026 Business Review", 1)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(72, height - 150, "Executive summary")
    pdf.setFont("Helvetica", 13)
    pdf.drawString(72, height - 195, "Annual recurring revenue reached $12.4 million.")
    pdf.drawString(72, height - 220, "Revenue grew 18 percent year over year.")
    pdf.setFillColor(colors.HexColor("#E8F1EE"))
    pdf.roundRect(72, height - 350, width - 144, 80, 6, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#173A34"))
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawString(96, height - 315, "+18% ARR growth")
    pdf.showPage()

    _draw_header(pdf, "Customer activation", 2)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(72, height - 130, "Quarterly activation rate")
    values = [("Q1", 42), ("Q2", 55), ("Q3", 71), ("Q4", 88)]
    bar_width = 72
    baseline = 210
    for index, (label, value) in enumerate(values):
        x = 92 + index * 110
        bar_height = value * 3.5
        color = "#72A699" if label != "Q4" else "#D94F4F"
        pdf.setFillColor(colors.HexColor(color))
        pdf.rect(x, baseline, bar_width, bar_height, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#202729"))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawCentredString(x + bar_width / 2, baseline - 24, label)
        pdf.drawCentredString(x + bar_width / 2, baseline + bar_height + 10, f"{value}%")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(72, 120, "Activation = accounts completing setup within seven days.")
    pdf.showPage()

    _draw_header(pdf, "Regional retention", 3)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(72, height - 130, "Twelve-month customer retention")
    table_x = 90
    table_y = height - 230
    row_height = 42
    rows = [("Region", "Retention"), ("North", "94%"), ("South", "89%"), ("West", "92%")]
    for row_index, (region, retention) in enumerate(rows):
        y = table_y - row_index * row_height
        pdf.setFillColor(colors.HexColor("#173A34") if row_index == 0 else colors.white)
        pdf.rect(table_x, y, 360, row_height, fill=1, stroke=1)
        pdf.setFillColor(colors.white if row_index == 0 else colors.HexColor("#202729"))
        pdf.setFont("Helvetica-Bold" if row_index == 0 else "Helvetica", 12)
        pdf.drawString(table_x + 18, y + 14, region)
        pdf.drawRightString(table_x + 340, y + 14, retention)
    pdf.showPage()

    pdf.save()
    return buffer.getvalue()


def _draw_header(pdf: canvas.Canvas, title: str, page_number: int) -> None:
    width, height = letter
    pdf.setFillColor(colors.HexColor("#173A34"))
    pdf.rect(0, height - 72, width, 72, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(48, height - 44, title)
    pdf.drawRightString(width - 48, height - 44, f"Page {page_number}")
    pdf.setFillColor(colors.HexColor("#202729"))


def write_sample_files(output_dir: Path) -> tuple[Path, Path]:
    """Write the sample PDF and its optional visual-description sidecar."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "sample_report.pdf"
    descriptions_path = output_dir / "sample_report.visual.json"
    pdf_path.write_bytes(build_sample_pdf())
    descriptions_path.write_text(json.dumps(SAMPLE_VISUAL_DESCRIPTIONS, indent=2), encoding="utf-8")
    return pdf_path, descriptions_path


def load_visual_descriptions(path: Path) -> dict[int, str]:
    """Load a sidecar and restore integer page keys lost by JSON encoding."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read visual-description sidecar: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Visual-description sidecar must contain a JSON object.")
    descriptions: dict[int, str] = {}
    for raw_page_number, description in payload.items():
        try:
            page_number = int(raw_page_number)
        except (TypeError, ValueError) as exc:
            raise ValueError("Visual-description sidecar page keys must be integers.") from exc
        if page_number < 1 or not isinstance(description, str):
            raise ValueError("Visual-description sidecar contains an invalid entry.")
        descriptions[page_number] = description
    return descriptions


if __name__ == "__main__":
    pdf_file, descriptions_file = write_sample_files(Path.cwd())
    print(f"Created {pdf_file}")
    print(f"Created {descriptions_file}")
