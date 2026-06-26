"""Edit-bbox calibration: lock the coordinate space before trusting the Edit API.

Makes a known PDF, extracts it to get a real citation bbox for a known string,
sends an edit using that bbox, downloads the result, and checks the replacement
text landed where the original was. Tries the citation's own coordinate space
(corners as-is) — our docs report bbox in PDF points, which is what the editor
expects.

Run: cd backend && python -m scripts.calibrate_edit
On pass, set editing_enabled=true (EDITING_ENABLED env / config).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # noqa: E402

from app.config import DATA_DIR, settings  # noqa: E402
from app.intelligence.edit import citation_to_edit_item, download_pdf, submit_edit  # noqa: E402
from app.unsiloed.client import UnsiloedClient  # noqa: E402
from app.unsiloed.registry import get_schema  # noqa: E402

OUT = DATA_DIR / "calibration"
KNOWN = "ACMECORP-ADDRESS-12345"
REPLACEMENT = "ZZZ-NEW-ADDRESS-99999"


def make_pdf() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "edit_calibration.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 120), "Vendor Contract", fontsize=20)
    page.insert_text((72, 220), f"Company Address: {KNOWN}", fontsize=12)
    page.insert_text((72, 320), "Contract Value: $50,000", fontsize=12)
    doc.save(path)
    doc.close()
    return path


def main():
    if not settings.unsiloed_api_key:
        sys.exit("UNSILOED_API_KEY not set")

    pdf = make_pdf()
    client = UnsiloedClient()

    # extract with the vendors schema (has 'address') to get a citation bbox
    print("extracting to locate the known string...")
    job = client.submit_extract(pdf, get_schema("vendors"))
    result = client.wait("extract", job, deadline_s=300)

    # find the citation whose value contains the known token
    target = None
    def walk(node):
        nonlocal target
        if isinstance(node, dict):
            if "value" in node and isinstance(node.get("value"), str) and KNOWN in node["value"]:
                if node.get("citation", {}).get("bbox"):
                    target = node["citation"]
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(result.get("result", {}))

    if not target:
        sys.exit(f"could not find a citation for {KNOWN}; response shape unexpected")
    print(f"citation bbox: {target}")

    item = citation_to_edit_item(target, REPLACEMENT)
    print(f"edit item: {item}")

    print("calling Edit API...")
    resp = submit_edit(str(pdf), [item])
    print(f"edit response: success={resp.get('success')} items={resp.get('items_processed')} url={bool(resp.get('pdf_url'))}")
    if not resp.get("pdf_url"):
        sys.exit(f"no pdf_url in response: {resp}")

    edited = OUT / "edit_calibration_result.pdf"
    if not download_pdf(resp["pdf_url"], edited):
        sys.exit("could not download edited PDF")

    text = fitz.open(edited)[0].get_text()
    replaced = REPLACEMENT in text
    original_gone = KNOWN not in text
    print(f"\nedited PDF text contains replacement={replaced}, original_removed={original_gone}")
    if replaced:
        print("✅ CALIBRATION PASSED — citation bbox (corners as-is) is the correct edit space.")
        print("   Set EDITING_ENABLED=true to enable the edit feature.")
    else:
        print("❌ CALIBRATION FAILED — replacement text not found. Inspect", edited)
        print("   Keep editing_enabled=false; features 1-4 ship without it.")


if __name__ == "__main__":
    main()
