import os
import textwrap
import requests
from openai import OpenAI

PROBLEM_MAP_URL = "https://raw.githubusercontent.com/onestardao/WFGY/main/ProblemMap/README.md"
TXTOS_URL = "https://raw.githubusercontent.com/onestardao/WFGY/main/OS/TXTOS.txt"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def fetch_text(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def build_system_prompt(problem_map: str, txtos: str) -> str:
    prompt = f"""
    You are an LLM debugger that follows the WFGY 16 Problem Map.

    Goal:
    Given a description of a bug or failure in an LLM or RAG pipeline, you map it
    to the closest Problem Map number (No.1–No.16), then describe:

    - the primary Problem Map number (and at most one secondary candidate)
    - why this failure matches that number, in plain language
    - which WFGY document to read first, and what minimal patch to try

    You have two reference documents inlined below.
    They are long. Skim for structure and names, not every sentence.

    [WFGY Problem Map 1.0 README]
    {problem_map}

    [TXT OS semantic operating system]
    {txtos}

    Answer format (markdown):

    1. **Primary Problem Map number**: No.X
    2. **Optional secondary**: No.Y (if clearly relevant, otherwise say "none")
    3. **Reasoning**: 2–4 sentences, plain language, no equations.
    4. **Next steps**: which WFGY page to open and the first concrete fix to try.

    Always stay within the 16 Problem Map numbers. Do not invent new numbers.
    """
    return textwrap.dedent(prompt).strip()


def run_session() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Please set OPENAI_API_KEY in your environment.")

    print("Downloading WFGY references...")
    problem_map = fetch_text(PROBLEM_MAP_URL)
    txtos = fetch_text(TXTOS_URL)

    system_prompt = build_system_prompt(problem_map, txtos)
    client = OpenAI(api_key=api_key)

    print("\nWFGY 16 Problem Map LLM Debugger")
    print("Describe your bug or failure. Type a few lines, then press Enter on an empty line to send.")
    print("Type 'q' on a new line (before any text) to quit.\n")

    while True:
        print("Bug description:")
        lines = []
        while True:
            line = input()
            if line.strip().lower() == "q" and not lines:
                print("Bye. Map once, then fix once.")
                return
            if line == "":
                break
            lines.append(line)

        if not lines:
            continue

        user_prompt = "\n".join(lines)

        print("\nThinking with WFGY...")
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content or ""
        print("\n" + content + "\n")
        print("-" * 72 + "\n")


if __name__ == "__main__":
    run_session()
