"""Cross-document entity resolution.

Collapses counterparty/vendor names that appear across many documents into one
canonical Vendor row, and sets canonical_vendor_id on every entity that names a
party. Makes "Deloitte across a contract + statements + an audit = one vendor"
a single WHERE clause, and powers cross-PDF edit impact analysis.

Idempotent: rebuilds canonical vendors from scratch each run.
"""

import logging

from rapidfuzz import fuzz
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.intelligence.normalize import normalize_name
from app.models import (
    Account,
    Contract,
    Investment,
    Obligation,
    TaxItem,
    Transaction,
    Vendor,
)

logger = logging.getLogger(__name__)

AUTO_MERGE = 92  # >= -> same canonical vendor
REVIEW_BAND = 85  # 85..92 -> still link but flag needs_review

# (model, name_column) for every place a party name appears
NAME_SOURCES = [
    (Transaction, "counterparty"),
    (Contract, "counterparty"),
    (Obligation, "counterparty"),
    (TaxItem, "counterparty"),
    (Account, "institution_name"),
    (Investment, "holding_name"),
]


def _best_canonical(norm: str, canon: list[Vendor]) -> tuple[Vendor | None, float]:
    best, best_score = None, 0.0
    for c in canon:
        if c.normalized_name == norm:
            return c, 100.0
        score = fuzz.token_sort_ratio(norm, c.normalized_name)
        if score > best_score:
            best, best_score = c, score
    return best, best_score


def run(db: Session, project) -> int:
    # 1. reset: drop canonical vendors, null every link
    db.query(Vendor).filter(Vendor.project_id == project.id, Vendor.is_canonical.is_(True)).delete(
        synchronize_session=False
    )
    for model, _ in NAME_SOURCES:
        db.execute(
            update(model).where(model.project_id == project.id).values(canonical_vendor_id=None)
        )
    db.execute(
        update(Vendor).where(Vendor.project_id == project.id).values(canonical_vendor_id=None)
    )
    db.commit()

    # 2. gather every (display_name, normalized) seen anywhere
    names: dict[str, str] = {}  # normalized -> a representative display name
    extracted_vendors = list(
        db.scalars(select(Vendor).where(Vendor.project_id == project.id, Vendor.is_canonical.is_(False)))
    )
    for v in extracted_vendors:
        if v.normalized_name:
            names.setdefault(v.normalized_name, v.name)
    for model, col in NAME_SOURCES:
        rows = db.execute(
            select(getattr(model, col)).where(
                model.project_id == project.id, getattr(model, col).isnot(None)
            ).distinct()
        ).all()
        for (raw,) in rows:
            norm = normalize_name(raw)
            if norm:
                names.setdefault(norm, raw)

    # 3. cluster normalized names into canonical vendors (fuzzy-merge near dupes)
    canon: list[Vendor] = []
    norm_to_canon: dict[str, Vendor] = {}
    for norm, display in sorted(names.items()):
        match, score = _best_canonical(norm, canon)
        if match and score >= AUTO_MERGE:
            norm_to_canon[norm] = match
            continue
        # carry over address/tax_id from an extracted vendor row if we have one
        src = next((v for v in extracted_vendors if v.normalized_name == norm), None)
        cv = Vendor(
            project_id=project.id,
            name=display,
            normalized_name=norm,
            address=src.address if src else None,
            tax_id=src.tax_id if src else None,
            is_canonical=True,
        )
        db.add(cv)
        db.flush()
        canon.append(cv)
        norm_to_canon[norm] = cv
    db.commit()

    # 4. link every entity to its canonical vendor
    linked = 0

    def _link(model, col):
        nonlocal linked
        rows = list(db.scalars(select(model).where(model.project_id == project.id)))
        for row in rows:
            raw = getattr(row, col, None)
            norm = normalize_name(raw)
            if not norm:
                continue
            cv = norm_to_canon.get(norm)
            if cv is None:
                cv, score = _best_canonical(norm, canon)
                if not cv or score < REVIEW_BAND:
                    continue
            row.canonical_vendor_id = cv.id
            linked += 1

    for model, col in NAME_SOURCES:
        _link(model, col)
    # link extracted vendor rows to their canonical too
    for v in extracted_vendors:
        cv = norm_to_canon.get(v.normalized_name)
        if cv:
            v.canonical_vendor_id = cv.id
    db.commit()

    logger.info("resolve: %d canonical vendors, %d entity links", len(canon), linked)
    return len(canon)
