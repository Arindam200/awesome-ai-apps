# 🧠 TraceMind — Adaptive Learning Diagnostic Agent

> Identify step-level misconceptions in student reasoning and track them over time.

TraceMind is an adaptive learning diagnostic agent that analyzes a student's reasoning trace, identifies possible misconceptions, and keeps track of recurring mistakes across attempts.

Built as a lightweight example under `advance_ai_agents`.

## 🚀 Features

- **Trace parser** — processes a student's step-by-step reasoning and extracts meaningful reasoning steps.
- **Misconception matcher** — compares reasoning patterns against a small library of known Python loop misconceptions.
- **Persistence tracker** — records recurring misconceptions so repeated mistakes can be identified over multiple attempts.
- **Simple CLI demo** — run the diagnostic workflow directly from the terminal.

## 🛠️ Tech Stack

- **Python 3.10+**
- Python standard library
- Lightweight rule-based misconception matching
- JSON-based persistence for diagnostic history

## 🔄 Workflow

```text
Student reasoning trace
        ↓
    Trace Parser
        ↓
Misconception Matcher
        ↓
Diagnostic Result
        ↓
Persistence Tracker
        ↓
Updated learning history

```

Trace parser — reads the student's step-by-step reasoning.
Misconception matcher — checks the reasoning against known Python loop misconception patterns.
Diagnostic result — reports the detected misconception and the reasoning step where it occurred.
Persistence tracker — stores the diagnostic history so recurring misconceptions can be recognized later.


## 📦 Getting Started

### Prerequisites
Python 3.10+
uv (recommended) or pip
No API keys or environment variables are required for the current MVP.

### Installation
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/advance_ai_agents/tracemind

uv sync

### Usage

Run the CLI example:

uv run python main.py

The demo runs a sample student reasoning trace through the diagnostic pipeline and displays the detected misconception and learning history.

## 📂 Project Structure

```text
tracemind/
├── main.py              # CLI demonstration
├── parser.py            # Student reasoning trace parser
├── misconception.py     # Known misconception matching
├── tracker.py            # Persistent diagnostic history
├── pyproject.toml       # Project dependencies and metadata
├── .env.example         # Environment configuration template
└── README.md
```



## 🔍 Example Diagnostic

A student may reason about a Python loop incorrectly by assuming that a loop variable permanently changes the underlying collection.

TraceMind can identify the relevant reasoning pattern, report the associated misconception, and store it in the student's diagnostic history.

## 🤝 Contributing

Contributions are welcome! Please see the repository's CONTRIBUTING.md for details.
