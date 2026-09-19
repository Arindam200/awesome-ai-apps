"""The shared Knowledge-Gap Graph: per-student mastery, misconceptions and gap status.

Every agent reads and writes this state. The update rules are deliberately simple and
explainable, so a teacher can be told exactly why a concept turned red.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

PRIOR = 0.5            # mastery before any evidence
CORRECT_DELTA = 0.15   # mastery gained for a correct answer
WRONG_DELTA = -0.20    # mastery lost for a wrong answer
GAP_BELOW = 0.4        # a concept below this after a tagged mistake is an open gap
READY_AT = 0.6         # prerequisites must reach this before a concept is examined
MASTERED_AT = 0.7


@dataclass
class StudentRecord:
    id: str
    nickname: str
    language: str
    mastery: dict[str, float]
    misconceptions: dict[str, dict[str, int]] = field(default_factory=dict)
    gaps: dict[str, str] = field(default_factory=dict)          # concept -> "open" | "closed"
    seen: list[str] = field(default_factory=list)               # question ids
    responses: list[dict] = field(default_factory=list)

    def answered(self, concept_id: str) -> int:
        return sum(1 for r in self.responses if r["concept_id"] == concept_id)

    def top_gap(self) -> tuple[str, str] | None:
        """(concept, misconception) of the weakest open gap, if any."""
        open_gaps = [c for c, status in self.gaps.items() if status == "open"]
        if not open_gaps:
            return None
        concept = min(open_gaps, key=lambda c: self.mastery[c])
        tags = self.misconceptions.get(concept, {})
        tag = max(tags, key=tags.get) if tags else "unclassified"
        return concept, tag


def new_student(student_id: str, nickname: str, language: str, concept_ids: list[str]) -> StudentRecord:
    return StudentRecord(id=student_id, nickname=nickname, language=language,
                         mastery={c: PRIOR for c in concept_ids})


def apply_diagnosis(student: StudentRecord, question: dict, answer: str, diagnosis: dict) -> float:
    """Update mastery and gap status from one diagnosed answer. Returns the mastery delta."""
    concept = question["concept_id"]
    before = student.mastery[concept]
    delta = CORRECT_DELTA if diagnosis["correct"] else WRONG_DELTA
    student.mastery[concept] = round(min(1.0, max(0.0, before + delta)), 3)
    student.seen.append(question["id"])
    student.responses.append({"question_id": question["id"], "concept_id": concept, "answer": answer, **diagnosis})
    tag = diagnosis.get("misconception_tag")
    if not diagnosis["correct"] and tag:
        bucket = student.misconceptions.setdefault(concept, {})
        bucket[tag] = bucket.get(tag, 0) + 1
        if student.mastery[concept] < GAP_BELOW:
            student.gaps[concept] = "open"
    return round(student.mastery[concept] - before, 3)


def close_gap(student: StudentRecord, concept_id: str, retry_correct: bool) -> bool:
    """A gap closes only when every retry item on that concept is answered correctly."""
    if student.gaps.get(concept_id) != "open":
        return False
    if retry_correct:
        student.gaps[concept_id] = "closed"
        student.mastery[concept_id] = max(student.mastery[concept_id], READY_AT)
        return True
    return False


class ClassroomState(TypedDict, total=False):
    """LangGraph state. `events` is append-only; every agent hand-off adds one entry."""

    topic: Any
    personas: list[dict]
    students: dict[str, StudentRecord]
    questions_per_student: int
    seed: int
    lesson_language: str | None
    events: Annotated[list[dict], operator.add]
    analysis: dict
    proposal: dict
    critiques: list[dict]
    recommendations: list[dict]
    lessons: list[dict]
    parent_messages: list[dict]


def event(agent: str, action: str, reason: str, student_id: str | None = None) -> dict:
    return {"agent": agent, "action": action, "reason": reason[:240], "student_id": student_id}
