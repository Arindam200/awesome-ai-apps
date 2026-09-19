"""Examiner: chooses the next question from the student's position in the Knowledge-Gap Graph.

Rule (no LLM): among concepts whose prerequisites are all at or above READY_AT, pick the one with the
lowest mastery, breaking ties by curriculum order, and ask at most MAX_PER_CONCEPT questions on it
per session so one gap cannot swallow the whole quiz.
"""

from __future__ import annotations

from ..state import READY_AT, StudentRecord
from ..topic import Topic

MAX_PER_CONCEPT = 2


def eligible_concepts(topic: Topic, student: StudentRecord) -> list[str]:
    return [c for c in topic.order if all(student.mastery[p] >= READY_AT for p in topic.prereqs(c))]


def next_question(topic: Topic, student: StudentRecord,
                  kinds: tuple[str, ...] = ("mcq", "text")) -> tuple[dict, str] | None:
    """Return (question, reason) or None when nothing suitable is left."""
    candidates = [c for c in eligible_concepts(topic, student) if student.answered(c) < MAX_PER_CONCEPT]
    candidates.sort(key=lambda c: (student.mastery[c], topic.order.index(c)))
    for concept in candidates:
        unseen = [q for q in topic.questions_for(concept, kinds) if q["id"] not in student.seen]
        if unseen:
            question = unseen[0]
            prereqs = topic.prereqs(concept)
            gate = ", ".join(f"{p} {student.mastery[p]:.2f}" for p in prereqs) or "none"
            reason = (f"{concept} has the lowest ready mastery ({student.mastery[concept]:.2f}); "
                      f"prerequisites: {gate}")
            return question, reason
    return None
