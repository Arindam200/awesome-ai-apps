"""FAQ lookup using simple keyword matching."""

import json
from pathlib import Path

_FAQ_FILE = Path(__file__).resolve().parent.parent / "data" / "faq.json"


def lookup_faq(query: str) -> dict[str, str]:
    faq = json.loads(_FAQ_FILE.read_text())
    q = query.lower()
    best_topic, best_score = None, 0
    for topic, entry in faq.items():
        score = sum(1 for kw in entry["keywords"] if kw in q)
        if score > best_score:
            best_topic, best_score = topic, score

    if not best_topic:
        return {
            "found": False,
            "answer": "I do not have that information on hand. Would you like me to escalate to a supervisor?",
        }
    return {"found": True, "topic": best_topic, "answer": faq[best_topic]["answer"]}
