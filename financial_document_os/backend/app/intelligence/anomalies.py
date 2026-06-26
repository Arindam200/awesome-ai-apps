"""Anomaly detection — deterministic rules over the entity tables.

Each rule emits an Anomaly row with resolved evidence_citation_ids so the UI
can show the exact bbox(es) backing the claim. Idempotent: clears prior
anomalies for the project before recomputing.
"""

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Anomaly,
    Contract,
    EntityCitation,
    Investment,
    Obligation,
    TaxItem,
    Transaction,
    Vendor,
)

logger = logging.getLogger(__name__)

EXPIRING_DAYS = 365
OBLIGATION_THRESHOLD = 500_000
DUP_WINDOW_DAYS = 10  # real duplicate payments land days apart; recurring bills are >=15 days apart


def _citations_for(db: Session, entity_kind: str, entity_id: int, field: str | None = None) -> list[int]:
    q = select(EntityCitation.id).where(
        EntityCitation.entity_kind == entity_kind, EntityCitation.entity_id == entity_id
    )
    if field:
        q = q.where(EntityCitation.field_name == field)
    return list(db.scalars(q))


def run(db: Session, project, today: date | None = None) -> int:
    today = today or date.today()
    pid = project.id
    db.query(Anomaly).filter(Anomaly.project_id == pid).delete(synchronize_session=False)
    db.commit()

    found: list[Anomaly] = []
    seen_keys: set[str] = set()

    def add(rule, severity, title, description, refs, cite_ids, key=None):
        dedup = key or (f"{rule}:" + ",".join(f"{r['entity_kind']}{r['entity_id']}" for r in refs))
        if dedup in seen_keys:
            return  # collapse the same real-world finding seen across multiple documents
        seen_keys.add(dedup)
        found.append(Anomaly(
            project_id=pid, rule=rule, severity=severity, title=title, description=description,
            entity_refs=refs, evidence_citation_ids=cite_ids, source="rule", dedup_key=dedup,
        ))

    # 1. Vendor paid more than its contract value
    contracts = db.scalars(
        select(Contract).where(Contract.project_id == pid, Contract.canonical_vendor_id.isnot(None),
                               Contract.contract_value.isnot(None))
    ).all()
    for c in contracts:
        paid = db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.project_id == pid,
                Transaction.canonical_vendor_id == c.canonical_vendor_id,
                Transaction.direction == "debit",
            )
        ) or 0
        if float(paid) > float(c.contract_value) * 1.01:
            cites = _citations_for(db, "contract", c.id, "contract_value")
            add("vendor_over_contract", "high",
                f"{c.counterparty} paid above contract value",
                f"Paid ${float(paid):,.0f} against a ${float(c.contract_value):,.0f} contract "
                f"(${float(paid) - float(c.contract_value):,.0f} over).",
                [{"entity_kind": "contract", "entity_id": c.id}], cites)

    # 2. Duplicate payment — same canonical vendor, same amount, within window
    txns = db.scalars(
        select(Transaction).where(Transaction.project_id == pid, Transaction.direction == "debit",
                                  Transaction.amount.isnot(None))
    ).all()
    by_key: dict[tuple, list[Transaction]] = {}
    for t in txns:
        by_key.setdefault((t.canonical_vendor_id, float(t.amount)), []).append(t)
    for (cv, amt), group in by_key.items():
        if cv is None or len(group) < 2:
            continue
        group.sort(key=lambda t: t.txn_date or date.min)
        for a, b in zip(group, group[1:]):
            if a.txn_date and b.txn_date and (b.txn_date - a.txn_date) <= timedelta(days=DUP_WINDOW_DAYS):
                cites = _citations_for(db, "transaction", a.id, "amount") + _citations_for(db, "transaction", b.id, "amount")
                add("duplicate_payment", "high",
                    f"Possible duplicate payment to {b.counterparty}",
                    f"Two ${amt:,.0f} debits to {b.counterparty} on {a.txn_date} and {b.txn_date}.",
                    [{"entity_kind": "transaction", "entity_id": a.id},
                     {"entity_kind": "transaction", "entity_id": b.id}], cites)

    # 3. Contracted vendor paid in statements but absent from tax filings.
    #    Scoped to vendors we have a CONTRACT with (a material relationship) so
    #    incidental one-off payees don't create noise.
    paid_vendors = set(db.scalars(
        select(Transaction.canonical_vendor_id).where(
            Transaction.project_id == pid, Transaction.direction == "debit",
            Transaction.canonical_vendor_id.isnot(None)).distinct()
    ))
    contracted_vendors = set(db.scalars(
        select(Contract.canonical_vendor_id).where(
            Contract.project_id == pid, Contract.canonical_vendor_id.isnot(None)).distinct()
    ))
    taxed_vendors = set(db.scalars(
        select(TaxItem.canonical_vendor_id).where(
            TaxItem.project_id == pid, TaxItem.canonical_vendor_id.isnot(None)).distinct()
    ))
    for cv in (paid_vendors & contracted_vendors) - taxed_vendors:
        v = db.get(Vendor, cv)
        total = db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.project_id == pid, Transaction.canonical_vendor_id == cv,
                Transaction.direction == "debit")
        ) or 0
        if float(total) < 1000:
            continue
        sample = db.scalar(select(Transaction).where(
            Transaction.project_id == pid, Transaction.canonical_vendor_id == cv,
            Transaction.direction == "debit"))
        add("expense_not_in_tax", "medium",
            f"{v.name if v else 'Vendor'} expensed but not in any tax filing",
            f"${float(total):,.0f} paid to {v.name if v else 'this vendor'} appears in statements "
            f"but has no matching tax-filing line item.",
            [{"entity_kind": "transaction", "entity_id": sample.id}] if sample else [],
            _citations_for(db, "transaction", sample.id, "counterparty") if sample else [])

    # 4. Investment valuation below cost basis
    invs = db.scalars(
        select(Investment).where(Investment.project_id == pid, Investment.current_value.isnot(None),
                                 Investment.cost_basis.isnot(None))
    ).all()
    for inv in invs:
        if float(inv.current_value) < float(inv.cost_basis):
            drop = float(inv.cost_basis) - float(inv.current_value)
            pct = drop / float(inv.cost_basis) * 100
            add("valuation_drop", "high" if pct >= 25 else "medium",
                f"{inv.holding_name} is below cost basis",
                f"Now ${float(inv.current_value):,.0f} vs ${float(inv.cost_basis):,.0f} cost "
                f"(down {pct:.0f}%).",
                [{"entity_kind": "investment", "entity_id": inv.id}],
                _citations_for(db, "investment", inv.id, "current_value"),
                key=f"valuation_drop:{(inv.holding_name or '').lower()}")

    # 5. Contracts / loans expiring within a year
    for c in db.scalars(select(Contract).where(Contract.project_id == pid)).all():
        exp = c.end_date or c.maturity_date
        if exp and today <= exp <= today + timedelta(days=EXPIRING_DAYS):
            field = "end_date" if c.end_date else "maturity_date"
            add("contract_expiring", "medium",
                f"{c.counterparty} {('contract' if c.contract_type != 'loan_agreement' else 'loan')} expires {exp}",
                f"Expires in {(exp - today).days} days.",
                [{"entity_kind": "contract", "entity_id": c.id}],
                _citations_for(db, "contract", c.id, field))

    # 6. Obligations over threshold
    for o in db.scalars(
        select(Obligation).where(Obligation.project_id == pid, Obligation.amount.isnot(None))
    ).all():
        if float(o.amount) >= OBLIGATION_THRESHOLD:
            add("large_obligation", "medium",
                f"Large obligation: {o.description or o.obligation_type}",
                f"${float(o.amount):,.0f} owed{f' to {o.counterparty}' if o.counterparty else ''}"
                f"{f', due {o.due_date}' if o.due_date else ''}.",
                [{"entity_kind": "obligation", "entity_id": o.id}],
                _citations_for(db, "obligation", o.id, "amount"),
                key=f"large_obligation:{(o.counterparty or '').lower()}:{float(o.amount):.0f}")

    for a in found:
        db.add(a)
    db.commit()
    logger.info("anomalies: %d detected", len(found))
    return len(found)
