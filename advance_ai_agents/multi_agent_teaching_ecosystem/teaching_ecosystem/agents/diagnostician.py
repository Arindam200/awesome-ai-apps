"""Diagnostician: decides whether an answer is right and, if not, which misconception it shows.

Rules first, LLM for the long tail:
- MCQ: every distractor in the bank carries a misconception tag, so no LLM is needed.
- Typed answers: exact fraction arithmetic decides correctness; known wrong answers map to tags;
  only an unfamiliar wrong answer goes to the LLM.
- Photos of handwritten working: the LLM transcribes the steps and points at the first wrong one.
"""

from __future__ import annotations

from .. import prompts, schemas
from ..llm import LLM, LLMError, source_of
from ..topic import Topic, is_simplest, normalize, parse_answer

MIN_CONFIDENCE = 0.5


def _tag_list(topic: Topic) -> str:
    return "\n".join(f"- {tag}: {definition}" for tag, definition in topic.taxonomy.items())


def _checked_tag(topic: Topic, tag: str, confidence: float) -> tuple[str, float]:
    if tag not in topic.taxonomy or confidence < MIN_CONFIDENCE:
        return "unclassified", min(confidence, 0.49)
    return tag, confidence


def diagnose_mcq(question: dict, answer: str) -> dict:
    chosen = next((o for o in question["options"] if normalize(o["text"]) == normalize(answer)), None)
    if chosen is None:
        return {"correct": False, "misconception_tag": "unclassified", "error_step": None,
                "confidence": 0.0, "feedback": "That option is not on this question.", "source": "key"}
    if chosen.get("correct"):
        return {"correct": True, "misconception_tag": None, "error_step": None,
                "confidence": 1.0, "feedback": "Correct.", "source": "key"}
    return {"correct": False, "misconception_tag": chosen["tag"], "error_step": None,
            "confidence": 1.0, "feedback": "", "source": "key"}


def answer_key(question: dict) -> str:
    """The correct answer as text, for typed and multiple-choice questions alike."""
    if question["kind"] == "mcq":
        return next(o["text"] for o in question["options"] if o.get("correct"))
    return question["answer"]


def known_wrong_answers(question: dict) -> dict[str, str]:
    """Typed wrong answers we already recognise, mapped to their misconception tag."""
    if question["kind"] == "mcq":
        return {normalize(o["text"]): o["tag"] for o in question["options"] if not o.get("correct")}
    return {normalize(k): v for k, v in question.get("wrong_answers", {}).items()}


def diagnose_text(topic: Topic, question: dict, answer: str, llm: LLM | None, use_rules: bool = True) -> dict:
    """Diagnose a typed answer. Works for typed questions and for MCQ stems answered by typing."""
    key = answer_key(question)
    value, expected = parse_answer(answer), parse_answer(key)
    if use_rules:
        same_value = value is not None and value == expected
        if (same_value or normalize(answer) == normalize(key)) and (not question.get("simplest") or is_simplest(answer)):
            return {"correct": True, "misconception_tag": None, "error_step": None,
                    "confidence": 1.0, "feedback": "Correct.", "source": "rule"}
        known = known_wrong_answers(question)
        if normalize(answer) in known:
            return {"correct": False, "misconception_tag": known[normalize(answer)], "error_step": None,
                    "confidence": 0.95, "feedback": "", "source": "rule"}
    if llm is None:
        return {"correct": False, "misconception_tag": "unclassified", "error_step": None,
                "confidence": 0.0, "feedback": "", "source": "none"}
    prompt = (f"Question: {question['stem']}\nCorrect answer: {key}\n"
              f"Correct method: {question.get('method', 'not given')}\n"
              f"Simplest form required: {'yes' if question.get('simplest') else 'no'}\n"
              f"Allowed tags:\n{_tag_list(topic)}\n\nStudent's typed answer: {answer}")
    try:
        out = llm.generate(system=prompts.DIAGNOSE_TEXT, prompt=prompt, schema=schemas.TextDiagnosis,
                           context={"question": question, "answer": answer})
    except LLMError:
        return {"correct": False, "misconception_tag": "unclassified", "error_step": None,
                "confidence": 0.0, "feedback": "", "source": "fallback"}
    tag, confidence = (None, out.confidence) if out.correct else _checked_tag(topic, out.misconception_tag, out.confidence)
    return {"correct": out.correct, "misconception_tag": tag, "error_step": out.error_step,
            "confidence": round(confidence, 2), "feedback": out.feedback_student, "source": source_of(llm)}


def diagnose_photo(topic: Topic, question: dict, image: bytes, llm: LLM, image_mime: str = "image/jpeg") -> dict:
    """Returns the diagnosis, or {"needs_typed_answer": True, ...} when the image cannot be read."""
    prompt = (f"Question: {question['stem']}\nCorrect answer: {question['answer']}\n"
              f"Correct method: {question['method']}\nAllowed tags:\n{_tag_list(topic)}\n\n"
              "The photograph of the student's working is attached.")
    try:
        out = llm.generate(system=prompts.DIAGNOSE_PHOTO, prompt=prompt, schema=schemas.PhotoDiagnosis,
                           context={"question": question}, image=image, image_mime=image_mime)
    except LLMError as exc:
        return {"needs_typed_answer": True, "reason": str(exc), "source": "vision"}
    tag, confidence = (None, out.confidence) if out.correct else _checked_tag(topic, out.misconception_tag, out.confidence)
    return {"correct": out.correct, "misconception_tag": tag, "error_step": out.error_step, "steps": out.steps,
            "final_answer_read": out.final_answer_read, "confidence": round(confidence, 2),
            "feedback": out.feedback_student, "source": "vision"}


def diagnose(topic: Topic, question: dict, answer: str, llm: LLM | None) -> dict:
    if question["kind"] == "mcq":
        return diagnose_mcq(question, answer)
    if question["kind"] == "text":
        return diagnose_text(topic, question, answer, llm)
    raise ValueError("Photo questions need diagnose_photo with the image bytes.")


def explain(topic: Topic, diagnosis: dict) -> str:
    """One-line reason for the activity feed."""
    if diagnosis.get("correct"):
        return f"Correct ({diagnosis['source']})."
    tag = diagnosis.get("misconception_tag") or "unclassified"
    return f"{tag} ({diagnosis['source']}, confidence {diagnosis.get('confidence', 0):.2f})"
