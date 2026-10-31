# MemTether Governed Memory Agent

> A runnable agent that uses [MemTether](https://github.com/MemTether/MemTether) as a governed, tamper-evident memory store — writes, corrects (supersede), recalls, and audits memories. LLM access via [Nebius Token Factory](https://dub.sh/nebius).

This project demonstrates **memory with governance**: every fact written by the agent carries a source identity and a hash-chained audit trail; corrections use bi-temporal supersession (nothing is deleted); and the agent can query memory "as of" any past point in time. It shows the two features that separate MemTether from plain memory stores: **correct-instead-of-delete** and **as_of queries**.

## 🚀 Features

- **Governed memory writes**: every `remember` call carries a `--source` so you always know which agent wrote what.
- **Supersede-instead-of-delete**: corrections create a new version and mark the old one superseded — nothing is lost.
- **Bi-temporal `as_of` queries**: ask "what did the system believe at 10-15?" and get the historical truth.
- **Tamper-evident audit chain**: a hash chain over all memories; running `python examples/audit_chain_demo.py` in the MemTether repo shows it turn red on tampering.
- **LLM-agnostic**: uses OpenAI-compatible chat completion via Nebius Token Factory (swap `NEBIUS_API_KEY` for any OpenAI-compatible endpoint).
- **Rich CLI output**: formatted tables via `rich` showing memory UIDs, conflict verdicts, and chain status.

## 🛠️ Tech Stack

- **Python**: Core programming language
- **MemTether**: Governed cross-client memory hub (SQLite, hash-chained audit, bi-temporal)
- **Nebius Token Factory**: For LLM chat completion (DeepSeek-V3-0324)
- **Rich**: For formatted terminal output
- **python-dotenv**: For environment variable management

## Workflow

```
┌─────────────────┐     remember(...)      ┌──────────────────┐
│   Agent (you)   │ ──────────────────────▶│  MemTether DB    │
│                 │                        │  (source=codex,  │
│  1. Write fact  │                        │   hash-chained)  │
│  2. Correct it  │ ◀──────────────────────│  supersede chain │
│  3. Query as_of │     search/correct     │  bi-temporal     │
└─────────────────┘                        └──────────────────┘
```

## 📦 Getting Started

### Prerequisites

- Python 3.11+
- A [Nebius Token Factory](https://dub.sh/nebius) API key (free tier available)
- `memtether` installed via pip (installed automatically by `uv sync` or `pip install`)

### Environment Variables

Create a `.env` file in the project root:

```env
NEBIUS_API_KEY="your_nebius_api_key_here"
```

**Note:** MemTether stores its database locally in a SQLite file. No cloud service is needed for memory — only the LLM call goes to Nebius.

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/memory_agents/memtether_memory_agent
   ```

2. **Create and activate a virtual environment:**

   - **Using `venv`:**
     ```bash
     python -m venv .venv
     source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
     ```

3. **Install dependencies:**

   - **Using `uv` (recommended):**
     ```bash
     uv sync
     ```
   - **Using `pip`:**
     ```bash
     pip install memtether openai python-dotenv rich
     ```

## ⚙️ Usage

1. **Run the application:**

   ```bash
   uv run main.py
   ```

2. The agent will:

   **Step 1 — Write a memory.** The agent calls `memtether remember` with a source tag and a fact, then prints the memory UID and chain anchor.

   **Step 2 — Correct the memory.** The agent realizes a fact is outdated and calls `memtether correct` (supersede). The old version is marked superseded but not deleted — you can still query it with `--as_of`.

   **Step 3 — Query memory as of a past date.** The agent calls `memtether search --as_of 2026-10-01` to get the historical state, showing that the old value was "true" at that time.

   **Step 4 — Audit.** The agent runs `memtether court <uid>` to display the full case file: temporal validity, provenance chain, conflict verdicts, and hash-chain integrity.

3. **Expected output** (abridged):

   ```
   ┌────────────────────────────────────────────────┐
   │ Step 1: Writing memory...                      │
   │ uid: fact-20261031-abc123  source: demo-agent  │
   │ chain: PASS (1 anchor, 1 entry)                │
   ├────────────────────────────────────────────────┤
   │ Step 2: Correcting (supersede)...              │
   │ old: fact-20261031-abc123 → superseded         │
   │ new: fact-20261031-def456                      │
   ├────────────────────────────────────────────────┤
   │ Step 3: Searching as_of 2026-10-01...          │
   │ result: old value (correct for that date)      │
   ├────────────────────────────────────────────────┤
   │ Step 4: Memory Court audit...                  │
   │ 1. CONTENT    Clash proxy port is 7897         │
   │ 2. TEMPORAL    valid: 10-05 → present          │
   │ 3. PROVENANCE #1 remember → #2 correct         │
   │ 4. CONFLICTS  case #3: verdict=superseded      │
   │ 5. INTEGRITY  chain: PASS                      │
   └────────────────────────────────────────────────┘
   ```

## 📂 Project Structure

```
memtether_memory_agent/
├── main.py               # Runnable agent: write → correct → as_of → court
├── pyproject.toml        # Dependencies (memtether, openai, rich, dotenv)
├── README.md             # This file
└── .env.example          # Copy to .env and fill in your Nebius key
```

## 📄 License

This project is part of the awesome-ai-apps collection. MemTether itself is Apache-2.0 licensed.

## 🙏 Acknowledgments

- [MemTether](https://github.com/MemTether/MemTether) — the governed memory hub this agent uses
- [Nebius Token Factory](https://dub.sh/nebius) — for the LLM
- Inspired by the awesome-llm-apps collection
