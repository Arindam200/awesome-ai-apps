"""Coach: proposes teacher interventions, revises them after the Analyst's challenge, and drafts
parent messages. Every path has a template fallback so the teacher always gets a plan."""

from __future__ import annotations

import json

from .. import prompts, schemas
from ..llm import LLM, LLMError, source_of
from ..prompts import LANGUAGES
from ..state import StudentRecord
from ..topic import Topic


def _worked_example(topic: Topic, concept_id: str) -> str:
    for q in topic.questions_for(concept_id, ("text", "photo")):
        return f"{q['stem']} {q['method']}"
    return topic.concept_name(concept_id)


def _next_steps_seed(topic: Topic, students: dict[str, StudentRecord], limit: int = 3) -> list[dict]:
    ranked = sorted((s for s in students.values() if s.top_gap()), key=lambda s: s.mastery[s.top_gap()[0]])
    seeds = []
    for s in ranked[:limit]:
        concept, _ = s.top_gap()
        items = [q["stem"] for q in topic.questions_for(concept, ("mcq", "text")) if q["id"] not in s.seen][:3]
        seeds.append({"student_id": s.id, "items": items})
    return seeds


def _context(topic, analysis, students, critiques=None):
    return {"analysis": analysis, "concept_names": {c: topic.concept_name(c) for c in topic.order},
            "worked_example": _worked_example(topic, analysis["focus_concept"]),
            "next_steps_seed": _next_steps_seed(topic, students), "critiques": critiques}


def _template(topic: Topic, analysis: dict, students: dict[str, StudentRecord]) -> dict:
    focus = analysis["focus_concept"]
    concept = analysis["concepts"][focus]
    tag = concept["top_misconceptions"][0][0] if concept["top_misconceptions"] else "unclassified"
    group = analysis["groups"]["reteach"]
    return {
        "recommendations": [{
            "group_label": f"Group A, {len(group)} students", "concept_id": focus, "misconception_tag": tag,
            "headline": f"Re-teach {topic.concept_name(focus).lower()} to Group A",
            "plan_5min": ["Show today's most common wrong answer", "Ask what went wrong",
                          "Work the correct method together", "Each student solves one item"],
            "worked_example": _worked_example(topic, focus),
            "why": f"{len(group)} of {analysis['n_students']} students are below 0.4 on {focus}.",
        }],
        "student_next_steps": _next_steps_seed(topic, students),
    }


def propose(topic: Topic, analysis: dict, students: dict[str, StudentRecord], llm: LLM) -> tuple[dict, str]:
    prompt = f"Class analysis:\n{json.dumps(analysis)}\n\nWorked example you may use:\n{_worked_example(topic, analysis['focus_concept'])}"
    try:
        out = llm.generate(system=prompts.COACH_PROPOSE, prompt=prompt, schema=schemas.CoachProposal,
                           context=_context(topic, analysis, students))
        return out.model_dump(), source_of(llm)
    except LLMError:
        return _template(topic, analysis, students), "template"


def revise(topic: Topic, analysis: dict, students: dict[str, StudentRecord], proposal: dict,
           critiques: list[dict], llm: LLM) -> tuple[dict, str]:
    prompt = (f"Class analysis:\n{json.dumps(analysis)}\n\nYour proposals:\n{json.dumps(proposal)}\n\n"
              f"Analyst verdicts:\n{json.dumps(critiques)}")
    try:
        out = llm.generate(system=prompts.COACH_REVISE, prompt=prompt, schema=schemas.CoachProposal,
                           context=_context(topic, analysis, students, critiques))
        return out.model_dump(), source_of(llm)
    except LLMError:
        return _template(topic, analysis, students), "template"


def parent_message(topic: Topic, student: StudentRecord, concept_id: str, tag: str, llm: LLM) -> tuple[dict, str]:
    tip = topic.definition(tag)
    prompt = (f"Target language: {LANGUAGES.get(student.language, 'English')}\nChild's name: {student.nickname}\n"
              f"Concept practised: {topic.concept_name(concept_id)}\nThe mistake to help with: {tip}")
    ctx = {"nickname": student.nickname, "concept_name": topic.concept_name(concept_id), "tip": tip,
           "language": student.language}
    try:
        out = llm.generate(system=prompts.PARENT, prompt=prompt, schema=schemas.ParentMessage, context=ctx)
        return out.model_dump(), source_of(llm)
    except LLMError:
        return parent_template(ctx), "template"


def parent_template(ctx: dict) -> dict:
    """English fallback used when no LLM is reachable."""
    return {"language": "en",
            "message": (f"Today {ctx['nickname']} practised {ctx['concept_name'].lower()} and kept trying on the hard "
                        f"ones. At home, please ask them to explain one question aloud. The mistake to watch for: "
                        f"{ctx['tip']} The teacher will follow up in class this week.")}
