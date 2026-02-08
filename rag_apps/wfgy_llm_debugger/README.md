# WFGY 16 Problem Map LLM Debugger

A Nebius-compatible notebook and minimal CLI that turns messy LLM and RAG bugs into **one of 16 reproducible failure modes**, each with a documented fix in the WFGY Problem Map.

Instead of guessing why your pipeline broke again, you:

1. paste the bug or trace  
2. get back the closest **Problem Map number (No.1–No.16)**  
3. follow the linked fix in the WFGY repo  

Everything runs as plain text prompts. No SDKs, no provider lock in.

---

## What this app is

This app is a thin wrapper around two public assets from the WFGY project:

- `TXTOS.txt` – a text based “reasoning OS” prompt that gives the model a stable way to analyse problems  
- `ProblemMap/README.md` – a 16 mode catalog of common AI failures with concrete fixes  

By loading both into your model (on Nebius, Colab, or any Jupyter environment), the debugger can:

- read your bug description, logs, or screenshots  
- classify it into one primary Problem Map number (and optionally a secondary candidate)  
- explain why this number fits  
- suggest a minimal fix and point you to the exact document in the WFGY repo  

Think of it as a **semantic firewall debugger** that sits in front of any LLM pipeline.

---

## The 16 Problem Map overview

The full map lives in the main WFGY repo:

- [WFGY Problem Map 1.0 – main page](https://github.com/onestardao/WFGY/tree/main/ProblemMap#readme)

This app focuses on mapping real world bugs into the following 16 classes:

| No. | Problem domain | What breaks in practice | Doc |
|-----|----------------|-------------------------|-----|
| 1   | Hallucination and chunk drift | Retrieval returns wrong or irrelevant content | [hallucination](https://github.com/onestardao/WFGY/blob/main/ProblemMap/hallucination.md) |
| 2   | Interpretation collapse | Chunk is correct, reasoning is wrong | [retrieval collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/retrieval-collapse.md) |
| 3   | Long reasoning chains | Multi step tasks drift and never converge | [context drift](https://github.com/onestardao/WFGY/blob/main/ProblemMap/context-drift.md) |
| 4   | Bluffing and overconfidence | Confident answers with no real support | [bluffing](https://github.com/onestardao/WFGY/blob/main/ProblemMap/bluffing.md) |
| 5   | Semantic ≠ embedding | Cosine similarity does not match true meaning | [embedding vs semantic](https://github.com/onestardao/WFGY/blob/main/ProblemMap/embedding-vs-semantic.md) |
| 6   | Logic collapse and recovery | Chains hit dead ends and need controlled reset | [logic collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/logic-collapse.md) |
| 7   | Memory breaks across sessions | Lost threads and no continuity | [memory coherence](https://github.com/onestardao/WFGY/blob/main/ProblemMap/memory-coherence.md) |
| 8   | Debugging as a black box | No visibility into retrieval and failure paths | [retrieval traceability](https://github.com/onestardao/WFGY/blob/main/ProblemMap/retrieval-traceability.md) 
| 9   | Entropy collapse | Attention melts into incoherent output | [entropy collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/entropy-collapse.md) |
| 10  | Creative freeze | Flat and literal outputs when you needed structure and creativity | [creative freeze](https://github.com/onestardao/WFGY/blob/main/ProblemMap/creative-freeze.md) |
| 11  | Symbolic collapse | Abstract or logical prompts stop working | [symbolic collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/symbolic-collapse.md) |
| 12  | Philosophical recursion | Self reference loops and paradox traps | [philosophical recursion](https://github.com/onestardao/WFGY/blob/main/ProblemMap/philosophical-recursion.md) |
| 13  | Multi agent chaos | Agents overwrite or misalign each other | [multi agent problems](https://github.com/onestardao/WFGY/blob/main/ProblemMap/Multi-Agent_Problems.md) |
| 14  | Bootstrap ordering | Services start before dependencies and quietly fail | [bootstrap ordering](https://github.com/onestardao/WFGY/blob/main/ProblemMap/bootstrap-ordering.md) |
| 15  | Deployment deadlock | Circular waits in infra and pipelines | [deployment deadlock](https://github.com/onestardao/WFGY/blob/main/ProblemMap/deployment-deadlock.md) |
| 16  | Pre deploy collapse | Version skew or missing secrets on first call | [pre deploy collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/predeploy-collapse.md) |

Once a bug is mapped to a number, you can apply the fix and expect it not to silently reappear in the same way.

---

## Running on Nebius (or any Jupyter environment)

This project is designed to run on Nebius-hosted notebooks but also works on Colab, local Jupyter, or any environment where you can make OpenAI-compatible API calls.

High-level flow inside the notebook:

1. **Install dependencies**

   ```bash
   pip install openai requests python-dotenv

2. **Set your model endpoint**

   You can use:

   * a Nebius endpoint that exposes an OpenAI-compatible API, or
   * the standard OpenAI endpoint, or
   * any other provider that uses the same API style

   Export the relevant environment variables, for example:

   ```bash
   export OPENAI_API_KEY="your_api_key"
   export OPENAI_BASE_URL="https://your-nebius-endpoint/v1"    # optional, omit for default OpenAI
   export OPENAI_MODEL="gpt-4o-mini"
   ```

3. **Load TXT OS and the Problem Map**

   The notebook downloads two text files from the WFGY repo:

   * `TXTOS.txt` from `OS/TXTOS.txt`
   * `ProblemMap/README.md`

   Both are concatenated into a single system prompt so the model has:

   * the reasoning OS (how to think), and
   * the 16 problem catalog (what to map to).

4. **Paste your bug**

   You provide:

   * a short description of the issue
   * the prompt and answer, or RAG traces, or logs

   The more concrete the example, the easier it is to classify.

5. **Run the debugger cell**

   The model responds with:

   * one primary Problem Map number `No.X`
   * an optional secondary candidate if there is a close tie
   * a short explanation in plain language
   * which WFGY document to read next and what first patch to try

You can treat this as a diagnostic layer in front of any LLM app, without changing your existing infra.

---

## Minimal CLI demo (`main.py`)

For people who prefer a terminal flow, this repository includes a small CLI script.
It uses the same logic as the notebook but runs entirely in the console.

Place the following file at `rag_apps/wfgy_llm_debugger/main.py`:

```python
import os
import textwrap
import requests
from openai import OpenAI


PROBLEM_MAP_URL = "https://raw.githubusercontent.com/onestardao/WFGY/main/ProblemMap/README.md"
TXTOS_URL = "https://raw.githubusercontent.com/onestardao/WFGY/main/OS/TXTOS.txt"


def fetch_text(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def build_system_prompt(problem_map: str, txtos: str) -> str:
    header = """
You are an LLM debugger that follows the WFGY 16 Problem Map.

Goal:
Given a description of a bug or failure in an LLM or RAG pipeline, you map it to the closest Problem Map number (No.1–No.16), explain why, and propose a minimal fix.

Rules:
- Always return one primary Problem Map number and at most one secondary candidate.
- Explain your reasoning in plain language.
- When useful, mention the original document name inside the WFGY repo so users can look it up.
"""
    return (
        textwrap.dedent(header)
        + "\n\n=== TXT OS excerpt ===\n"
        + txtos[:6000]
        + "\n\n=== Problem Map excerpt ===\n"
        + problem_map[:6000]
    )


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        raise RuntimeError("Please set OPENAI_API_KEY in your environment.")

    print("Downloading WFGY assets...")
    problem_map_text = fetch_text(PROBLEM_MAP_URL)
    txtos_text = fetch_text(TXTOS_URL)

    system_prompt = build_system_prompt(problem_map_text, txtos_text)

    client = OpenAI(api_key=api_key, base_url=base_url)

    print()
    print("Paste a short description of your LLM or RAG bug.")
    print("Include the prompt, answer, and any relevant logs.")
    print("Finish with an empty line and press Enter.")
    print()

    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)

    user_bug = "\n".join(lines)

    if not user_bug.strip():
        print("No input provided. Exiting.")
        return

    print()
    print("Asking the WFGY debugger...")
    print()

    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_bug},
        ],
        temperature=0.2,
    )

    answer = completion.choices[0].message.content
    print(answer)


if __name__ == "__main__":
    main()
```

### How to run the CLI demo

1. Install the Python dependencies:

   ```bash
   pip install openai requests python-dotenv
   ```

2. Set environment variables for your provider:

   ```bash
   export OPENAI_API_KEY="your_api_key"
   export OPENAI_BASE_URL="https://your-nebius-endpoint/v1"    # optional
   export OPENAI_MODEL="gpt-4o-mini"
   ```

3. Run the script from the `rag_apps/wfgy_llm_debugger` directory:

   ```bash
   python main.py
   ```

4. Paste your bug description, prompt, answer, and any logs.
   End the input with an empty line and press Enter.

The tool prints:

* the suggested Problem Map number
* a short diagnosis in plain language
* which WFGY document to open and what fix to try first

---

## Optional helper: Dr WFGY ER

If you prefer a fully prepared chat window instead of running code, there is also an optional helper:

* **Dr WFGY in ChatGPT Room** – a pre-configured share link that behaves like an ER doctor for broken pipelines.

You can paste the same bugs or even screenshots of WFGY pages there.
However, this repository focuses on the **code and notebook version**, which you can fork, extend, and run on Nebius or any other OpenAI-compatible stack.

