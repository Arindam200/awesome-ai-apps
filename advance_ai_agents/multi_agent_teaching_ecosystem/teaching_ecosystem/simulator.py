"""Synthetic students for demos and tests. Answers come only from the verified bank, so a simulated
class never calls the LLM and always produces the same results for the same seed."""

from __future__ import annotations

import random

from .topic import Topic


def simulate_answer(topic: Topic, persona: dict, question: dict, rng: random.Random) -> str:
    concept = question["concept_id"]
    if rng.random() < persona["p_correct"][concept]:
        if question["kind"] == "mcq":
            return next(o["text"] for o in question["options"] if o.get("correct"))
        return question["answer"]
    preferred = persona["preferred_tags"].get(concept)
    if question["kind"] == "mcq":
        wrong = [o for o in question["options"] if not o.get("correct")]
        match = [o for o in wrong if o["tag"] == preferred]
        return (match or wrong)[0 if match else rng.randrange(len(wrong))]["text"]
    wrong_answers = question.get("wrong_answers", {})
    match = [a for a, tag in wrong_answers.items() if tag == preferred]
    if match:
        return match[0]
    if wrong_answers:
        return rng.choice(sorted(wrong_answers))
    return "I am not sure"
