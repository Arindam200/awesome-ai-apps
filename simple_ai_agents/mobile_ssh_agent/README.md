# Mobile SSH Agent

> Run AI coding agents on a remote server and access them from anywhere — your laptop, phone, or tablet.

A setup script that provisions a remote server with an AI coding agent (Claude Code, Codex CLI, or Aider) over SSH and starts an interactive session. Once configured, you can reconnect from any device with an SSH client.

## How it Works

The script connects to your remote server via SSH and:

1. Checks connectivity and authentication
2. Installs Node.js (via nvm) if the chosen agent requires it
3. Installs the coding agent CLI globally
4. Launches an interactive terminal session with the agent

After the initial setup, you can connect directly from any SSH client — including mobile apps like [Onepilot](https://onepilotapp.com), Termius, or Blink Shell — and start the agent manually.

## Why Remote Agents?

Running coding agents on a remote server has a few practical benefits:

- **Access from any device** — SSH in from your phone during a commute, or from a tablet on the couch
- **Persistent sessions** — use `tmux` or `screen` so agent sessions survive disconnects
- **Better hardware** — run agents on a machine with more RAM/CPU than your local device
- **Consistent environment** — same dev setup regardless of which client you connect from

## Prerequisites

- Python 3.10+
- A remote server (VPS, cloud instance, or home lab) with SSH access
- An API key for your chosen agent:
  - [Anthropic API key](https://console.anthropic.com/) for Claude Code
  - [OpenAI API key](https://platform.openai.com/) for Codex CLI
  - Any supported provider key for Aider

## Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/simple_ai_agents/mobile_ssh_agent
   ```

2. **Install dependencies:**

   ```bash
   pip install uv
   uv sync
   ```

   Or with pip:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your server details:

   ```env
   SSH_HOST="your-server.example.com"
   SSH_USER="your_username"
   SSH_PORT="22"
   SSH_KEY_PATH="~/.ssh/id_rsa"
   AGENT_CLI="claude"
   ```

## Usage

Run the setup script:

```bash
uv run main.py
```

This will connect to your server, install the agent if needed, and drop you into an interactive session.

### Reconnecting Later

Once set up, you can skip the script and SSH in directly:

```bash
ssh your-server.example.com
claude  # or codex, aider
```

For persistent sessions that survive disconnects:

```bash
ssh your-server.example.com
tmux new -s agent
claude
# Detach with Ctrl+B, D — reattach later with: tmux attach -t agent
```

## Supported Agents

| Agent | Install Command | Requires |
|-------|----------------|----------|
| [Claude Code](https://github.com/anthropics/claude-code) | `npm install -g @anthropic-ai/claude-code` | Node.js, Anthropic API key |
| [Codex CLI](https://github.com/openai/codex) | `npm install -g @openai/codex` | Node.js, OpenAI API key |
| [Aider](https://github.com/paul-gauthier/aider) | `pip install aider-chat` | Python, any supported API key |
