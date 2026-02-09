# WFGY 16 Problem Map LLM Debugger (Colab full demo)
# Single cell script: paste everything into one Colab cell and run.

from getpass import getpass
import os
import textwrap
import requests
from openai import OpenAI

PROBLEM_MAP_URL = "https://raw.githubusercontent.com/onestardao/WFGY/main/ProblemMap/README.md"
TXTOS_URL = "https://raw.githubusercontent.com/onestardao/WFGY/main/OS/TXTOS.txt"
WFGY_PROBLEM_MAP_HOME = "https://github.com/onestardao/WFGY/tree/main/ProblemMap#readme"
WFGY_REPO = "https://github.com/onestardao/WFGY"

EXAMPLE_1 = """=== Example 1 - retrieval hallucination (No.1 style) ===

Context: I have a simple RAG chatbot that answers questions from a product FAQ.
The FAQ only covers billing rules for my SaaS product and does NOT mention anything about cryptocurrency or stock trading.

Prompt: "Can I pay my subscription with Bitcoin?"

Retrieved context (from vector store):
- "We only accept major credit cards and PayPal."
- "All payments are processed in USD."

Model answer:
"Yes, you can pay with Bitcoin. We support several cryptocurrencies through a third-party payment gateway."

Logs:
No errors. Retrieval shows the FAQ chunks above, but the model still confidently invents "Bitcoin" support.
"""

EXAMPLE_2 = """=== Example 2 - bootstrap ordering / infra race (No.14 style) ===

Context: We have a simple RAG API with three services: api-gateway, rag-worker, and vector-db (running Qdrant).
In local docker compose everything works without problems.

Deployment: In production, we deploy these services on Kubernetes.

Symptom:
Sometimes, right after a fresh deploy, the api-gateway returns 500 errors for the first few minutes.
Logs show connection timeouts from api-gateway to vector-db.

After a while, maybe 5 to 10 minutes, the errors disappear and the system works normally.

We suspect some kind of startup race between api-gateway and vector-db, but we are not sure how to fix it properly.
"""

EXAMPLE_3 = """=== Example 3 - secrets / config drift around first deploy (No.16 style) ===

Context: We added a new environment variable for our RAG pipeline: SECRET_RAG_KEY.
This is required by a middleware that signs all outgoing requests to our internal search API.

Local: On local machines, developers set SECRET_RAG_KEY in their .env file and everything works.

Production:
We deployed a new version of the app, but forgot to add SECRET_RAG_KEY to the production environment.
The first requests after deploy start failing with 500 errors and "missing secret" messages in the logs.

After we hot-patched the secret into the production config, the errors stopped.
However, this kind of "first deploy breaks because of missing secrets or config drift" keeps happening in different forms.
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
Given a description of a bug or failure in an LLM or RAG pipeline, you map it to the closest Problem Map number (No.1 to No.16), explain why, and propose a minimal fix.

Rules:
- Always return exactly one primary Problem Map number (No.1 to No.16).
- Optionally return one secondary candidate if it is very close.
- Explain your reasoning in plain language.
- Point the user toward the right place inside the WFGY Problem Map when possible.
- Prefer minimal structural patches over generic high level advice.

About the three built in examples:
- Example 1 is a clean retrieval hallucination pattern. It should map primarily to No.1.
- Example 2 is a bootstrap ordering or infra race pattern. It should map primarily to No.14.
- Example 3 is a first deploy secrets or config drift pattern. It should map primarily to No.16.
"""
    return (
        textwrap.dedent(header).strip()
        + "\n\n=== TXTOS excerpt ===\n"
        + txtos[:6000]
        + "\n\n=== Problem Map excerpt ===\n"
        + problem_map[:6000]
    )


def setup_client():
    """
    Collect API configuration, preload WFGY assets, and return
    an OpenAI client together with the system prompt and model name.
    """
    print("Step 1: configure your OpenAI-compatible endpoint.")
    print()

    # Prefer environment variables if they exist, but allow override.
    env_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("NEBIUS_API_KEY")
    api_key: str

    if env_api_key:
        print("Detected an API key in environment variables.")
        use_env = input("Use this key? (y/n, default y): ").strip().lower()
        if use_env in ("", "y"):
            api_key = env_api_key.strip()
        else:
            api_key = getpass("Enter your OpenAI-compatible API key: ").strip()
    else:
        api_key = getpass("Enter your OpenAI-compatible API key: ").strip()

    if not api_key:
        raise ValueError("API key cannot be empty.")

    # Default to Nebius Token Factory endpoint if none is provided.
    default_base_url = os.getenv("OPENAI_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
    base_url = input(
        f"Custom OpenAI-compatible base URL (press Enter for {default_base_url}): "
    ).strip()
    if not base_url:
        base_url = default_base_url

    # Let the user choose any model id. Provide a Nebius friendly default.
    default_model = os.getenv("OPENAI_MODEL") or "meta-llama/Meta-Llama-3.1-70B-Instruct"
    model_name = input(
        f"Model name (press Enter for {default_model}): "
    ).strip()
    if not model_name:
        model_name = default_model

    print()
    print("Step 2: downloading WFGY Problem Map and TXTOS prompt...")
    problem_map_text = fetch_text(PROBLEM_MAP_URL)
    txtos_text = fetch_text(TXTOS_URL)
    system_prompt = build_system_prompt(problem_map_text, txtos_text)
    print("Setup complete. WFGY debugger is ready.")
    print()
    print(f"Using base URL: {base_url}")
    print(f"Using model:   {model_name}")
    print()

    client = OpenAI(api_key=api_key, base_url=base_url)

    return client, system_prompt, model_name


def print_examples():
    """Print the three ready-to-copy examples."""
    print("If you are not sure what to write, you can start from one of these examples:")
    print("  - Example 1: retrieval hallucination (No.1 style)")
    print("  - Example 2: bootstrap ordering or infra race (No.14 style)")
    print("  - Example 3: secrets or config drift around first deploy (No.16 style)")
    print()
    print("Full text of the examples (ready to copy and paste):")
    print("------------------------------------------------------------")
    print(EXAMPLE_1)
    print("------------------------------------------------------------")
    print(EXAMPLE_2)
    print("------------------------------------------------------------")
    print(EXAMPLE_3)
    print("------------------------------------------------------------")
    print()


def run_debug_session(client: OpenAI, system_prompt: str, model_name: str) -> None:
    """Run one interactive debug round in the Colab cell."""
    print("============================================================")
    print("WFGY 16 Problem Map LLM Debugger")
    print()
    print("How to use this cell:")
    print("  1) Scroll up and read the three examples.")
    print("  2) Paste one example or your own LLM / RAG bug description.")
    print("     Include prompt, answer, and any relevant logs.")
    print("  3) When you are done, press Enter on an empty line to submit.")
    print("  4) After you see the diagnosis, open the WFGY Problem Map for the full fix.")
    print()

    print_examples()

    print("Now it is your turn.")
    print("Type your bug description line by line.")
    print("Colab will open a small input box for each line.")
    print("When you are finished, press Enter on an empty line to submit.")
    print()

    lines = []
    first = True
    while True:
        try:
            if first:
                prompt = (
                    "Line 1 - paste your bug here "
                    "(press Enter for next line, empty line to finish): "
                )
                first = False
            else:
                prompt = (
                    "Next line - continue typing, or press Enter on an empty line to submit: "
                )
            line = input(prompt)
        except EOFError:
            break

        if not line.strip():
            # Empty line = end of input block.
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

    try:
        completion = client.chat.completions.create(
            model=model_name,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Here is the bug description. Please follow the WFGY rules.\n\n"
                        + user_bug
                    ),
                },
            ],
        )
    except Exception as exc:
        print("Call to the LLM endpoint failed.")
        print("Please check your API key, base URL, and model name.")
        print(f"Error detail: {exc}")
        print()
        return

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


# Boot the debugger session.
client, system_prompt, model_name = setup_client()

while True:
    run_debug_session(client, system_prompt, model_name)
    again = input("Debug another bug? (y/n): ").strip().lower()
    if again != "y":
        print("Session finished. Goodbye.")
        break
