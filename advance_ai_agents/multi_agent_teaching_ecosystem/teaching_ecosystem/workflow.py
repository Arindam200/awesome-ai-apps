"""The LangGraph workflow that connects the five agents around the shared Knowledge-Gap Graph.

    assess_class -> analyze -> coach_propose -> analyst_critique -+-> coach_revise -> curate -> END
                                                                  +-----------------> curate

`analyst_critique` routes to `coach_revise` only when at least one proposal was challenged.
"""

from __future__ import annotations

import random

from langgraph.graph import END, START, StateGraph

from .agents import analyst, coach, curator, diagnostician, examiner
from .llm import LLM
from .simulator import simulate_answer
from .state import ClassroomState, StudentRecord, apply_diagnosis, event, new_student
from .topic import Topic


def build_workflow(llm: LLM, lesson_cache: dict | None = None, max_lessons: int = 3):
    cache = lesson_cache if lesson_cache is not None else {}

    def assess_class(state: ClassroomState) -> dict:
        topic: Topic = state["topic"]
        rng = random.Random(state.get("seed", 42))
        students: dict[str, StudentRecord] = {}
        events = []
        llm_calls = 0
        for persona in state["personas"]:
            s = new_student(persona["id"], persona["nickname"], persona["language"], topic.order)
            for _ in range(state.get("questions_per_student", 8)):
                picked = examiner.next_question(topic, s)
                if picked is None:
                    break
                question, reason = picked
                answer = simulate_answer(topic, persona, question, rng)
                diagnosis = diagnostician.diagnose(topic, question, answer, llm)
                llm_calls += diagnosis["source"] == "llm"
                apply_diagnosis(s, question, answer, diagnosis)
                if not students:  # trace the first student in full so the hand-offs are visible
                    events.append(event("Examiner", "select_question", f"{question['id']}: {reason}", s.id))
                    events.append(event("Diagnostician", "diagnose",
                                        f"{s.nickname} answered {answer!r}: {diagnostician.explain(topic, diagnosis)}", s.id))
            students[s.id] = s
        answered = sum(len(s.responses) for s in students.values())
        events.append(event("Diagnostician", "class_done",
                            f"{answered} answers from {len(students)} students diagnosed; {llm_calls} needed the LLM."))
        return {"students": students, "events": events}

    def analyze(state: ClassroomState) -> dict:
        a = analyst.analyze(state["topic"], state["students"])
        focus = a["concepts"][a["focus_concept"]]
        top = focus["top_misconceptions"][0][0] if focus["top_misconceptions"] else "none"
        reason = (f"Focus {a['focus_concept']} ({focus['name']}), average {focus['avg']:.2f}; top misconception {top}; "
                  f"{a['open_gaps']} open gaps; groups re-teach {len(a['groups']['reteach'])}, "
                  f"practise {len(a['groups']['practice'])}, extend {len(a['groups']['extend'])}, "
                  f"not yet assessed {len(a['groups']['not_assessed'])}.")
        return {"analysis": a, "events": [event("Analyst", "analyze_class", reason)]}

    def coach_propose(state: ClassroomState) -> dict:
        proposal, source = coach.propose(state["topic"], state["analysis"], state["students"], llm)
        events = [event("Coach", f"propose ({source})", f"{r['group_label']}: {r['headline']}")
                  for r in proposal["recommendations"]]
        return {"proposal": proposal, "recommendations": proposal["recommendations"], "events": events}

    def analyst_critique(state: ClassroomState) -> dict:
        critiques, source = analyst.critique(state["analysis"], state["proposal"], llm)
        events = [event("Analyst", f"{c['verdict']} ({source})", c["reason"]) for c in critiques]
        return {"critiques": critiques, "events": events}

    def route_after_critique(state: ClassroomState) -> str:
        return "coach_revise" if any(c["verdict"] == "revise" for c in state["critiques"]) else "curate"

    def coach_revise(state: ClassroomState) -> dict:
        revised, source = coach.revise(state["topic"], state["analysis"], state["students"], state["proposal"],
                                       state["critiques"], llm)
        events = [event("Coach", f"revise ({source})", f"{r['group_label']}: {r['headline']}")
                  for r in revised["recommendations"]]
        return {"proposal": revised, "recommendations": revised["recommendations"], "events": events}

    def curate(state: ClassroomState) -> dict:
        topic: Topic = state["topic"]
        students = state["students"]
        with_gaps = sorted((s for s in students.values() if s.top_gap()), key=lambda s: s.mastery[s.top_gap()[0]])
        lessons, messages, events = [], [], []
        for s in with_gaps[:max_lessons]:
            concept, tag = s.top_gap()
            language = state.get("lesson_language") or s.language
            body, source = curator.lesson(topic, concept, tag, language, llm, cache)
            retry = curator.retry_items(topic, s, concept, tag)
            lessons.append({"student_id": s.id, "nickname": s.nickname, "concept_id": concept, "tag": tag,
                            "language": language, **body, "retry": retry, "source": source})
            reason = f"{s.nickname}: {concept} / {tag} in {language}; {len(retry)} retry items from the bank"
            events.append(event("Curator", f"lesson ({source})", reason, s.id))
            message, msource = coach.parent_message(topic, s, concept, tag, llm)
            messages.append({"student_id": s.id, **message, "source": msource})
            events.append(event("Coach", f"parent_message ({msource})", f"Drafted for {s.nickname}'s family", s.id))
        return {"lessons": lessons, "parent_messages": messages, "events": events}

    builder = StateGraph(ClassroomState)
    builder.add_node("assess_class", assess_class)
    builder.add_node("analyze", analyze)
    builder.add_node("coach_propose", coach_propose)
    builder.add_node("analyst_critique", analyst_critique)
    builder.add_node("coach_revise", coach_revise)
    builder.add_node("curate", curate)
    builder.add_edge(START, "assess_class")
    builder.add_edge("assess_class", "analyze")
    builder.add_edge("analyze", "coach_propose")
    builder.add_edge("coach_propose", "analyst_critique")
    builder.add_conditional_edges("analyst_critique", route_after_critique,
                                  {"coach_revise": "coach_revise", "curate": "curate"})
    builder.add_edge("coach_revise", "curate")
    builder.add_edge("curate", END)
    return builder.compile()


def initial_state(topic: Topic, personas: list[dict], *, questions_per_student: int = 8, seed: int = 42,
                  lesson_language: str | None = None) -> ClassroomState:
    return {"topic": topic, "personas": personas, "questions_per_student": questions_per_student,
            "seed": seed, "lesson_language": lesson_language, "events": []}
