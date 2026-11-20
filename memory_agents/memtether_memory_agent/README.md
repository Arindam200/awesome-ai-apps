# MemTether Governed Memory Agent

> A runnable agent where a [Nebius Token Factory](https://dub.sh/nebius) model extracts facts from a conversation, [MemTether](https://github.com/MemTether/MemTether) stores them with provenance, a later correction supersedes the outdated entry instead of deleting it, and the model answers using a bi-temporal `as_of` query over both the old and the current state.

Most memory demos are a `remember()` call next to a vector store. This one is built around the two things that separate MemTether from a plain store: **corrections that supersede instead of overwrite**, and **`as_of` queries that still return the old value for the window in which it was true**.

The model is on the critical path. It extracts the facts, it decides which stored fact a correction supersedes, and it writes the answer from the `as_of` snapshots. Without `NEBIUS_API_KEY` the script exits non-zero rather than quietly running a memory-only path.

## Features

- **LLM-driven extraction**: the model turns a short conversation into a JSON list of durable facts, which are then written one by one.
- **Governed writes**: every `remember()` call carries a `source`, so you always know which agent wrote what.
- **Supersede instead of delete**: the correction creates a new row and closes the old one. The old value still exists with a `valid_to`.
- **Bi-temporal `as_of`**: the same question is answered twice, once at the timestamp of the first write and once now, so the change is visible.
- **Tamper-evident audit chain**: `memtether court <uid>` prints the provenance chain over `audit_log` plus a hash-chain integrity check.
- **Portable**: `OPENAI_BASE_URL` lets you point the same code at any OpenAI-compatible endpoint.

## Tech Stack

- **Python 3.11+**
- **MemTether 0.1.9**: governed memory hub (SQLite, hash-chained audit log, bi-temporal supersession)
- **Nebius Token Factory**: chat completions, default model `Qwen/Qwen3-235B-A22B-Instruct-2507`
- **Rich**: terminal panels
- **python-dotenv**: `.env` loading

## Workflow

```
short conversation
        |
        v
  Nebius extracts facts  --->  memtether.remember(fact, source=...)
                                        |
                                        v
                             corrigendum arrives
                                        |
                                        v
                     Nebius picks the fact it supersedes
                                        |
                                        v
                     memtether.correct(uid, new_fact)   (old row kept)
                                        |
                                        v
        as_of(T1) + as_of(now)  --->  Nebius answers from both snapshots
                                        |
                                        v
                        memtether court <original uid>  (hash chain)
```

## Getting Started

### Prerequisites

- Python 3.11+
- A [Nebius Token Factory](https://dub.sh/nebius) API key. The free tier is enough for this demo.

### Environment variables

Copy `.env.example` to `.env` and fill in the key:

```env
NEBIUS_API_KEY="your_nebius_api_key_here"
```

Optional overrides:

```env
LLM_MODEL="Qwen/Qwen3-235B-A22B-Instruct-2507"
OPENAI_BASE_URL="https://api.tokenfactory.nebius.com/v1"
```

The memory database itself never leaves the machine: MemTether writes a SQLite file under a temporary directory for each run. Only the chat completion calls reach Nebius.

### Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/memory_agents/memtether_memory_agent
```

With `uv`:

```bash
uv sync
uv run main.py
```

With `pip`:

```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -e .
python main.py
```

## What the run does

1. **Extract.** The model reads a four line conversation and returns a JSON array of facts, for example the proxy port, the log retention policy, and the hardware. Nothing is stored yet.
2. **Store.** Each extracted fact goes through `memtether.remember(content, type=..., source="memtether-demo-agent")`. The returned uids are printed.
3. **Correct.** A correction arrives ("I moved the proxy back to 7890"). The model receives the stored uids and their content and returns JSON naming exactly one uid to supersede, plus the corrected sentence. `memtether.correct()` then closes that row and appends the new one.
4. **Answer from `as_of`.** The same question is asked twice with two snapshots: what was valid at the timestamp of the first write, and what is valid now. The model has to report the change and say which value is current.
5. **Audit.** `memtether court <original uid>` prints the case file: content, bi-temporal validity window, the provenance chain from `audit_log`, and the hash-chain integrity result.

## Expected output

Abridged. Uids and the model's wording change on every run; the structure does not.

```
| MemTether governed memory agent
| extract with Nebius, store, correct, answer from as_of, audit with court
  model: Qwen/Qwen3-235B-A22B-Instruct-2507
  db:    /tmp/memtether_demo_xxxx/demo.db

| Step 1: Nebius extracts facts from a conversation
  model extracted 4 facts:
    - Alex moved their entire setup off the cloud and runs it locally.  (fact)
    - Alex's local proxy listens on port 7897, after 7890 kept timing out.  (fact)
    - Alex keeps 14 days of logs and deletes anything older.  (preference)
    - Alex runs a refurbished mini PC with 32 GB of RAM.  (fact)

| Step 2: writing each fact with memtether.remember()
  fact-20261120153129-ed329a777146  (source=memtether-demo-agent)  Alex moved their entire setup off the cloud and runs it locally.
  fact-20261120153129-e548302d15b6  (source=memtether-demo-agent)  Alex's local proxy listens on port 7897, after 7890 kept timing out.
  fact-20261120153129-17b08aece357  (source=memtether-demo-agent)  Alex keeps 14 days of logs and deletes anything older.
  fact-20261120153129-1c8348fdfa56  (source=memtether-demo-agent)  Alex runs a refurbished mini PC with 32 GB of RAM.

| Step 3: a correction arrives, Nebius picks the entry
  supersedes: fact-20261120153129-e548302d15b6
  reason: the correction restates the proxy port
  new entry: fact-20261120153131-6391f036da4a  op=supersede
  the superseded row still exists, with a closed valid_to

| Step 4: Nebius answers the same question twice (2026-11-20 15:31:29 vs now)
  question: Which local proxy port does Alex use, and what changed about it?
  snapshot A at 2026-11-20 15:31:29: 4 rows
  snapshot B now: 4 rows
  | model answer
  | Alex uses port 7890 now. Port 7897 was valid until 2026-11-20 15:31:31, when the
  | correction closed that window, so 7897 is the superseded value and 7890 is current.

| Step 5: memtether court, the hash-chained dossier
+============================================================+
| MEMTETHER MEMORY COURT - CASE FILE
| UID: fact-20261120153129-e548302d15b6
+============================================================+
| 1. CONTENT (current active version)
|   Alex's local proxy listens on port 7897, after 7890 kept timing out.
|   status=superseded conf=0.80 q=0.45 uses=1
|
| 2. TEMPORAL EVIDENCE (bi-temporal)
|   valid (T):  2026-11-20 15:31:29 -> 2026-11-20 15:31:31
|   known (T'): 2026-11-20 15:31:29 -> 2026-11-20 15:31:31
|
| 3. PROVENANCE CHAIN (audit_log)
|   #2 remember  by=memtether-demo-agent  Alex's local proxy listens on port 7
|   #5 correct   by=memtether-demo-agent  Alex's local proxy listens on port 7
|   #6 qvalue    by=memtether-demo-agent  auto: corrected/superseded
|
| 4. CONFLICT ADJUDICATIONS
|   (no conflicts on record)
|
| 5. INTEGRITY PROOF
|   chain: PASS (1 anchors, 6 entries hashed)
|   verify anytime: memtether court --verify
+============================================================+
```

Two details in that output are worth pointing at.

`court` is run against the **original** uid, because `audit_log.target` records the entry that was written and then corrected. Reading the newly created uid shows an empty provenance chain, which is how a superseded fact stays auditable: the history hangs off the row that was replaced.

The two `as_of` snapshots return the same number of rows but different content. That is the point. A plain store would have four rows and no way to ask what was true before the correction.

## Project Structure

```
memtether_memory_agent/
├── main.py            # extract -> store -> correct -> as_of answer -> court
├── pyproject.toml     # pinned dependencies (memtether==0.1.9)
├── README.md
└── .env.example       # copy to .env and fill in the Nebius key
```

## Notes

- `MEM_DB` and `MEMTETHER_HOME` are set inside `main()` before MemTether is imported, so every run gets a throwaway SQLite file and never touches your real memory hub.
- `MAX_TOKENS` is 1500 on purpose. A reasoning model returns an empty string when the budget is too small to finish thinking, and an empty reply looks like a memory bug rather than a truncation.
- The response parser accepts fenced JSON, plain JSON, and JSON surrounded by prose, because not every model honours "JSON only".

## License

This project is part of the awesome-ai-apps collection. MemTether itself is Apache-2.0 licensed.

## Acknowledgments

- [MemTether](https://github.com/MemTether/MemTether): the governed memory hub this agent uses
- [Nebius Token Factory](https://dub.sh/nebius): chat completions
