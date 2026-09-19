"""Run the multi-agent teaching ecosystem from the command line.

    python main.py                              # simulate a class of 30 and watch the agents work
    python main.py --language kn                # write the micro-lessons in Kannada (needs GEMINI_API_KEY)
    python main.py --photo working.jpg --question Q22   # diagnose a photo of handwritten working
    python main.py --eval                       # measure the Diagnostician on the labelled set
    python main.py --eval-photos data/eval_photo   # measure photo diagnosis on your labelled photos
    python main.py --offline                    # no API key, no network: deterministic stand-in model
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path

from dotenv import load_dotenv

from teaching_ecosystem.agents import diagnostician
from teaching_ecosystem.llm import get_llm
from teaching_ecosystem.topic import DATA_DIR, load_personas, load_topic
from teaching_ecosystem.workflow import build_workflow, initial_state

WIDTH = 100


def rule(title: str = "") -> None:
    print(f"\n-- {title} " + "-" * max(0, WIDTH - len(title) - 4) if title else "-" * WIDTH)


def run_class(args) -> None:
    topic = load_topic()
    personas = load_personas()[: args.students]
    llm = get_llm(offline=args.offline)
    print(f"GuruGraph | topic: {topic.name} | students: {len(personas)} | model: {llm.name}")
    graph = build_workflow(llm)
    final = {}
    state = initial_state(topic, personas, questions_per_student=args.questions, seed=args.seed,
                          lesson_language=args.language)
    for update in graph.stream(state, stream_mode="updates"):
        for node, delta in update.items():
            rule(node)
            for e in delta.get("events", []):
                print(f"  {e['agent']:<14} {e['action']:<24} {e['reason']}")
            final.update(delta)

    a = final["analysis"]
    rule("class knowledge graph (average mastery)")
    for cid in topic.order:
        c = a["concepts"][cid]
        bar = "#" * round(c["avg"] * 30)
        top = ", ".join(f"{t} x{n}" for t, n in c["top_misconceptions"][:2]) or "-"
        print(f"  {cid} {c['name']:<34} {c['avg']:.2f} {bar:<30} {top}")

    rule("recommendations the teacher approves")
    for r in final["recommendations"]:
        print(f"  [{r['group_label']}] {r['headline']}")
        for i, step in enumerate(r["plan_5min"], 1):
            print(f"      {i}. {step}")
        print(f"      Why: {r['why']}")

    if final.get("lessons"):
        lesson = final["lessons"][0]
        rule(f"micro-lesson for {lesson['nickname']} ({lesson['concept_id']}, {lesson['tag']}, {lesson['language']})")
        print("  " + lesson["lesson_md"].replace("\n", "\n  "))
        print("  Retry items that decide whether the gap closed:")
        for item in lesson["retry"]:
            choices = f"  options: {' | '.join(item['options'])}" if item["kind"] == "mcq" else "  (typed answer)"
            print(f"    - {item['stem']}{choices}")
        msg = final["parent_messages"][0]
        rule("parent message")
        print("  " + msg["message"])


def run_photo(args) -> None:
    topic = load_topic()
    question = topic.questions[args.question]
    image = Path(args.photo).read_bytes()
    mime = mimetypes.guess_type(args.photo)[0] or "image/jpeg"
    llm = get_llm(offline=args.offline)
    result = diagnostician.diagnose_photo(topic, question, image, llm, image_mime=mime)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def run_eval(args) -> None:
    topic = load_topic()
    llm = get_llm(offline=args.offline)
    items = [json.loads(line) for line in (DATA_DIR / "eval_text.jsonl").read_text(encoding="utf-8").splitlines()]
    for use_rules in (True, False):
        correct_ok = tag_ok = wrong_items = 0
        for item in items:
            q = topic.questions[item["question_id"]]
            d = diagnostician.diagnose_text(topic, q, item["answer"], llm, use_rules=use_rules)
            correct_ok += d["correct"] == item["label_correct"]
            if not item["label_correct"]:
                wrong_items += 1
                tag_ok += d["misconception_tag"] == item["label_tag"]
        mode = "rules first, then LLM" if use_rules else f"LLM only ({llm.name})"
        print(f"{mode:<32} right/wrong accuracy {correct_ok}/{len(items)} = {correct_ok / len(items):.0%} | "
              f"misconception accuracy {tag_ok}/{wrong_items} = {tag_ok / wrong_items:.0%}")
    print("Note: the rule tables were written from this same set, so the first row shows coverage, not a fair "
          "estimate. Quote the LLM-only row as the Diagnostician's accuracy.")
    if llm.name == "offline":
        print("Offline mode: the LLM-only row measures the stand-in model, not a real LLM. Set GEMINI_API_KEY.")


def run_eval_photos(args) -> None:
    """Score photo diagnosis on a folder of labelled photos (see data/eval_photo/README.md)."""
    topic = load_topic()
    llm = get_llm(offline=args.offline)
    folder = Path(args.eval_photos)
    labels = [json.loads(line) for line in (folder / "labels.jsonl").read_text(encoding="utf-8").splitlines() if line]
    right = tag_ok = step_ok = wrong_items = unreadable = 0
    for item in labels:
        path = folder / item["file"]
        result = diagnostician.diagnose_photo(topic, topic.questions[item["question_id"]], path.read_bytes(), llm,
                                              image_mime=mimetypes.guess_type(path.name)[0] or "image/jpeg")
        if result.get("needs_typed_answer"):
            unreadable += 1
            print(f"  {item['file']:<24} unreadable: {result['reason'][:80]}")
            continue
        right += result["correct"] == item["label_correct"]
        if not item["label_correct"]:
            wrong_items += 1
            tag_ok += result["misconception_tag"] == item["label_tag"]
            step_ok += result["error_step"] == item["label_error_step"]
        print(f"  {item['file']:<24} correct={result['correct']!s:<5} tag={result['misconception_tag']} "
              f"step={result['error_step']} confidence={result['confidence']}")
    n = len(labels)
    print(f"Photos: right/wrong {right}/{n} | misconception {tag_ok}/{wrong_items} | wrong step {step_ok}/{wrong_items} "
          f"| unreadable {unreadable}")


def main(argv=None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--students", type=int, default=30)
    parser.add_argument("--questions", type=int, default=8, help="questions per simulated student")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--language", choices=["en", "hi", "kn"], help="lesson language (default: each student's)")
    parser.add_argument("--photo", help="path to a photo of handwritten working")
    parser.add_argument("--question", default="Q22", help="question id for --photo")
    parser.add_argument("--eval", action="store_true", help="evaluate the Diagnostician on typed answers")
    parser.add_argument("--eval-photos", metavar="FOLDER", help="evaluate photo diagnosis on labelled photos")
    parser.add_argument("--offline", action="store_true", help="use the deterministic stand-in model")
    args = parser.parse_args(argv)
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    if args.photo:
        run_photo(args)
    elif args.eval_photos:
        run_eval_photos(args)
    elif args.eval:
        run_eval(args)
    else:
        run_class(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
