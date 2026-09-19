"""Analyst: turns the class's graph into numbers, groups, and a data check on the Coach's plans.

Aggregation is pure Python. The critique starts from explicit rules so every challenge cites real
numbers; the LLM is only asked to phrase it, and the rule text is used if the LLM is unavailable.
"""

from __future__ import annotations

import json
from collections import Counter

from .. import prompts, schemas
from ..llm import LLM, LLMError, source_of
from ..state import GAP_BELOW, MASTERED_AT, PRIOR, StudentRecord
from ..topic import Topic

WHOLE_CLASS_MIN_SHARE = 0.5  # re-teach everyone only if at least half the class shows the misconception
MAX_PLAN_STEPS = 5
META_TAGS = {"careless_arithmetic", "unclassified"}


def analyze(topic: Topic, students: dict[str, StudentRecord]) -> dict:
    """Aggregate the class. Slips and unclassified answers are counted but never chosen as a teaching
    target: a teacher can act on a misconception, not on 'careless'."""
    n = len(students)
    concepts = {}
    for cid in topic.order:
        responders = [s for s in students.values() if s.answered(cid)]
        avg = sum(s.mastery[cid] for s in responders) / len(responders) if responders else PRIOR
        tags = Counter()
        affected = Counter()
        for s in students.values():
            for tag, count in s.misconceptions.get(cid, {}).items():
                tags[tag] += count
                affected[tag] += 1
        conceptual = Counter({t: c for t, c in tags.items() if t not in META_TAGS})
        concepts[cid] = {
            "name": topic.concept_name(cid),
            "avg": round(avg, 3),
            "responders": len(responders),
            "below_gap": sum(1 for s in responders if s.mastery[cid] < GAP_BELOW),
            "top_misconceptions": conceptual.most_common(3),
            "slips": sum(c for t, c in tags.items() if t in META_TAGS),
            "affected_by_tag": dict(affected),
        }

    # Focus = the concept with the most open gaps (the unit a teacher can close); ties and a gap-free
    # class fall back to the lowest average among concepts enough students have answered.
    open_by_concept = Counter(c for s in students.values() for c, st in s.gaps.items() if st == "open")
    min_responders = max(1, min(5, n // 4))
    ranked = [c for c in topic.order if concepts[c]["responders"] >= min_responders] or topic.order
    focus = min(ranked, key=lambda c: (-open_by_concept.get(c, 0), concepts[c]["avg"], topic.order.index(c)))

    groups = {"reteach": [], "practice": [], "extend": [], "not_assessed": []}
    for s in students.values():
        if not s.answered(focus):
            groups["not_assessed"].append(s.id)
            continue
        m = s.mastery[focus]
        key = "reteach" if m < GAP_BELOW else ("extend" if m >= MASTERED_AT else "practice")
        groups[key].append(s.id)

    gaps = Counter(status for s in students.values() for status in s.gaps.values())
    total_gaps = gaps["open"] + gaps["closed"]
    return {
        "n_students": n,
        "concepts": concepts,
        "focus_concept": focus,
        "groups": groups,
        "open_gaps": gaps["open"],
        "closed_gaps": gaps["closed"],
        "gap_closure_rate": round(gaps["closed"] / total_gaps, 3) if total_gaps else 0.0,
        "most_open_gaps_concept": open_by_concept.most_common(1)[0][0] if open_by_concept else None,
    }


def rule_critiques(analysis: dict, proposal: dict) -> list[dict]:
    """Check each recommendation against the data. Returns schema-shaped critiques."""
    n = analysis["n_students"]
    out = []
    targeted = {r["concept_id"] for r in proposal["recommendations"]}
    for i, rec in enumerate(proposal["recommendations"]):
        concept = analysis["concepts"].get(rec["concept_id"])
        problems = []
        if concept is None:
            problems.append(f"{rec['concept_id']} is not a concept in this topic.")
        else:
            affected = concept["affected_by_tag"].get(rec["misconception_tag"], 0)
            share = affected / n if n else 0
            whole_class = "whole" in rec["group_label"].lower()
            if whole_class and share < WHOLE_CLASS_MIN_SHARE:
                problems.append(
                    f"Only {affected} of {n} students show {rec['misconception_tag']} on "
                    f"{rec['concept_id']}; re-teaching everyone wastes the period. Split the class."
                )
            elif affected == 0:
                problems.append(f"No student shows {rec['misconception_tag']} on {rec['concept_id']}.")
            top = [t for t, _ in concept["top_misconceptions"]]
            if top and rec["misconception_tag"] not in top:
                problems.append(
                    f"{rec['misconception_tag']} is not among the top misconceptions on "
                    f"{rec['concept_id']} ({', '.join(top)})."
                )
        if len(rec["plan_5min"]) > MAX_PLAN_STEPS or not rec["worked_example"].strip():
            problems.append("The plan needs at most 5 steps and one worked example.")
        worst = analysis.get("most_open_gaps_concept")
        if i == 0 and worst and worst not in targeted:
            problems.append(f"{worst} has the most open gaps but no recommendation targets it.")
        out.append(
            {
                "recommendation_index": i,
                "verdict": "revise" if problems else "accept",
                "reason": " ".join(problems)
                if problems
                else f"Matches the data: {concept['affected_by_tag'].get(rec['misconception_tag'], 0)} of {n} "
                f"students show this on {rec['concept_id']}.",
            }
        )
    return out


def critique(analysis: dict, proposal: dict, llm: LLM) -> tuple[list[dict], str]:
    """Rule-backed critique, phrased by the LLM when available. Returns (critiques, source)."""
    rules = rule_critiques(analysis, proposal)
    compact = {
        "n_students": analysis["n_students"],
        "focus_concept": analysis["focus_concept"],
        "concepts": {c: {k: v for k, v in d.items() if k != "name"} for c, d in analysis["concepts"].items()},
    }
    prompt = (
        f"Class numbers:\n{json.dumps(compact)}\n\nCoach proposals:\n{json.dumps(proposal['recommendations'])}\n\n"
        f"Rule checks (binding):\n{json.dumps(rules)}"
    )
    try:
        out = llm.generate(
            system=prompts.ANALYST_CRITIQUE,
            prompt=prompt,
            schema=schemas.CritiqueSet,
            context={"rule_critiques": rules},
        )
        phrased = [c.model_dump() for c in out.critiques]
        # the rules are binding: the LLM may only rephrase, never flip a verdict
        by_index = {c["recommendation_index"]: c for c in phrased}
        merged = []
        for r in rules:
            p = by_index.get(r["recommendation_index"])
            merged.append({**r, "reason": p["reason"]} if p and p["verdict"] == r["verdict"] else r)
        return merged, source_of(llm)
    except LLMError:
        return rules, "rules"
