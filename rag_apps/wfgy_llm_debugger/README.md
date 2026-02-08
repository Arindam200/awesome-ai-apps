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
- `ProblemMap/README.md` – a 16-mode catalog of common AI failures with concrete fixes  

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

This app focuses on mapping real-world bugs into the following 16 classes:

| No. | Problem domain | What breaks in practice | Doc |
|-----|----------------|-------------------------|-----|
| 1   | Hallucination and chunk drift | Retrieval returns wrong or irrelevant content | [hallucination](https://github.com/onestardao/WFGY/blob/main/ProblemMap/hallucination.md) |
| 2   | Interpretation collapse | Chunk is correct, reasoning is wrong | [retrieval collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/retrieval-collapse.md) |
| 3   | Long reasoning chains | Multi-step tasks drift and never converge | [context drift](https://github.com/onestardao/WFGY/blob/main/ProblemMap/context-drift.md) |
| 4   | Bluffing and overconfidence | Confident answers with no real support | [bluffing](https://github.com/onestardao/WFGY/blob/main/ProblemMap/bluffing.md) |
| 5   | Semantic ≠ embedding | Cosine similarity does not match true meaning | [embedding vs semantic](https://github.com/onestardao/WFGY/blob/main/ProblemMap/embedding-vs-semantic.md) |
| 6   | Logic collapse and recovery | Chains hit dead ends and need controlled reset | [logic collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/logic-collapse.md) |
| 7   | Memory breaks across sessions | Lost threads and no continuity | [memory coherence](https://github.com/onestardao/WFGY/blob/main/ProblemMap/memory-coherence.md) |
| 8   | Debugging as a black box | No visibility into retrieval and failure paths | [retrieval traceability](https://github.com/onestardao/WFGY/blob/main/ProblemMap/retrieval-traceability.md) |
| 9   | Entropy collapse | Attention melts into incoherent output | [entropy collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/entropy-collapse.md) |
| 10  | Creative freeze | Flat and literal outputs when you needed structure and creativity | [creative freeze](https://github.com/onestardao/WFGY/blob/main/ProblemMap/creative-freeze.md) |
| 11  | Symbolic collapse | Abstract or logical prompts stop working | [symbolic collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/symbolic-collapse.md) |
| 12  | Philosophical recursion | Self-reference loops and paradox traps | [philosophical recursion](https://github.com/onestardao/WFGY/blob/main/ProblemMap/philosophical-recursion.md) |
| 13  | Multi-agent chaos | Agents overwrite or misalign each other | [multi agent problems](https://github.com/onestardao/WFGY/blob/main/ProblemMap/Multi-Agent_Problems.md) |
| 14  | Bootstrap ordering | Services start before dependencies and quietly fail | [bootstrap ordering](https://github.com/onestardao/WFGY/blob/main/ProblemMap/bootstrap-ordering.md) |
| 15  | Deployment deadlock | Circular waits in infra and pipelines | [deployment deadlock](https://github.com/onestardao/WFGY/blob/main/ProblemMap/deployment-deadlock.md) |
| 16  | Pre-deploy collapse | Version skew or missing secrets on first call | [pre-deploy collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/predeploy-collapse.md) |

Once a bug is mapped to a number, you can apply the fix and expect it not to silently reappear in the same way.

---

## Running on Nebius (or any Jupyter environment)

This project is designed to run on Nebius-hosted notebooks but also works on Colab, local Jupyter, or any environment where you can make OpenAI-compatible API calls.

High-level flow inside the notebook:

1. **Install dependencies**

   ```bash
   pip install openai requests

2. **Paste the single-cell debugger script**

   Create a new notebook cell and paste the full script from this repo
   (or save it as `main.py` and call it with `!python main.py` inside the notebook).

3. **Run the cell**

   When you run the cell, the debugger will:

   * ask for your API key (via a secure prompt)
   * ask for an optional custom base URL (you can paste your Nebius endpoint here)
   * ask for a model name (press Enter to use `gpt-4o` by default)

   After setup, it downloads:

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

5. **Submit and read the diagnosis**

   The cell will guide you line by line:

   * type multiple lines
   * press Enter on an empty line to finish
   * the debugger returns one primary `No.X`, an optional secondary `No.Y`,
     a short explanation, and which WFGY document to open for the first fix.

You can treat this as a diagnostic layer in front of any LLM app, without changing your existing infra.

---

## Minimal CLI demo (`main.py`)

For people who prefer a terminal flow, this repository includes a small CLI script.
It uses the same logic as the notebook and can also be dropped into a single Colab cell.

Place the following file at `rag_apps/wfgy_llm_debugger/main.py`:

```python
# WFGY 16 Problem Map LLM Debugger (Colab full demo)
# Single cell script: paste into one Colab cell and run.

from getpass import getpass
import textwrap
import requests
from openai import OpenAI

PROBLEM_MAP_URL = "https://raw.githubusercontent.com/onestardao/WFGY/main/ProblemMap/README.md"
TXTOS_URL = "https://raw.githubusercontent.com/onestardao/WFGY/main/OS/TXTOS.txt"
WFGY_PROBLEM_MAP_HOME = "https://github.com/onestardao/WFGY/tree/main/ProblemMap#readme"
WFGY_REPO = "https://github.com/onestardao/WFGY"

EXAMPLE_1 = """=== Example 1 — retrieval hallucination (No.1 style) ===

Context: I have a simple RAG chatbot that answers questions from a product FAQ.
The FAQ only covers billing rules for my SaaS product and does NOT mention anything about cryptocurrency or stock trading.

Prompt: "Can I pay my subscription with Bitcoin?"

Retrieved context (from vector store):
- "We only accept major credit cards and PayPal."
- "All payments are processed in USD."

Model answer:
"Yes, you can pay with Bitcoin. We support several cryptocurrencies through a third-party payment gateway."

Logs:
No errors. Retrieval shows the FAQ chunks above, but the model still confidently invents 'Bitcoin' support.
"""

EXAMPLE_2 = """=== Example 2 — bootstrap ordering / infra race (No.14 style) ===

Context: We have a simple RAG API with three services: api-gateway, rag-worker, and vector-db (running Qdrant).
In local docker compose everything works without problems.

Deployment: In production, we deploy these services on Kubernetes.

Symptom:
Sometimes, right after a fresh deploy, the api-gateway returns 500 errors for the first few minutes.
Logs show connection timeouts from api-gateway to vector-db.

After a while (5–10 minutes), the errors disappear and the system works normally.

We suspect some kind of startup race between api-gateway and vector-db, but we are not sure how to fix it properly.
"""

EXAMPLE_3 = """=== Example 3 — secrets / config drift around first deploy (No.16 style) ===

Context: We added a new environment variable for our RAG pipeline: SECRET_RAG_KEY.
This is required by a middleware that signs all outgoing requests to our internal search API.

Local: On local machines, developers set SECRET_RAG_KEY in their .env file and everything works.

Production:
We deployed a new version of the app, but forgot to add SECRET_RAG_KEY to the production environment.
The first requests after deploy start failing with 500 errors and 'missing secret' messages in the logs.

After we hot-patched the secret into the production config, the errors stopped.
However, this kind of 'first deploy breaks because of missing secrets / config drift' keeps happening in different forms.
We want to classify this failure mode and stop repeating the same mistake.
"""


def fetch_text(url: str) -> str:
    """Download a small text file with basic error handling."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def build_system_prompt(problem_map: str, txtos: str) -> str:
    """Build the system prompt that powers the debugger."""
    header = """
You are an LLM debugger that follows the WFGY 16 Problem Map.

Goal:
Given a description of a bug or failure in an LLM or RAG pipeline, you map it to the closest Problem Map number (No.1–No.16), explain why, and propose a minimal fix.

Rules:
- Always return exactly one primary Problem Map number (No.1–No.16).
- Optionally return one secondary candidate if it is very close.
- Explain your reasoning in plain language.
- Point the user to the right direction inside the WFGY Problem Map when possible.
- Prefer minimal structural patches over generic high level advice.

About the three built in examples:
- Example 1 is a clean retrieval hallucination pattern. It should map primarily to No.1.
- Example 2 is a bootstrap ordering or infra race pattern. It should map primarily to No.14.
- Example 3 is a first deploy secrets / config drift pattern. It should map primarily to No.16.
"""
    return (
        textwrap.dedent(header)
        + "\n\n=== TXT OS excerpt ===\n"
        + txtos[:6000]
        + "\n\n=== Problem Map excerpt ===\n"
        + problem_map[:6000]
    )


def setup_client():
    """Collect API config and preload WFGY assets."""
    print("Enter your OpenAI API key:")
    api_key = getpass("API key: ")

    base_url = input(
        "Custom OpenAI-compatible base URL (press Enter for default api.openai.com): "
    ).strip()
    if not base_url:
        base_url = "https://api.openai.com/v1"

    model_name = input(
        "Model name (press Enter for gpt-4o): "
    ).strip()
    if not model_name:
        model_name = "gpt-4o"

    print("Downloading WFGY Problem Map and TXTOS prompt...")
    problem_map_text = fetch_text(PROBLEM_MAP_URL)
    txtos_text = fetch_text(TXTOS_URL)
    system_prompt = build_system_prompt(problem_map_text, txtos_text)
    print("Setup complete. WFGY debugger is ready.")
    print()

    client = OpenAI(api_key=api_key, base_url=base_url)

    return client, system_prompt, model_name


def print_examples():
    """Print the three ready-to-copy examples."""
    print("If you do not know what to write, you can copy one of these examples:")
    print("  - Example 1: retrieval hallucination (No.1 style)")
    print("  - Example 2: bootstrap ordering / infra race (No.14 style)")
    print("  - Example 3: secrets / config drift around first deploy (No.16 style)")
    print()
    print("Full text of the examples (ready to copy paste):")
    print("------------------------------------------------------------")
    print(EXAMPLE_1)
    print("------------------------------------------------------------")
    print(EXAMPLE_2)
    print("------------------------------------------------------------")
    print(EXAMPLE_3)
    print("------------------------------------------------------------")
    print()


def run_debug_session(client: OpenAI, system_prompt: str, model_name: str) -> None:
    """Run one interactive debug round."""
    print("============================================================")
    print("WFGY 16 Problem Map LLM Debugger")
    print()
    print("How to use this session:")
    print("  1) Scroll up and read the three examples if you are unsure what to paste.")
    print("  2) Paste one example OR your own LLM / RAG bug description.")
    print("     Include prompt, answer, and any relevant logs.")
    print("  3) When you are done, press Enter on an empty line to submit.")
    print("  4) After you see the diagnosis, open the WFGY Problem Map for the full fix.")
    print()

    print_examples()

    print("Now it is your turn.")
    print("Type your bug description line by line.")
    print("The program will prompt you for each line.")
    print("When you are finished, just press Enter on an empty line to submit.")
    print()

    lines = []
    first = True
    while True:
        try:
            if first:
                prompt = (
                    "Line 1 — paste your bug here "
                    "(press Enter for next line, empty line to finish): "
                )
                first = False
            else:
                prompt = (
                    "Next line — continue typing, or press Enter on an empty line to submit: "
                )
            line = input(prompt)
        except EOFError:
            break

        if not line.strip():
            # Empty line = end of input block
            break

        lines.append(line)

    user_bug = "\n".join(lines).strip()
    if not user_bug:
        print("No bug description detected. Nothing to debug in this round.")
        print()
        return

    print()
    print("Asking the WFGY debugger...")
    print()

    completion = client.chat.completions.create(
        model=model_name,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Here is the bug description. Please follow the rules.\n\n"
                    + user_bug
                ),
            },
        ],
    )

    reply = completion.choices[0].message.content or ""
    print(reply)
    print()
    print("For full documentation and concrete fixes, open the WFGY Problem Map:")
    print(WFGY_PROBLEM_MAP_HOME)
    print()
    print("This debugger is only the front door. The real fixes live in the repo:")
    print(WFGY_REPO)
    print("============================================================")
    print()


# Boot the debugger session
client, system_prompt, model_name = setup_client()

while True:
    run_debug_session(client, system_prompt, model_name)
    again = input("Debug another bug? (y/n): ").strip().lower()
    if again != "y":
        print("Session finished. Goodbye.")
        break
```

### How to run the CLI demo

1. Install the Python dependencies:

   ```bash
   pip install openai requests
   ```

2. Run the script from the `rag_apps/wfgy_llm_debugger` directory:

   ```bash
   python main.py
   ```

3. When prompted:

   * paste your API key
   * optionally paste a custom base URL (for example, your Nebius OpenAI-compatible endpoint)
   * choose a model name (press Enter to use `gpt-4o`)

4. Paste your bug description, prompt, answer, and any logs.
   Type multiple lines if needed; press Enter on an empty line to submit the bug.

You can send multiple bugs in one session; after each diagnosis, the script will ask if you want to debug another one.

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

