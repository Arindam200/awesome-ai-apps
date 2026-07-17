# Custom MCP Server

> A minimal example of building your own [Model Context Protocol](https://modelcontextprotocol.io/) server and calling it from an OpenAI Agents SDK agent.

This project shows the two halves of an MCP integration end to end: a small **email-sending MCP server** built with `FastMCP`, and a **client agent** that spawns that server over stdio and uses its tools to configure and send an email. Use it as a template for wrapping any Python function as an MCP tool.

## 🚀 Features

- **Custom MCP server** (`mcp-server.py`) exposing two tools: `configure_email` and `send_email`
- **Stdio transport** — the server runs as a subprocess, no networking setup required
- **OpenAI Agents SDK client** (`mcp-client.py`) that connects to the server via `MCPServerStdio` and drives it with natural language
- **SMTP email sending** via `smtplib` (Gmail SMTP by default)

## 🛠️ Tech Stack

- **Python**: Core programming language
- **[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)** (`mcp[cli]`) with `FastMCP`: For defining the MCP server and tools
- **[OpenAI Agents SDK](https://github.com/openai/openai-agents-python)**: For the client-side agent that calls the MCP server
- **[Nebius Token Factory](https://dub.sh/nebius)**: OpenAI-compatible inference endpoint for the agent's LLM
- **`smtplib`**: For sending email over SMTP

## Workflow

1. The client starts the MCP server as a subprocess over stdio (`uv run mcp-server.py`).
2. The agent calls `configure_email` with sender name, email, and app passkey.
3. The agent calls `send_email` with a recipient, subject, and body.
4. The MCP server sends the email via Gmail's SMTP server and returns a success/error payload back to the agent.

## 📦 Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for package management
- A [Nebius Token Factory](https://dub.sh/nebius) API key
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833) (regular passwords won't work with `smtplib`)

### Environment Variables

Create a `.env` file in the project root:

```env
NEBIUS_API_KEY="your_nebius_api_key"
GOOGLE_PASSKEY="your_gmail_app_password"
```

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-llm-apps.git
   cd awesome-llm-apps/mcp_ai_agents/custom_mcp_server
   ```

2. **Install dependencies:**

   ```bash
   uv sync
   ```

## ⚙️ Usage

`mcp-client.py` currently points at the MCP server via **absolute paths** (`EMAIL_MCP_PATH` and `UV_PATH`) and a hardcoded example message. Before running it:

1. Update `EMAIL_MCP_PATH` to the absolute path of this project directory on your machine.
2. Update `UV_PATH` to the absolute path of your `uv` binary (`which uv`).
3. Edit the sender name, sender email, recipient, subject, and body in the `message` string to your own values.

Then run:

```bash
uv run mcp-client.py
```

The client will spin up `mcp-server.py` as a subprocess, ask the agent to configure the email sender and send a test email, and print the result.

You can also run the server standalone (e.g. to test it with another MCP client) with:

```bash
uv run mcp-server.py
```

## 📂 Project Structure

```
custom_mcp_server/
├── mcp-server.py      # FastMCP server exposing configure_email / send_email tools
├── mcp-client.py       # OpenAI Agents SDK client that drives the MCP server
├── pyproject.toml      # Dependencies
└── README.md
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See the [CONTRIBUTING.md](https://github.com/Arindam200/awesome-llm-apps/blob/main/CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/Arindam200/awesome-llm-apps/blob/main/LICENSE) file for details.
