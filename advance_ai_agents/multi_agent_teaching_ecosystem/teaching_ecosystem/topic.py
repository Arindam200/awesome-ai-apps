"""Topic pack loading and answer parsing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from fractions import Fraction
from math import gcd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:\s*/\s*\d+)?")


@dataclass(frozen=True)
class Topic:
    id: str
    name: str
    concepts: dict[str, dict]
    order: list[str]
    taxonomy: dict[str, str]
    questions: dict[str, dict]

    def concept_name(self, concept_id: str) -> str:
        return self.concepts[concept_id]["name"]

    def prereqs(self, concept_id: str) -> list[str]:
        return list(self.concepts[concept_id]["prereqs"])

    def questions_for(self, concept_id: str, kinds: tuple[str, ...] = ("mcq", "text", "photo")) -> list[dict]:
        return [q for q in self.questions.values() if q["concept_id"] == concept_id and q["kind"] in kinds]

    def definition(self, tag: str) -> str:
        return self.taxonomy.get(tag, self.taxonomy["unclassified"])


def _topological(concepts: list[dict]) -> list[str]:
    remaining = {c["id"]: set(c["prereqs"]) for c in concepts}
    order: list[str] = []
    while remaining:
        ready = sorted(cid for cid, pre in remaining.items() if pre <= set(order))
        if not ready:
            raise ValueError("prerequisite cycle in topic pack")
        order.extend(ready)
        for cid in ready:
            remaining.pop(cid)
    return order


def load_topic(path: Path | None = None) -> Topic:
    raw = json.loads((path or DATA_DIR / "fractions.json").read_text(encoding="utf-8"))
    concepts = {c["id"]: c for c in raw["concepts"]}
    return Topic(
        id=raw["topic"]["id"],
        name=raw["topic"]["name"],
        concepts=concepts,
        order=_topological(raw["concepts"]),
        taxonomy={t["tag"]: t["definition"] for t in raw["taxonomy"]},
        questions={q["id"]: q for q in raw["questions"]},
    )


def load_personas(path: Path | None = None) -> list[dict]:
    return json.loads((path or DATA_DIR / "personas.json").read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    """Canonical form for matching typed answers: lower case, no spaces around '/'."""
    return re.sub(r"\s*/\s*", "/", " ".join(text.lower().split()))


def parse_answer(text: str) -> Fraction | None:
    """Read the first number or fraction in a typed answer: '3/5', '0.6', '6 pieces', '2 / 1'."""
    match = _NUMBER.search(text or "")
    if not match:
        return None
    token = match.group(0).replace(" ", "")
    try:
        if "/" in token:
            num, den = token.split("/")
            return Fraction(int(float(num)), int(den)) if int(den) else None
        return Fraction(token)
    except (ValueError, ZeroDivisionError):
        return None


def is_simplest(text: str) -> bool:
    """True when a typed fraction is in lowest terms (decimals and whole numbers count as simplest)."""
    match = _NUMBER.search(text or "")
    if not match or "/" not in match.group(0):
        return True
    num, den = (int(float(x)) for x in match.group(0).replace(" ", "").split("/"))
    return den == 1 or gcd(abs(num), den) == 1
