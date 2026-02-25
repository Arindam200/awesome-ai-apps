# Taskade MCP Agent

An AI-powered workspace agent that connects to [Taskade](https://taskade.com) via the [Model Context Protocol (MCP)](https://github.com/taskade/mcp) to manage projects, tasks, and workflows using natural language. Built with Agno and Nebius AI.

## Features

- **Project Management**: Create, list, and manage Taskade projects and workspaces
- **Task Operations**: Add, update, complete, and organize tasks across projects
- **AI Agent Integration**: Interact with Taskade's autonomous AI agents
- **Natural Language Interface**: Manage your workspace using conversational queries
- **MCP Protocol**: Uses Taskade's official MCP server for secure, structured API access

## Tech Stack

- **Python**: Core programming language
- **Streamlit**: Interactive web interface
- **Agno**: AI agent framework
- **Nebius AI**: LLM provider (Qwen3-30B-A3B)
- **Taskade MCP Server**: Model Context Protocol server for Taskade API
- **python-dotenv**: Environment variable management

## Prerequisites

- Python 3.10+
- Node.js 18+ (for the Taskade MCP server)
- A [Taskade](https://taskade.com) account and API key
- A [Nebius AI](https://studio.nebius.ai/) API key

## Getting Started

### Environment Variables

Create a `.env` file in the project root:

```env
NEBIUS_API_KEY="your_nebius_api_key"
TASKADE_API_KEY="your_taskade_api_key"
```

You can generate a Taskade API key from your [Taskade Settings](https://taskade.com/settings/api).

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/mcp_ai_agents/taskade_mcp_agent
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -r requirements.txt
   ```

4. **Install the Taskade MCP server:**

   ```bash
   npm install -g @taskade/mcp-server
   ```

## Usage

1. **Run the application:**

   ```bash
   streamlit run main.py
   ```

2. **Open your browser** to `http://localhost:8501`

3. In the sidebar, enter your Nebius API key and Taskade API key, then click **Save Configuration**.

4. Use the query input to interact with your Taskade workspace:
   - **List Projects**: "Show all my projects"
   - **Create Tasks**: "Add a task called 'Review PR' to my project"
   - **Manage Workflows**: "What tasks are due this week?"
   - **Custom Queries**: Ask anything about your Taskade workspace

## Project Structure

```
taskade_mcp_agent/
├── assets/               # Static assets
├── .env.example          # Example environment variables
├── main.py               # Streamlit application
├── requirements.txt      # Python dependencies
└── README.md             # Project documentation
```

## About Taskade

[Taskade](https://taskade.com) is an AI-native workspace platform for building apps, deploying autonomous AI agents, and automating workflows with 100+ integrations. Key features include:

- **AI Agents**: Deploy autonomous agents that work across your projects
- **Genesis AI App Builder**: Build custom AI-powered apps visually
- **MCP Server**: Connect AI tools to Taskade via the Model Context Protocol
- **Workflow Automation**: Automate repetitive tasks with AI-powered workflows

Learn more:
- [Taskade AI Agents](https://taskade.com/agents)
- [Taskade MCP Server](https://github.com/taskade/mcp)
- [Taskade Genesis](https://taskade.com/genesis)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See the [CONTRIBUTING.md](../../CONTRIBUTING.md) for more details.

## License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.
