"""Generate a large, dense, multi-page synthetic financial corpus for the demo.

~23 interlinked documents, multi-page where it counts (quarterly bank statements
with 30-40 transactions each flow across pages) so Unsiloed's table extraction is
genuinely exercised. Deterministic (seeded) for reproducibility.

Cross-document seeds preserved for the demo:
  - "Deloitte LLP" recurs across 8 statements + a contract + audits + tax filings
    (resolution) and is paid far above its $80k contract (over-contract anomaly)
  - One company address across every contract + loan (the cross-PDF edit target)
  - A duplicate payment within a quarter (duplicate-payment anomaly)
  - Globex holding drops across the two brokerage statements (valuation-drop)
  - Atlassian is paid in statements but omitted from tax filings (missing-tax)

Run: python -m app.seed.generate_corpus   (writes to backend/data/corpus/)
"""

import random
from datetime import date, timedelta
from pathlib import Path

from reportlab import rl_config

# Deterministic output: no embedded timestamps, so identical content -> identical
# bytes -> the content-hash cache dedupes re-generated documents correctly.
rl_config.invariant = 1

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.config import DATA_DIR

CORPUS_DIR = DATA_DIR / "corpus"
COMPANY = "Northwind Capital LLC"
ADDRESS = "100 Market St, Suite 400, San Francisco, CA 94105"

styles = getSampleStyleSheet()
H = ParagraphStyle("H", parent=styles["Title"], fontSize=18, spaceAfter=6)
SUB = ParagraphStyle("SUB", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#555"))
BODY = styles["Normal"]
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=4)


def _table(headers, rows, col_widths=None):
    t = Table([headers] + rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f7")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _doc(name):
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    path = CORPUS_DIR / name
    return SimpleDocTemplate(str(path), pagesize=LETTER, topMargin=0.7 * inch,
                             bottomMargin=0.7 * inch, leftMargin=0.8 * inch,
                             rightMargin=0.8 * inch, title=name), path


def _m(n):
    return f"{n:,.2f}"


# ---------- vendors & recurring patterns ----------

BANK = "First Meridian Bank"

# (vendor, description, monthly amount, category)
MONTHLY = [
    ("ADP Payroll", "Payroll run", 53200, "payroll"),
    ("Amazon Web Services", "Cloud services", 8600, "cloud"),
    ("WeWork", "Office rent", 18000, "rent"),
    ("Atlassian", "Software license", 3200, "software"),
    ("Salesforce", "CRM subscription", 4500, "software"),
    ("Google Workspace", "Email & productivity", 1450, "software"),
    ("Slack Technologies", "Team messaging", 980, "software"),
    ("Datadog", "Monitoring", 2100, "software"),
    ("GitHub", "Developer tooling", 1260, "software"),
    ("Anthropic", "AI API usage", 3400, "software"),
    ("Comcast Business", "Internet & phone", 740, "utilities"),
    ("PG&E", "Electricity", 1280, "utilities"),
    ("Anthem Health", "Employee health plan", 9600, "benefits"),
    ("The Hartford", "Business insurance", 2200, "insurance"),
]
# quarterly-ish one-offs (vendor, description, amount, category)
QUARTERLY = [
    ("Deloitte LLP", "Consulting fees", 45000, "professional_services"),
    ("Acme Supplies", "Office supplies", 12500, "supplies"),
    ("Morrison & Foerster LLP", "Legal fees", 22000, "legal"),
]
CLIENTS = [("Globex Corp", "Client payment", 72000), ("Initech Inc", "Client payment", 48000)]


def quarter_transactions(qstart: date, opening: float, seed: int, inject_dup: bool):
    """Build ~30-40 transactions for a quarter with a coherent running balance."""
    rng = random.Random(seed)
    txns = []
    bal = opening
    # three months in the quarter
    for m in range(3):
        month = (qstart.month - 1 + m) % 12 + 1
        year = qstart.year + (qstart.month - 1 + m) // 12
        # two client revenue events per month (credits)
        for ci, cl in enumerate(CLIENTS):
            amt = cl[2] + rng.randint(-4000, 8000)
            bal += amt
            txns.append((date(year, month, 2 + ci), cl[1], cl[0], amt, "credit", bal, "revenue"))
        # mid-month bonus payroll run (semi-monthly)
        bal -= 26000
        txns.append((date(year, month, 15), "Payroll run (semi-monthly)", "ADP Payroll", 26000, "debit", bal, "payroll"))
        # monthly recurring (debits) — spread across the month
        for di, (v, d, base, cat) in enumerate(MONTHLY):
            amt = base + rng.randint(-300, 400)
            bal -= amt
            txns.append((date(year, month, min(4 + di, 27)), d, v, amt, "debit", bal, cat))
        # one quarterly one-off per month, rotating
        v, d, base, cat = QUARTERLY[(m + seed) % len(QUARTERLY)]
        amt = base + rng.randint(-1500, 1500)
        bal -= amt
        txns.append((date(year, month, 22), d, v, amt, "debit", bal, cat))
        # several small misc debits
        for k in range(rng.randint(3, 5)):
            v = rng.choice(["Stripe Fees", "FedEx", "Uber for Business", "DoorDash for Work",
                            "Amazon Business", "Notion Labs", "Figma", "Zoom"])
            amt = rng.randint(120, 2400)
            bal -= amt
            txns.append((date(year, month, 24 + k), "Operating expense", v, amt, "debit", bal, "ops"))
    # always include a Deloitte payment each quarter (drives over-contract over time)
    bal -= 45000
    txns.append((date(qstart.year, qstart.month, 28), "Consulting fees", "Deloitte LLP", 45000, "debit", bal, "professional_services"))
    # inject a genuine duplicate Acme payment (same invoice paid twice, 3 days apart)
    if inject_dup:
        for off in (12, 15):
            bal -= 12500
            d = qstart + timedelta(days=off)
            txns.append((d, "Office supplies (INV-4471)", "Acme Supplies", 12500, "debit", bal, "supplies"))
    txns.sort(key=lambda t: t[0])
    # recompute running balance after sort so the column stays consistent
    bal = opening
    fixed = []
    for t in txns:
        bal = bal + t[3] if t[4] == "credit" else bal - t[3]
        fixed.append((t[0], t[1], t[2], t[3], t[4], bal, t[6]))
    return fixed, bal


def bank_statement(name, period_label, qstart, opening, seed, inject_dup):
    doc, path = _doc(name)
    txns, closing = quarter_transactions(qstart, opening, seed, inject_dup)
    rows = [[t[0].isoformat(), t[1], t[2], _m(t[3]), t[4], _m(t[5])] for t in txns]
    flow = [
        Paragraph(BANK, H),
        Paragraph(f"Business Checking Statement — {period_label}", SUB), Spacer(1, 6),
        Paragraph(f"Account Holder: {COMPANY}", BODY),
        Paragraph("Account: ****4821 (Business Checking) · USD", BODY),
        Paragraph(f"Opening Balance: ${_m(opening)}", BODY), Spacer(1, 10),
        _table(["Date", "Description", "Counterparty", "Amount", "Dir", "Balance"], rows,
               [0.8 * inch, 1.9 * inch, 1.5 * inch, 0.9 * inch, 0.5 * inch, 1.0 * inch]),
        Spacer(1, 8), Paragraph(f"Closing Balance: ${_m(closing)}", BODY),
    ]
    doc.build(flow)
    return path, closing


def investment_statement(name, asof, holdings):
    doc, path = _doc(name)
    rows = [[h[0], h[1], _m(h[2]), _m(h[3]), _m(h[4]), asof] for h in holdings]
    flow = [
        Paragraph("Vanguard Brokerage Services", H),
        Paragraph(f"Investment Account Statement — As of {asof}", SUB), Spacer(1, 6),
        Paragraph(f"Account Holder: {COMPANY} · Account ****7733", BODY), Spacer(1, 10),
        _table(["Holding", "Ticker", "Quantity", "Cost Basis", "Current Value", "Val. Date"], rows,
               [1.7 * inch, 0.7 * inch, 0.9 * inch, 1.0 * inch, 1.1 * inch, 0.9 * inch]),
    ]
    doc.build(flow)
    return path


CLAUSES = [
    "1. Scope. The Vendor shall provide the services described in Schedule A in a professional and workmanlike manner.",
    "2. Term. This Agreement is effective as of the Start Date and continues until the End Date unless terminated earlier.",
    "3. Fees. The Company shall pay the Contract Value in accordance with the Payment Terms set forth below.",
    "4. Confidentiality. Each party shall protect the other's confidential information using reasonable care.",
    "5. Indemnification. The Vendor shall indemnify the Company against third-party claims arising from its negligence.",
    "6. Limitation of Liability. Neither party's liability shall exceed the total fees paid under this Agreement.",
    "7. Termination. Either party may terminate for material breach upon thirty (30) days written notice.",
    "8. Governing Law. This Agreement is governed by the laws of the State of California.",
]


def contract(name, vendor, value, start, end, terms, ctype="vendor_contract"):
    doc, path = _doc(name)
    title = "Loan Agreement" if ctype == "loan_agreement" else "Master Services Agreement"
    flow = [Paragraph(title, H), Spacer(1, 6),
            Paragraph(f"This Agreement is entered into between <b>{COMPANY}</b> and <b>{vendor}</b>.", BODY),
            Paragraph(f"Registered office of {COMPANY}:", BODY),
            Paragraph(ADDRESS, BODY), Spacer(1, 8),
            Paragraph("Terms", H2),
            _table(["Field", "Value"],
                   [["Counterparty", vendor], ["Contract Value", f"${_m(value)} USD"],
                    ["Start Date", start], ["End Date", end], ["Payment Terms", terms],
                    ["Renewal", "Auto-renews annually unless terminated with 60 days notice"],
                    ["Company Address", ADDRESS]],
                   [1.6 * inch, 4.2 * inch]),
            Spacer(1, 10), Paragraph("Standard Terms & Conditions", H2)]
    flow += [Paragraph(c, BODY) for c in CLAUSES]
    flow += [Spacer(1, 10), Paragraph("Schedule A — Services & Milestones", H2),
             _table(["Milestone", "Description", "Due", "Fee"],
                    [["M1", f"Onboarding and discovery with {vendor}", start, f"${_m(value * 0.2)}"],
                     ["M2", "Implementation phase one", "Quarter 2", f"${_m(value * 0.3)}"],
                     ["M3", "Implementation phase two", "Quarter 3", f"${_m(value * 0.3)}"],
                     ["M4", "Final delivery and acceptance", end, f"${_m(value * 0.2)}"]],
                    [0.8 * inch, 3.0 * inch, 1.0 * inch, 1.0 * inch])]
    flow += [Spacer(1, 10), Paragraph(f"Executed on behalf of {COMPANY}, registered at:", SUB),
             Paragraph(ADDRESS, SUB)]
    doc.build(flow)
    return path


def loan_agreement(name, lender, principal, rate, maturity):
    doc, path = _doc(name)
    flow = [Paragraph("Loan Agreement", H), Spacer(1, 6),
            Paragraph(f"Borrower: <b>{COMPANY}</b>.  Lender: <b>{lender}</b>.", BODY),
            Paragraph("Borrower registered office:", BODY),
            Paragraph(ADDRESS, BODY), Spacer(1, 8),
            Paragraph("Loan Terms", H2),
            _table(["Field", "Value"],
                   [["Principal Amount", f"${_m(principal)} USD"],
                    ["Interest Rate", f"{rate}% per annum"], ["Maturity Date", maturity],
                    ["Repayment", "Monthly, interest-only, balloon at maturity"],
                    ["Company Address", ADDRESS]],
                   [1.6 * inch, 4.2 * inch]),
            Spacer(1, 10), Paragraph("Covenants", H2)]
    flow += [Paragraph(c, BODY) for c in CLAUSES[:5]]
    doc.build(flow)
    return path


def tax_filing(name, year, lines):
    doc, path = _doc(name)
    rows = [[l[0], l[1], _m(l[2])] for l in lines]
    flow = [Paragraph(f"Form 1120 — U.S. Corporation Income Tax Return ({year})", H),
            Paragraph(f"Taxpayer: {COMPANY} · Federal · EIN 47-2025xxx", SUB), Spacer(1, 10),
            Paragraph("Deductions — Schedule of Expenses", H2),
            _table(["Line Item", "Vendor", "Amount"], rows, [2.6 * inch, 1.8 * inch, 1.2 * inch])]
    doc.build(flow)
    return path


def audit_report(name, year, obligations):
    doc, path = _doc(name)
    rows = [[o[0], o[1], o[2], _m(o[3]), o[4]] for o in obligations]
    flow = [Paragraph(f"Independent Audit Report ({year})", H),
            Paragraph(f"Prepared for {COMPANY} by Deloitte LLP", SUB), Spacer(1, 8),
            Paragraph("In our opinion, the financial statements present fairly, in all material "
                      "respects, the financial position of the Company as of the year then ended. "
                      "The following obligations and commitments were identified during the review.", BODY),
            Spacer(1, 10), Paragraph("Identified Obligations", H2),
            _table(["Type", "Description", "Counterparty", "Amount", "Due Date"], rows,
                   [1.0 * inch, 1.9 * inch, 1.2 * inch, 0.9 * inch, 0.9 * inch])]
    doc.build(flow)
    return path


def annual_report(name, year, obligations, holdings):
    doc, path = _doc(name)
    flow = [Paragraph(f"{COMPANY} — Annual Report {year}", H), Spacer(1, 6),
            Paragraph("Management Discussion & Analysis", H2),
            Paragraph("The Company delivered steady revenue growth driven by recurring client "
                      "engagements with Globex Corp and Initech Inc. Operating expenses were "
                      "dominated by personnel, cloud infrastructure, and professional services. "
                      "Management continues to monitor vendor concentration and contractual "
                      "commitments.", BODY), Spacer(1, 8),
            Paragraph("Outstanding Obligations & Commitments", H2),
            _table(["Type", "Description", "Counterparty", "Amount", "Due Date"],
                   [[o[0], o[1], o[2], _m(o[3]), o[4]] for o in obligations],
                   [1.0 * inch, 1.9 * inch, 1.2 * inch, 0.9 * inch, 0.9 * inch]),
            Spacer(1, 10), Paragraph("Investment Holdings", H2),
            _table(["Holding", "Ticker", "Quantity", "Cost Basis", "Current Value", "Val. Date"],
                   [[h[0], h[1], _m(h[2]), _m(h[3]), _m(h[4]), f"{year}-12-31"] for h in holdings],
                   [1.7 * inch, 0.7 * inch, 0.9 * inch, 1.0 * inch, 1.1 * inch, 0.9 * inch])]
    doc.build(flow)
    return path


def generate_all():
    paths = []
    # 8 quarterly bank statements over 2024-2025, balance carried forward
    bal = 240000.0
    quarters = [
        ("Q1 2024", date(2024, 1, 1)), ("Q2 2024", date(2024, 4, 1)),
        ("Q3 2024", date(2024, 7, 1)), ("Q4 2024", date(2024, 10, 1)),
        ("Q1 2025", date(2025, 1, 1)), ("Q2 2025", date(2025, 4, 1)),
        ("Q3 2025", date(2025, 7, 1)), ("Q4 2025", date(2025, 10, 1)),
    ]
    for i, (label, qstart) in enumerate(quarters):
        fname = f"bank_statement_{qstart.year}_q{(qstart.month - 1) // 3 + 1}.pdf"
        p, bal = bank_statement(fname, label, qstart, bal, seed=100 + i, inject_dup=(i == 5))
        paths.append(p)

    # 2 brokerage statements — Globex drops between them
    paths.append(investment_statement("investment_statement_2025h1.pdf", "2025-06-30", [
        ["Globex Corp (private)", "—", 100000, 500000, 500000],
        ["Initech Series A", "—", 50000, 250000, 360000],
        ["Vanguard S&P 500 ETF", "VOO", 1200, 480000, 561000],
        ["iShares Core US Agg", "AGG", 2000, 200000, 196000],
    ]))
    paths.append(investment_statement("investment_statement_2025h2.pdf", "2025-12-31", [
        ["Globex Corp (private)", "—", 100000, 500000, 320000],  # -36% drop
        ["Initech Series A", "—", 50000, 250000, 410000],
        ["Vanguard S&P 500 ETF", "VOO", 1200, 480000, 612000],
        ["iShares Core US Agg", "AGG", 2000, 200000, 201000],
    ]))

    # 6 contracts (Deloitte over-contract: $80k vs ~$360k paid across statements)
    paths.append(contract("contract_deloitte.pdf", "Deloitte LLP", 80000, "2024-01-01", "2026-09-30", "Net 30"))
    paths.append(contract("contract_acme.pdf", "Acme Supplies", 50000, "2024-01-01", "2026-12-31", "Net 15"))
    paths.append(contract("contract_aws.pdf", "Amazon Web Services", 110000, "2024-06-01", "2026-05-31", "Net 30"))
    paths.append(contract("contract_atlassian.pdf", "Atlassian", 40000, "2024-03-01", "2026-02-28", "Annual"))
    paths.append(contract("contract_salesforce.pdf", "Salesforce", 55000, "2025-01-01", "2026-12-31", "Annual"))
    paths.append(contract("contract_mofo.pdf", "Morrison & Foerster LLP", 90000, "2024-01-01", "2026-08-15", "Net 45"))

    # 2 loans (share the company address)
    paths.append(loan_agreement("loan_svb_term.pdf", "Silicon Valley Bank", 500000, 7.5, "2028-06-30"))
    paths.append(loan_agreement("loan_line_of_credit.pdf", "First Meridian Bank", 250000, 9.25, "2027-03-31"))

    # 2 tax filings — Atlassian omitted (missing-tax anomaly)
    for yr in (2024, 2025):
        paths.append(tax_filing(f"tax_filing_{yr}.pdf", yr, [
            ["Professional services", "Deloitte LLP", 180000],
            ["Cloud infrastructure", "Amazon Web Services", 103000],
            ["Office supplies", "Acme Supplies", 60000],
            ["Payroll", "ADP Payroll", 638000],
            ["Legal fees", "Morrison & Foerster LLP", 88000],
            ["Office rent", "WeWork", 216000],
        ]))

    # 2 audit reports
    for yr in (2024, 2025):
        paths.append(audit_report(f"audit_report_{yr}.pdf", yr, [
            ["Lease", "HQ office lease commitment", "WeWork", 720000, f"{yr + 3}-12-31"],
            ["Debt", "Term loan principal", "Silicon Valley Bank", 500000, "2028-06-30"],
            ["Debt", "Revolving credit facility", "First Meridian Bank", 250000, "2027-03-31"],
            ["Payable", "Outstanding vendor invoices", "Acme Supplies", 16800, f"{yr + 1}-01-31"],
        ]))

    # 1 annual report (multi-page)
    paths.append(annual_report("annual_report_2025.pdf", 2025, [
        ["Lease", "HQ office lease commitment", "WeWork", 720000, "2028-12-31"],
        ["Debt", "Term loan principal", "Silicon Valley Bank", 500000, "2028-06-30"],
        ["Commitment", "Cloud spend commitment", "Amazon Web Services", 110000, "2026-05-31"],
    ], [
        ["Globex Corp (private)", "—", 100000, 500000, 320000],
        ["Initech Series A", "—", 50000, 250000, 410000],
    ]))

    return paths


if __name__ == "__main__":
    out = generate_all()
    total_pages = 0
    try:
        import fitz
        for p in out:
            total_pages += fitz.open(p).page_count
    except Exception:
        pass
    print(f"generated {len(out)} documents ({total_pages or '?'} pages) in {CORPUS_DIR}")
    for p in out:
        print(" ", p.name)
