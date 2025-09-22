![demo](./assets/linkup_logo-removebg-preview.png)

## Researcher Agent with GibsonAI Memori & Linkup

An AI research assistant that performs real-time web research with Linkup, remembers everything with GibsonAI Memori, and lets you chat with your past research. The Streamlit app provides two modes: research and memory retrieval.

### Features

- **🔎 Real-time Research**: Uses Linkup to search and synthesize up-to-date information
- **🧠 Persistent Memory (Memori)**: Automatically stores research sessions and agent conversations
- **💬 Memory Chat**: Query your entire research history and get summarized answers
- **📚 Session History**: See topics and findings across sessions
- **⚙️ In-App API Setup**: Enter and save keys in the sidebar UI

### Prerequisites

- Python 3.10+
- API credentials for:
  - `OPENAI_API_KEY`
  - `LINKUP_API_KEY`

### Installation

Clone the repository:

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd "memory_agents/researcher_agent
```

Install dependencies with uv:

```bash
uv sync
```

If you prefer environment variables via shell, export them before running:

```bash
export OPENAI_API_KEY=your_openai_api_key
export LINKUP_API_KEY=your_linkup_api_key
```

You can also set these keys inside the app from the sidebar (no .env required).

### Usage

Run the Streamlit app with uv:

```bash
uv run streamlit run app.py
```

Open your browser to the URL shown in the terminal (typically `http://localhost:8501`).

### How It Works

#### 1) Research Chat
- Enter a research prompt in the chat input
- The agent conducts web research using Linkup and compiles a response
- All intermediate conversations are saved to Memori automatically

#### 2) Memory Chat
- Ask questions about your prior research sessions
- The agent retrieves and summarizes relevant findings from memory

### Sidebar Overview

- **Navigation**: Switch between Research Chat and Memory Chat
- **API Keys**: Provide `OPENAI_API_KEY` and `LINKUP_API_KEY`; saved to the session environment
- **About**: Quick project overview and capabilities
- **Research History**: View all research or clear memory (with confirmation)

### Architecture

- **UI Layer (`app.py`)**: Streamlit interface, sidebar controls, chat flows
- **Agent Layer (`researcher.py`)**: Defines and runs the research and memory agents
- **Storage (`research_memori.db`)**: Local database for persistent memory
- **Assets (`assets/`)**: Logos and visuals (e.g., `gibson.svg`, `linkup_logo-removebg-preview.png`)

### Example Prompts

- "Research the latest developments in brain-computer interfaces"
- "Analyze the current state of solid-state batteries"
- "Summarize my research history and main findings"


### Contributing

Issues and pull requests are welcome. Please open an issue to discuss significant changes.

### License

MIT License. See `LICENSE` if provided.


