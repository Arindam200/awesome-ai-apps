<!-- Optional: Add a banner or GIF at the top -->
<!-- TODO: Add a small Colab / Nebius screenshot later, e.g. ./assets/wfgy-16-debugger.gif -->

# 🧩 WFGY 16 Problem Map LLM Debugger (Nebius compatible)

> A 16 mode, map based debugger that turns messy LLM / RAG bugs into reproducible failure modes, each linked to a concrete fix in the WFGY Problem Map.

A Nebius compatible notebook and minimal CLI that helps LLM and RAG developers **classify bugs into one of 16 failure modes** (No.1–No.16) instead of guessing.

Paste a trace, log, or prompt / answer pair, and the debugger returns the closest Problem Map number plus a suggested fix in the open source WFGY repo.

The script is written in plain **Python** using the official **OpenAI client** and **requests**, so it can call any OpenAI compatible API.  
For Nebius Token Factory you only need to point the client to the Nebius endpoint and pick a Nebius model id.

---

## 🚀 Features

- **16 mode failure map**  
  Maps each bug or incident to one primary Problem Map number `No.1–No.16` and an optional secondary candidate.

- **LLM / RAG first design**  
  Works with prompts, answers, retrieval traces, and logs. No SDK or infra changes required. Everything is done with text prompts.

- **Semantic firewall debugger**  
  Uses `TXTOS.txt` as a “reasoning OS” plus the WFGY Problem Map README to reason about failures before generation.

- **Colab / Nebius single cell script**  
  One script that:
  - asks for your API key, base URL, and model
  - downloads WFGY references
  - guides you line by line to paste the bug
  - prints the diagnosis and next steps

- **CLI friendly**  
  The same script can be saved as `main.py` and run from a terminal, so it fits into existing workflows or dev shells.

---

## 🛠️ Tech Stack

- **Python 3.9+** – core runtime  
- **OpenAI Python client** – used against any OpenAI compatible chat completions API  
- **requests** – downloads WFGY assets (`TXTOS.txt` and `ProblemMap/README.md`)  
- **Nebius Token Factory or other OpenAI compatible endpoints** – LLM provider  
- **Jupyter / Colab / Nebius notebooks** – recommended for interactive runs, but not required

---

## 🧩 WFGY Problem Map (16 modes)

The debugger is powered by the public WFGY Problem Map:

- [WFGY Problem Map 1.0 – main page](https://github.com/onestardao/WFGY/tree/main/ProblemMap#readme)

It focuses on mapping real world bugs into the following classes:

| No. | Problem domain | What breaks in practice | Doc |
|-----|----------------|-------------------------|-----|
| 1   | Hallucination and chunk drift | Retrieval returns wrong or irrelevant content | [hallucination](https://github.com/onestardao/WFGY/blob/main/ProblemMap/hallucination.md) |
| 2   | Interpretation collapse | Chunk is correct, reasoning is wrong | [retrieval collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/retrieval-collapse.md) |
| 3   | Long reasoning chains | Multi step tasks drift and never converge | [context drift](https://github.com/onestardao/WFGY/blob/main/ProblemMap/context-drift.md) |
| 4   | Bluffing and overconfidence | Confident answers with no real support | [bluffing](https://github.com/onestardao/WFGY/blob/main/ProblemMap/bluffing.md) |
| 5   | Semantic ≠ embedding | Cosine similarity does not match true meaning | [embedding vs semantic](https://github.com/onestardao/WFGY/blob/main/ProblemMap/embedding-vs-semantic.md) |
| 6   | Logic collapse and recovery | Chains hit dead ends and need controlled reset | [logic collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/logic-collapse.md) |
| 7   | Memory breaks across sessions | Lost threads and no continuity | [memory coherence](https://github.com/onestardao/WFGY/blob/main/ProblemMap/memory-coherence.md) |
| 8   | Debugging as a black box | No visibility into retrieval and failure paths | [retrieval traceability](https://github.com/onestardao/WFGY/blob/main/ProblemMap/retrieval-traceability.md) |
| 9   | Entropy collapse | Attention melts into incoherent output | [entropy collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/entropy-collapse.md) |
| 10  | Creative freeze | Flat and literal outputs when you needed structure and creativity | [creative freeze](https://github.com/onestardao/WFGY/blob/main/ProblemMap/creative-freeze.md) |
| 11  | Symbolic collapse | Abstract or logical prompts stop working | [symbolic collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/symbolic-collapse.md) |
| 12  | Philosophical recursion | Self reference loops and paradox traps | [philosophical recursion](https://github.com/onestardao/WFGY/blob/main/ProblemMap/philosophical-recursion.md) |
| 13  | Multi agent chaos | Agents overwrite or misalign each other | [multi agent problems](https://github.com/onestardao/WFGY/blob/main/ProblemMap/Multi-Agent_Problems.md) |
| 14  | Bootstrap ordering | Services start before dependencies and quietly fail | [bootstrap ordering](https://github.com/onestardao/WFGY/blob/main/ProblemMap/bootstrap-ordering.md) |
| 15  | Deployment deadlock | Circular waits in infra and pipelines | [deployment deadlock](https://github.com/onestardao/WFGY/blob/main/ProblemMap/deployment-deadlock.md) |
| 16  | Pre deploy collapse | Version skew or missing secrets on first call | [pre deploy collapse](https://github.com/onestardao/WFGY/blob/main/ProblemMap/predeploy-collapse.md) |

Once a bug is mapped to a number, you can apply the fix and expect it not to quietly reappear in the same way.

---

## Workflow

<!-- Optional: Add a workflow diagram or GIF -->
<!-- TODO: Add a small text diagram or GIF later, e.g. ./assets/workflow.gif -->

**High level flow:**

1. User runs the single cell script in Nebius / Colab / Jupyter, or runs `python main.py` in a terminal.  
2. Script asks for:
   - API key (via `getpass`)
   - optional custom base URL
   - model name (you type the model id you want to use)
3. Script downloads:
   - `TXTOS.txt` from `OS/TXTOS.txt`
   - `ProblemMap/README.md` from `ProblemMap/README.md`
4. User pastes a bug description (prompt, answer, logs).  
5. Model returns:
   - primary `No.X`
   - optional secondary `No.Y`
   - short reasoning
   - which WFGY Problem Map page to read first and what patch to try.

You can treat this as a **diagnostic layer in front of any LLM app**, without changing infra.

---

## 📦 Getting Started

### Prerequisites

- Python **3.9+**
- An OpenAI compatible endpoint, for example:
  - Nebius Token Factory  
  - OpenAI  
  - your own gateway
- An API key for that endpoint

### Environment variables

The script can be run entirely interactively, but these are the variables it ultimately uses.  
For Nebius Token Factory a typical setup looks like this:

```env
# Nebius Token Factory
NEBIUS_API_KEY="your_nebius_api_key"

# The script reads OPENAI_API_KEY, so you can export the same value here
OPENAI_API_KEY="$NEBIUS_API_KEY"

# Nebius Token Factory OpenAI compatible endpoint
OPENAI_BASE_URL="https://api.tokenfactory.nebius.com/v1/"

# Any Nebius model id, for example a Llama instruction model
OPENAI_MODEL="meta-llama/Meta-Llama-3.1-70B-Instruct"
````

If you prefer to keep everything interactive, you can skip setting these.
The script will then ask you for the API key, base URL, and model name at runtime.

For other OpenAI compatible endpoints you can point `OPENAI_BASE_URL` to the corresponding URL and use whatever model id your provider exposes.

---

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-llm-apps.git
   cd awesome-llm-apps/rag_apps/wfgy_llm_debugger
   ```

2. **Create and activate a virtual environment (optional but recommended):**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install openai requests
   ```

---

## ⚙️ Usage

### 1. Notebook / Colab / Nebius (single cell demo)

1. Open a new notebook (Nebius, Colab, or local Jupyter).

2. Paste the full script from `main.py` into a single cell.

3. Run the cell. It will:

   * ask for your API key
   * ask for an optional base URL
   * ask for a model name

   For Nebius, you can answer for example:

   * base URL: `https://api.tokenfactory.nebius.com/v1/`
   * model: `meta-llama/Meta-Llama-3.1-70B-Instruct` (or any other Nebius model id)

4. Follow the prompts:

   * type or paste your bug description line by line
   * press Enter on an empty line to submit

The debugger prints:

* one primary `No.X`
* an optional secondary `No.Y`
* a short explanation in plain language
* which WFGY document to open and what first fix to try

### 2. CLI demo (`main.py`)

You can also run the same script directly from the terminal.

```bash
python main.py
```

When prompted:

* paste your API key
* optionally paste a custom base URL (for example, the Nebius Token Factory endpoint)
* choose a model name by typing the model id you want to use

Then paste your bug description, prompt, answer, and any logs.
Type multiple lines if needed, and press Enter on an empty line to submit the bug.

You can send multiple bugs in one session. After each diagnosis, the script asks if you want to debug another one.

---

## 📂 Project Structure

This project lives under the `rag_apps` directory of the main repo.

```text
rag_apps/
└── wfgy_llm_debugger/
    ├── main.py        # Single cell style debugger script (also works as CLI)
    └── README.md      # This file
```

An `assets/` folder can be added later for GIFs or screenshots if desired.

---

## 🤝 Contributing

Contributions and feedback are welcome.
If you would like to tweak the prompt, add more examples, or extend the debugger to other providers, feel free to open an issue or submit a PR.

Please see the main repository’s [CONTRIBUTING.md](https://github.com/Arindam200/awesome-llm-apps/blob/main/CONTRIBUTING.md) for detailed guidelines.

---

## 📄 License

This project follows the license of the parent repository and the upstream WFGY project:

* awesome-llm-apps: [MIT License](https://github.com/Arindam200/awesome-llm-apps/blob/main/LICENSE)
* WFGY / Problem Map content: MIT licensed in the original repo

---

## 🙏 Acknowledgments

* [Nebius AI](https://nebius.com/) for the OpenAI compatible infrastructure.
* [WFGY Project](https://github.com/onestardao/WFGY) for the Problem Map, TXTOS, and the semantic firewall idea.
* The awesome-llm-apps maintainers for curating a high quality gallery of practical LLM and RAG applications.

