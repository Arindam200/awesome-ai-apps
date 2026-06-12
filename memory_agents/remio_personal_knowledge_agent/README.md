# Remio Personal Knowledge Agent

> A Remio-powered local-first personal knowledge agent that uses the Remio desktop app to search and answer questions over indexed notes, files, webpages, recordings, emails, messages, images, and other knowledge sources.

This Streamlit app demonstrates how agents can use Remio as their local memory and knowledge base, retrieving targeted context from Remio's local index and vector search instead of repeatedly scanning raw files or loading full documents into prompts.

## Features

- **Local-first memory retrieval**: Uses Remio's local index and vector retrieval for personal knowledge search.
- **RAG Q&A**: Answers questions with `remio rag` over indexed notes and files.
- **Semantic note search**: Finds relevant notes with `remio search_notes`.
- **Broad source coverage**: Works with Remio-parsed notes, files, webpages, recordings, emails, messages, and images.
- **Desktop app check**: Detects missing Remio desktop app or CLI access and points users to https://remio.ai/.
- **Token-efficient context**: Retrieves relevant indexed chunks before synthesis instead of sending whole folders or documents to an LLM.

## Tech Stack

- **Python**: Core programming language
- **Streamlit**: User interface
- **Remio Desktop App**: Required local knowledge base, parser, and index service
- **Remio CLI**: Interface this app uses to query Remio's local knowledge base

## Workflow

The app checks whether the Remio desktop app is installed and reachable through the CLI, then routes the user's query to either semantic note search or RAG Q&A. Remio handles indexing, vector retrieval, and source parsing before the app displays the answer or matching notes.

## Getting Started

### Prerequisites

- Python 3.10+
- `pip` or `uv` for package management
- Remio desktop app installed and running from https://remio.ai/
- Remio CLI access from your shell path

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/memory_agents/remio_personal_knowledge_agent
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Install or open Remio:**

   This app depends on the Remio desktop app. Download or open Remio from:

   ```text
   https://remio.ai/
   ```

   Then verify the local setup:

   ```bash
   remio doctor
   ```

## Usage

1. **Run the application:**

   ```bash
   streamlit run app.py
   ```

2. Open your browser to `http://localhost:8501`.

3. Use the sidebar to check Remio status, choose **RAG answer** or **Search notes**, then ask about your indexed personal knowledge.

## Project Structure

```
remio_personal_knowledge_agent/
├── app.py              # Streamlit application
├── requirements.txt    # Python dependencies
└── README.md           # Project documentation
```

## Contributing

Contributions are welcome. You can improve the UI, add more Remio commands, or extend the example with citation rendering and saved workflows.

## License

This project is part of the Awesome AI Apps collection.

## Acknowledgements

- [Remio](https://remio.ai/) for the local-first personal knowledge app, parser, index, semantic retrieval, and CLI access used by this project.
