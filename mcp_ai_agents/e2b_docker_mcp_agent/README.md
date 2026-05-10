# E2B MCP Python Demo with OpenAI Agents SDK

A Python demonstration of using [E2B](https://e2b.dev) with GitHub and Notion MCP (Model Context Protocol) servers, powered by the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/mcp/).

## Overview

This demo shows how to:

- Create an E2B sandbox with MCP server support
- Configure GitHub and Notion MCP servers
- Use the OpenAI Agents SDK to connect to E2B's MCP Gateway
- Build an AI agent that can interact with GitHub and Notion APIs
- Automate tasks across GitHub and Notion using natural language

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager 
- E2B API key from [e2b.dev/dashboard](https://e2b.dev/dashboard)
- OpenAI API key from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- GitHub Personal Access Token from [github.com/settings/tokens](https://github.com/settings/tokens)
  - Required scopes: `repo`, `read:user`, `read:org`
- Notion Integration Token from [notion.so/profile/integrations](https://www.notion.so/profile/integrations)
  - Remember to share pages/databases with your integration

## Setup

1. **Install uv**
Follow the instructions [here](https://docs.astral.sh/uv/install.sh) to install uv.

2. **Install dependencies**
```bash
uv sync
```

3. **Set up environment variables**
Create a `.env` file in the root of the project with the following keys:
```
E2B_API_KEY=your_e2b_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
NOTION_TOKEN=your_notion_integration_token_here
GITHUB_TOKEN=your_github_personal_access_token_here
NEBIUS_API_KEY=your_nebius_api_key_here
```

## Usage

Run the demo:
```bash
uv run main.py
```

## What It Does

The demo will:

1. Create an E2B sandbox with MCP servers configured
2. Connect to the E2B MCP Gateway using the OpenAI Agents SDK
3. Create an AI agent with access to GitHub and Notion tools
4. Execute a sample task that:
   - Lists your GitHub repositories
   - Creates a Notion page summarizing your top 3 repositories by stars

## How It Works

The implementation uses:

- **E2B Sandbox**: Provides a secure, isolated environment for the MCP servers
- **E2B MCP Gateway**: Exposes GitHub and Notion MCP servers via HTTP
- **OpenAI Agents SDK**: Connects to the MCP Gateway using `MCPServerStreamableHttp`
- **AI Agent**: Uses Nebius token factory's models to understand tasks and call the appropriate MCP tools

## References

- [E2B MCP Quickstart](https://e2b.dev/docs/mcp/quickstart)
- [OpenAI Agents SDK MCP Documentation](https://openai.github.io/openai-agents-python/mcp/)