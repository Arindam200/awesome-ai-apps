"""AI Invoice & Receipt Auditor.

Scanned invoices and receipts are OCR'd 100% locally with LiteParse (no cloud,
no API key, bounding boxes included). A Nebius Token Factory LLM then extracts
structured data and audits each document — math errors, tax mismatches, missing
fields — and every finding is pinned to the exact spot on the scan. Duplicate
charges are detected across the whole batch, with a spending dashboard and CSV
export on top.
"""

import base64
import hashlib
import json
import os
import re
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

# Nebius inference is remote. Transformers may be present transitively for
# tokenization, but this app does not require a local PyTorch installation.
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from liteparse import LiteParse
from llama_index.core.llms import ChatMessage, LLM
from llama_index.llms.nebius import NebiusLLM
from PIL import Image, ImageDraw

load_dotenv()

APP_DIR = Path(__file__).resolve().parent
LLAMAINDEX_LOGO = APP_DIR / "assets" / "llamaindex-color.png"
NEBIUS_LOGO = APP_DIR / "assets" / "nebius.png"
NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
MODELS = [
    "Qwen/Qwen3-235B-A22B-Instruct-2507",
    "meta-llama/Llama-3.3-70B-Instruct",
    "deepseek-ai/DeepSeek-V3-0324",
]

SEVERITY_COLORS = {
    "high": ((239, 68, 68, 80), (220, 38, 38, 255)),
    "medium": ((249, 115, 22, 80), (234, 88, 12, 255)),
    "low": ((250, 204, 21, 80), (202, 138, 4, 255)),
}
SEVERITY_LABELS = {"high": "High", "medium": "Medium", "low": "Low"}
SEVERITY_ORDER = ["low", "medium", "high"]

AUDIT_PROMPT = """\
You are a meticulous invoice and receipt auditor. Below is the OCR'd content of
one document, with each page delimited by [PAGE n] markers. OCR may introduce
small character errors — use judgement.

Extract the document's data and audit it. Respond with a single JSON object,
no markdown fences, in exactly this shape:
{{
  "doc_type": "invoice" | "receipt" | "other",
  "vendor": "<vendor/merchant name or null>",
  "date": "<document date as YYYY-MM-DD or null>",
  "invoice_number": "<invoice/receipt number or null>",
  "currency": "<3-letter code, e.g. USD>",
  "line_items": [
    {{"description": "<item>", "quantity": <number or null>, "unit_price": <number or null>, "amount": <number>}}
  ],
  "subtotal": <number or null>,
  "tax": <number or null>,
  "total": <number or null>,
  "findings": [
    {{
      "severity": "high" | "medium" | "low",
      "issue": "<one-sentence description of the problem>",
      "evidence_quote": "<short EXACT verbatim snippet from the document showing the problem>",
      "page": <page number>
    }}
  ]
}}

Audit checklist — report a finding for each problem you detect:
- Arithmetic: do the line items sum to the subtotal? Does subtotal + tax = total?
  Is quantity x unit_price = amount for each line? (high severity if wrong)
- Tax: is the tax amount implausible given the stated rate, or negative? (high)
- Missing essentials: no date, no vendor, no invoice number, no total. (medium)
- Suspicious patterns: duplicated line items within the document, conspicuously
  round totals on itemized invoices, dates in the future. (low or medium)

Rules:
- "evidence_quote" must be copied VERBATIM from the document text (max ~12 words)
  so it can be located on the scan. Do not paraphrase inside it.
- Numbers must be plain JSON numbers (no currency symbols or thousands separators).
- If the document is clean, return an empty findings list.

DOCUMENT ({filename}):
{document}
"""

SUMMARY_PROMPT = """\
You are an expense auditor writing a brief batch summary for a finance reviewer.
Given the audited invoices/receipts below, write a short summary in 3-5 bullet points:
- Total batch spend and top vendors
- How many documents are clean vs need review
- The most important findings (if any) and duplicates (if any)
- One clear recommended next step

Be concise, use plain markdown bullets, and mention amounts with currency.
Do not invent data not present in the JSON.

AUDITED BATCH:
{batch}
"""


# ---------------------------------------------------------------------------
# Parsing & OCR (fully local)
# ---------------------------------------------------------------------------

def stash_upload(name: str, data: bytes) -> str:
    """Persist an upload to a temp file; wrap images into a PDF so LiteParse
    can OCR them without an ImageMagick install."""
    suffix = Path(name).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg"}:
        img = Image.open(BytesIO(data)).convert("RGB")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        img.save(tmp, "PDF", resolution=150)
        tmp.close()
        return tmp.name
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(data)
    tmp.close()
    return tmp.name


@st.cache_resource(show_spinner=False)
def parse_document(file_hash: str, path: str) -> list[dict]:
    parser = LiteParse(output_format="markdown", ocr_enabled=True, quiet=True)
    result = parser.parse(path)
    return [
        {
            "page_num": p.page_num,
            "width": p.width,
            "height": p.height,
            "markdown": p.markdown,
            "items": [
                {"text": t.text, "x": t.x, "y": t.y, "w": t.width, "h": t.height}
                for t in p.text_items
            ],
        }
        for p in result.pages
    ]


@st.cache_data(show_spinner=False, max_entries=64)
def page_screenshot(file_hash: str, path: str, page_num: int) -> bytes:
    shots = LiteParse(quiet=True).screenshot(path, page_numbers=[page_num])
    return shots[0].image_bytes


# ---------------------------------------------------------------------------
# Evidence highlighting
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def find_evidence_boxes(page: dict, quote: str) -> list[dict]:
    nq = _norm(quote)
    if len(nq) < 3:
        return []
    boxes = []
    for item in page["items"]:
        ni = _norm(item["text"])
        if len(ni) >= 3 and (ni in nq or nq in ni):
            boxes.append(item)
    return boxes


def render_evidence(
    file_hash: str, path: str, pages: list[dict], findings: list[dict]
) -> list[tuple[int, Image.Image]]:
    """Render one image per page; pages with locatable evidence get color-coded
    highlight boxes, the rest render as plain scans."""
    per_page: dict[int, list[tuple[dict, str]]] = {}
    for f in findings:
        page = next((p for p in pages if p["page_num"] == f.get("page")), pages[0])
        severity = str(f.get("severity", "low")).lower()
        for box in find_evidence_boxes(page, str(f.get("evidence_quote", ""))):
            per_page.setdefault(page["page_num"], []).append((box, severity))

    rendered = []
    for page in pages:
        img = Image.open(BytesIO(page_screenshot(file_hash, path, page["page_num"]))).convert("RGBA")
        marks = per_page.get(page["page_num"], [])
        if marks:
            scale = img.width / page["width"]
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            pad = 2 * scale
            for box, severity in marks:
                fill, outline = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["low"])
                draw.rectangle(
                    (
                        box["x"] * scale - pad,
                        box["y"] * scale - pad,
                        (box["x"] + box["w"]) * scale + pad,
                        (box["y"] + box["h"]) * scale + pad,
                    ),
                    fill=fill,
                    outline=outline,
                    width=max(2, int(scale)),
                )
            img = Image.alpha_composite(img, overlay)
        rendered.append((page["page_num"], img))
    return rendered


# ---------------------------------------------------------------------------
# LLM audit
# ---------------------------------------------------------------------------

def extract_json(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def build_llm(api_key: str, model: str, temperature: float, max_tokens: int) -> LLM:
    """Build the native LlamaIndex integration for Nebius Token Factory."""
    return NebiusLLM(
        model=model,
        api_key=api_key,
        api_base=NEBIUS_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def audit_document(llm: LLM, filename: str, pages: list[dict]) -> dict:
    document = "\n\n".join(f"[PAGE {p['page_num']}]\n{p['markdown']}" for p in pages)[:60_000]
    response = llm.chat(
        [
            ChatMessage(role="system", content="You return only valid JSON."),
            ChatMessage(
                role="user",
                content=AUDIT_PROMPT.format(filename=filename, document=document),
            ),
        ],
    )
    return extract_json(response.message.content or "")


def batch_fingerprint(audits: dict[str, dict], model: str) -> str:
    payload = {name: audit["data"] for name, audit in sorted(audits.items())}
    raw = json.dumps(payload, sort_keys=True) + model
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def generate_batch_summary(llm: LLM, audits: dict[str, dict]) -> str:
    batch = json.dumps(
        {name: audit["data"] for name, audit in audits.items()},
        indent=1,
    )[:60_000]
    response = llm.chat(
        [
            ChatMessage(
                role="system",
                content="You write concise markdown summaries for finance reviewers.",
            ),
            ChatMessage(role="user", content=SUMMARY_PROMPT.format(batch=batch)),
        ],
    )
    return (response.message.content or "").strip()


def find_duplicates(audits: dict[str, dict]) -> list[dict]:
    """Deterministic cross-batch duplicate detection on (vendor, total, date)."""
    seen: dict[tuple, list[str]] = {}
    for name, audit in audits.items():
        data = audit["data"]
        if data.get("total") is None:
            continue
        try:
            total = round(float(data["total"]), 2)
        except (TypeError, ValueError):
            continue
        key = (_norm(str(data.get("vendor") or "")), total, data.get("date"))
        seen.setdefault(key, []).append(name)
    return [
        {"vendor": key[0] or "(unknown vendor)", "total": key[1], "date": key[2], "files": files}
        for key, files in seen.items()
        if len(files) > 1
    ]


def worst_severity(findings: list[dict]) -> str:
    severities = [
        str(f.get("severity", "low")).lower()
        for f in findings
        if str(f.get("severity", "low")).lower() in SEVERITY_ORDER
    ]
    return max(severities, key=SEVERITY_ORDER.index, default="low")


def money(value: Any, currency: str = "") -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.2f} {currency}".strip()
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def status_label(findings: list[dict]) -> str:
    if not findings:
        return "Clean"
    return f"Review · {SEVERITY_LABELS[worst_severity(findings)]}"


def render_welcome() -> None:
    st.markdown(
        """
        ### Audit invoices and receipts in one batch

        Upload scanned PDFs, photos, or DOCX files from the sidebar. LiteParse OCRs
        them locally on your machine, then Nebius extracts structured fields and flags
        math errors, missing data, and duplicate charges, with findings pinned on the scan.

        **What you get after running an audit**
        - A batch overview table with vendor, date, total, and review status
        - Per-document findings highlighted on the original scan
        - Duplicate charge detection across the whole upload
        - Spend breakdown by vendor and a CSV export
        - An LLM-generated batch summary with recommended next steps

        **Try the bundled samples** in `sample_invoices/`. They include a clean invoice,
        a resubmitted duplicate, an invoice with bad math, and a receipt missing a number.
        """
    )


st.set_page_config(
    page_title="Invoice Auditor",
    page_icon=str(LLAMAINDEX_LOGO),
    layout="wide",
)

st.session_state.setdefault("audits", {})
st.session_state.setdefault("batch_summary", "")
st.session_state.setdefault("summary_fingerprint", "")

# Header — same pattern as qwen3_rag
col1, col2 = st.columns([4, 1])
with col1:
    llama_base64 = base64.b64encode(LLAMAINDEX_LOGO.read_bytes()).decode()
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 10px;">
            <h1 style="margin: 0;">
                Invoice Auditor with LiteParse
                <img src="data:image/png;base64,{llama_base64}"
                     style="height: 40px; margin: 0; vertical-align: middle;">
                and Nebius
            </h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col2:
    if st.button("🗑️ Clear Audit"):
        st.session_state.clear()
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()

st.caption("Powered by Nebius AI · Local OCR via LiteParse")

# Sidebar — same pattern as qwen3_rag
with st.sidebar:
    st.image(str(NEBIUS_LOGO), width=150)

    api_key = st.text_input(
        "Nebius API Key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
        help="Create a key at tokenfactory.nebius.com",
    )

    model = st.selectbox("Generative Model", MODELS, index=0)

    st.divider()

    st.subheader("Upload invoices")
    uploads = st.file_uploader(
        "Choose PDF, JPG, PNG, or DOCX files",
        type=["pdf", "png", "jpg", "jpeg", "docx"],
        accept_multiple_files=True,
    )
    st.caption(
        "Upload invoices or receipts, then click **Run invoice audit** below "
        "to build your review workspace."
    )

    if uploads:
        preview_file = uploads[0]
        if len(uploads) > 1:
            st.caption(f"Previewing {preview_file.name} · {len(uploads)} files selected")
        suffix = Path(preview_file.name).suffix.lower()
        if suffix == ".pdf":
            st.subheader("PDF Preview")
            preview_pdf = base64.b64encode(preview_file.getvalue()).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{preview_pdf}" '
                'width="100%" height="500" type="application/pdf"></iframe>',
                unsafe_allow_html=True,
            )
        elif suffix in {".png", ".jpg", ".jpeg"}:
            st.subheader("Image Preview")
            st.image(preview_file, use_container_width=True)
        else:
            st.info("DOCX preview is unavailable. The file will still be audited.")

    run = st.button("🔍 Run invoice audit", use_container_width=True, disabled=not uploads)

if run and uploads:
    if not api_key:
        st.error("Please add your Nebius API key in the sidebar.")
        st.stop()
    audit_llm = build_llm(api_key, model, temperature=0.1, max_tokens=3000)
    progress = st.progress(0.0)
    for i, up in enumerate(uploads):
        data = up.getvalue()
        file_hash = hashlib.sha256(data).hexdigest()[:16]
        cached = st.session_state.audits.get(up.name)
        if cached and cached["hash"] == file_hash and cached["model"] == model:
            progress.progress((i + 1) / len(uploads), text=f"{up.name} — already audited")
            continue
        progress.progress(i / len(uploads), text=f"OCR-ing {up.name} locally...")
        try:
            path = stash_upload(up.name, data)
            pages = parse_document(file_hash, path)
        except Exception as exc:
            st.error(f"Failed to parse {up.name}: {exc}")
            continue
        if not pages or not any(p["items"] for p in pages):
            st.warning(f"No text found in {up.name} — skipping.")
            continue
        progress.progress(
            (i + 0.5) / len(uploads),
            text=f"Auditing {up.name} with {model.split('/')[-1]}...",
        )
        try:
            extracted = audit_document(audit_llm, up.name, pages)
        except Exception as exc:
            st.error(f"LLM audit failed for {up.name}: {exc}")
            continue
        if not extracted:
            st.error(f"Could not parse the model's response for {up.name}.")
            continue
        st.session_state.audits[up.name] = {
            "hash": file_hash,
            "model": model,
            "path": path,
            "pages": pages,
            "data": extracted,
        }
    progress.progress(1.0, text="Done")
    progress.empty()

audits: dict[str, dict] = st.session_state.audits

if not audits:
    render_welcome()
else:
    duplicates = find_duplicates(audits)
    all_findings = [
        {"file": name, **f}
        for name, audit in audits.items()
        for f in audit["data"].get("findings", [])
    ]
    totals = []
    for a in audits.values():
        try:
            totals.append(float(a["data"].get("total")))
        except (TypeError, ValueError):
            pass
    currencies = {a["data"].get("currency") or "USD" for a in audits.values()}
    currency_label = currencies.pop() if len(currencies) == 1 else ""
    n_high = sum(1 for f in all_findings if str(f.get("severity")).lower() == "high")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Documents audited", len(audits))
    c2.metric("Total spend", money(sum(totals), currency_label))
    c3.metric(
        "Findings",
        len(all_findings),
        delta=f"{n_high} high" if n_high else None,
        delta_color="inverse",
    )
    c4.metric("Duplicate charges", len(duplicates))

    for dup in duplicates:
        st.error(
            f"**Possible duplicate charge** — {dup['vendor'].title()} for "
            f"{money(dup['total'])} on {dup['date'] or 'unknown date'}: "
            + ", ".join(f"`{f}`" for f in dup["files"])
        )

    rows = []
    for name, audit in audits.items():
        d = audit["data"]
        findings = d.get("findings", [])
        rows.append(
            {
                "File": name,
                "Type": d.get("doc_type", "?"),
                "Vendor": d.get("vendor") or "—",
                "Date": d.get("date") or "—",
                "Invoice #": d.get("invoice_number") or "—",
                "Total": d.get("total"),
                "Currency": d.get("currency") or "—",
                "Findings": len(findings),
                "Status": status_label(findings),
            }
        )
    df = pd.DataFrame(rows)

    fingerprint = batch_fingerprint(audits, model)
    if fingerprint != st.session_state.summary_fingerprint:
        st.session_state.batch_summary = ""
        st.session_state.summary_fingerprint = fingerprint

    tab_overview, tab_docs = st.tabs(["Batch overview", "Document audits"])

    with tab_overview:
        if api_key:
            if not st.session_state.batch_summary:
                with st.spinner("Generating batch summary..."):
                    try:
                        summary_llm = build_llm(api_key, model, temperature=0.2, max_tokens=500)
                        st.session_state.batch_summary = generate_batch_summary(summary_llm, audits)
                    except Exception as exc:
                        st.warning(f"Could not generate summary: {exc}")
            if st.session_state.batch_summary:
                st.subheader("Batch summary")
                st.markdown(st.session_state.batch_summary)
        else:
            st.caption("Add your Nebius API key in the sidebar to generate a batch summary.")

        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "Download audit CSV",
            df.to_csv(index=False).encode(),
            "invoice_audit.csv",
            "text/csv",
        )
        spend = df.dropna(subset=["Total"]).groupby("Vendor")["Total"].sum()
        if len(spend) > 1:
            st.subheader("Spend by vendor")
            st.bar_chart(spend)

    with tab_docs:
        for name, audit in audits.items():
            d = audit["data"]
            findings = d.get("findings", [])
            header = (
                f"**{name}** — {d.get('vendor') or 'unknown vendor'} · "
                f"{money(d.get('total'), d.get('currency') or '')} · {status_label(findings)}"
            )
            with st.expander(header, expanded=len(audits) == 1):
                col_scan, col_data = st.columns(2, gap="large")
                with col_scan:
                    for page_num, img in render_evidence(
                        audit["hash"], audit["path"], audit["pages"], findings
                    ):
                        st.image(
                            img,
                            caption=f"Page {page_num} — findings highlighted",
                            use_container_width=True,
                        )
                with col_data:
                    if findings:
                        st.subheader("Findings")
                        for f in findings:
                            sev = str(f.get("severity", "low")).lower()
                            label = SEVERITY_LABELS.get(sev, sev).upper()
                            st.markdown(
                                f"**{label}** — {f.get('issue')}\n\n"
                                f"> “{f.get('evidence_quote', '')}” *(page {f.get('page', '?')})*"
                            )
                    else:
                        st.success("No issues found — document is clean.")
                    st.subheader("Extracted data")
                    meta_left, meta_right = st.columns(2)
                    meta_left.markdown(
                        f"**Vendor:** {d.get('vendor') or '—'}\n\n"
                        f"**Date:** {d.get('date') or '—'}\n\n"
                        f"**Invoice #:** {d.get('invoice_number') or '—'}"
                    )
                    meta_right.markdown(
                        f"**Subtotal:** {money(d.get('subtotal'), d.get('currency') or '')}\n\n"
                        f"**Tax:** {money(d.get('tax'), d.get('currency') or '')}\n\n"
                        f"**Total:** {money(d.get('total'), d.get('currency') or '')}"
                    )
                    if d.get("line_items"):
                        st.dataframe(
                            pd.DataFrame(d["line_items"]),
                            use_container_width=True,
                            hide_index=True,
                        )
