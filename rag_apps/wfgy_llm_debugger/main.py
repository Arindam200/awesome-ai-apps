"""
WFGY 16 Problem Map LLM Debugger
Simple terminal helper for mapping real bugs to the 16 core failure modes.

This script does not call any API by itself.
It is meant to be run in any plain Python environment
(local machine, Nebius notebook, or other cloud runtime).
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Problem:
    pid: int
    name: str
    short: str
    layer: str
    doc_url: str


PROBLEMS: List[Problem] = [
    Problem(
        pid=1,
        name="Hallucination & chunk drift",
        short="Retrieval surfaces wrong or off-topic chunks for the question.",
        layer="[IN] {OBS}",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/hallucination.md",
    ),
    Problem(
        pid=2,
        name="Interpretation collapse",
        short="Chunks are fine, but the model misinterprets them or answers the wrong question.",
        layer="[RE]",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/retrieval-collapse.md",
    ),
    Problem(
        pid=3,
        name="Long reasoning chains drift",
        short="Multi-step answers slowly wander away from the original task.",
        layer="[RE] {OBS}",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/context-drift.md",
    ),
    Problem(
        pid=4,
        name="Bluffing / overconfidence",
        short="The model sounds confident but the cited facts are not grounded.",
        layer="[RE]",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/bluffing.md",
    ),
    Problem(
        pid=5,
        name="Semantic ≠ embedding",
        short="Cosine similarity in the vector store does not match real semantic similarity.",
        layer="[IN] {OBS}",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/embedding-vs-semantic.md",
    ),
    Problem(
        pid=6,
        name="Logic collapse & recovery",
        short="Reasoning hits a dead end and needs a controlled reset, not random retries.",
        layer="[RE] {OBS}",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/logic-collapse.md",
    ),
    Problem(
        pid=7,
        name="Memory breaks across sessions",
        short="Conversations or agents forget previous agreements or context.",
        layer="[ST]",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/memory-coherence.md",
    ),
    Problem(
        pid=8,
        name="Debugging is a black box",
        short="No clear trace of how retrieval, prompts, and tools produced this answer.",
        layer="[IN] {OBS}",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/retrieval-traceability.md",
    ),
    Problem(
        pid=9,
        name="Entropy collapse",
        short="Attention melts and the answer turns incoherent or repetitive.",
        layer="[ST]",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/entropy-collapse.md",
    ),
    Problem(
        pid=10,
        name="Creative freeze",
        short="Outputs are flat or literal even when the prompt asks for exploration.",
        layer="[RE]",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/creative-freeze.md",
    ),
    Problem(
        pid=11,
        name="Symbolic collapse",
        short="Symbolic or abstract prompts break, proofs fall apart, math feels wrong.",
        layer="[RE]",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/symbolic-collapse.md",
    ),
    Problem(
        pid=12,
        name="Philosophical recursion",
        short="Self-reference loops, paradox traps, or endless meta-questions.",
        layer="[RE]",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/philosophical-recursion.md",
    ),
    Problem(
        pid=13,
        name="Multi-agent chaos",
        short="Multiple agents overwrite each other or drift into conflicting roles.",
        layer="[ST] {OBS}",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/Multi-Agent_Problems.md",
    ),
    Problem(
        pid=14,
        name="Bootstrap ordering",
        short="Services start in the wrong order, so early calls fail or hit empty stores.",
        layer="[OP]",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/bootstrap-ordering.md",
    ),
    Problem(
        pid=15,
        name="Deployment deadlock",
        short="Circular waits or blocked pipelines during deploy or rollback.",
        layer="[OP]",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/deployment-deadlock.md",
    ),
    Problem(
        pid=16,
        name="Pre-deploy collapse",
        short="First production calls hit missing secrets, wrong versions, or cold indexes.",
        layer="[OP] {OBS}",
        doc_url="https://github.com/onestardao/WFGY/blob/main/ProblemMap/predeploy-collapse.md",
    ),
]


def print_intro() -> None:
    print("=" * 72)
    print("WFGY 16 Problem Map LLM Debugger")
    print("=" * 72)
    print(
        "Use this helper when you have a stubborn LLM or RAG bug.\n"
        "Describe your symptom, pick the closest Problem Map number,\n"
        "then open the linked page in a browser to apply the full fix.\n"
    )


def print_all_problems() -> None:
    print("Available failure modes:\n")
    for p in PROBLEMS:
        print(f"  {p.pid:>2}. {p.name}  {p.layer}")
        print(f"      {p.short}")
    print()


def find_problem(pid: int) -> Optional[Problem]:
    for p in PROBLEMS:
        if p.pid == pid:
            return p
    return None


def interactive_loop() -> None:
    print_intro()
    print_all_problems()

    while True:
        raw = input(
            "Type a Problem Map number (1-16) to see details, "
            "'list' to show all, or 'q' to quit: "
        ).strip()

        if raw.lower() in {"q", "quit", "exit"}:
            print("Good luck with your debugging. Remember to map once, fix once.")
            return

        if raw.lower() in {"l", "list"}:
            print_all_problems()
            continue

        try:
            pid = int(raw)
        except ValueError:
            print("Please type a number between 1 and 16, 'list', or 'q'.")
            continue

        problem = find_problem(pid)
        if not problem:
            print("Unknown problem id, please choose between 1 and 16.")
            continue

        print()
        print(f"[No.{problem.pid}] {problem.name}  {problem.layer}")
        print("-" * 72)
        print(problem.short)
        print()
        print("Open this page in your browser for the full WFGY fix:")
        print(f"  {problem.doc_url}")
        print()

        follow_up = input(
            "Press Enter to continue, or type 'q' to quit: "
        ).strip().lower()
        if follow_up in {"q", "quit", "exit"}:
            print("Session ended. Map this once, then apply the permanent fix.")
            return


if __name__ == "__main__":
    interactive_loop()
