"""Curator: writes a micro-lesson and practice items for one (concept, misconception, language).

Lessons are cached per (concept, misconception, language), which is also how the production app keeps
LLM cost under a rupee per student per month. Retry items that decide whether a gap closed always come
from the verified question bank, never from the LLM, so a wrong answer key can never close a gap.
"""

from __future__ import annotations

from .. import prompts, schemas
from ..llm import LLM, LLMError
from ..prompts import LANGUAGES
from ..state import StudentRecord
from ..topic import Topic

SCRIPT_RANGES = {"kn": (0x0C80, 0x0CFF), "hi": (0x0900, 0x097F)}
MIN_SCRIPT_SHARE = 0.5


def script_share(text: str, language: str) -> float:
    """Share of letters written in the target script (1.0 for English)."""
    if language not in SCRIPT_RANGES:
        return 1.0
    lo, hi = SCRIPT_RANGES[language]
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for ch in letters if lo <= ord(ch) <= hi) / len(letters)


def retry_items(topic: Topic, student: StudentRecord | None, concept_id: str, tag: str, k: int = 2) -> list[dict]:
    """Pick k verified bank items on the concept: unseen MCQs that carry a distractor for the same
    misconception first, then unseen typed items, then items the student has already seen."""
    seen = set(student.seen) if student else set()
    items = topic.questions_for(concept_id, ("mcq", "text"))

    def rank(q):
        targets_tag = q["kind"] == "mcq" and any(o.get("tag") == tag for o in q["options"])
        return (q["id"] in seen, q["kind"] != "mcq", not targets_tag)

    picked = []
    for q in sorted(items, key=rank)[:k]:
        if q["kind"] == "mcq":
            picked.append({"question_id": q["id"], "kind": "mcq", "stem": q["stem"],
                           "options": [o["text"] for o in q["options"]],
                           "answer_index": next(i for i, o in enumerate(q["options"]) if o.get("correct"))})
        else:
            picked.append({"question_id": q["id"], "kind": "text", "stem": q["stem"], "answer": q["answer"]})
    return picked


def _practice_seed(topic: Topic, concept_id: str) -> list[dict]:
    typed = [{"stem": q["stem"], "answer": q["answer"]} for q in topic.questions_for(concept_id, ("text",))]
    mcq = [{"stem": q["stem"], "answer": next(o["text"] for o in q["options"] if o.get("correct"))}
           for q in topic.questions_for(concept_id, ("mcq",))]
    return (typed + mcq)[:3]


def lesson(topic: Topic, concept_id: str, tag: str, language: str, llm: LLM,
           cache: dict | None = None) -> tuple[dict, str]:
    key = f"{concept_id}|{tag}|{language}"
    if cache is not None and key in cache:
        return cache[key], "cache"
    method_q = next(iter(topic.questions_for(concept_id, ("text", "photo"))), None)
    method = f"{method_q['stem']} {method_q['method']}" if method_q else topic.concept_name(concept_id)
    practice_seed = _practice_seed(topic, concept_id)
    ctx = {"language": language, "definition": topic.definition(tag), "method": method,
           "practice_seed": practice_seed, "concept": topic.concept_name(concept_id)}
    prompt = (f"Target language: {LANGUAGES.get(language, 'English')}\nConcept: {topic.concept_name(concept_id)}\n"
              f"Misconception: {tag}: {topic.definition(tag)}\nCorrect worked method: {method}")
    source = "llm"
    try:
        out = llm.generate(system=prompts.CURATOR, prompt=prompt, schema=schemas.Lesson, context=ctx)
        if language != "en" and llm.name != "offline" and script_share(out.lesson_md, language) < MIN_SCRIPT_SHARE:
            out = llm.generate(system=prompts.CURATOR, prompt=prompt + "\nWrite the lesson in the target script only.",
                               schema=schemas.Lesson, context=ctx)
        result = out.model_dump()
        if llm.name == "offline":
            source = "offline"
    except LLMError:
        result = {"language": "en", "lesson_md": f"Watch out: {topic.definition(tag)}\n\nDo it this way: {method}",
                  "practice": practice_seed[:3]}
        source = "template"
    result["script_share"] = round(script_share(result["lesson_md"], language), 2)
    if cache is not None and source in ("llm", "offline"):
        cache[key] = result
    return result, source
