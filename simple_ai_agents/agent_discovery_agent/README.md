![Banner](./banner.png)

# AI Agent Discovery Agent

A discovery agent that helps you find and compare AI agents across multiple registries using the [Registry Broker API](https://hol.org/registry/docs). Search agents from NANDA, MCP, Virtuals Protocol, A2A, and ERC-8004 registries in one place.

## Features

- **Universal Search**: Search AI agents across 5+ registries with a single query
- **Agent Details**: Get comprehensive information about any agent including capabilities and endpoints
- **Similar Agents**: Find alternatives and compare agents with similar functionality
- **Faceted Browsing**: Filter by registry, category, and capabilities
- **Interactive CLI**: Natural language interface powered by Agno and Nebius

## Supported Registries

| Registry | Description |
|----------|-------------|
| **NANDA** | MIT's Network for AI Networked Digital Agents |
| **MCP** | Model Context Protocol servers |
| **Virtuals** | Virtuals Protocol on-chain agents |
| **A2A** | Google's Agent-to-Agent protocol |
| **ERC-8004** | Ethereum standard for on-chain agents |

## Prerequisites

- Python 3.10 or higher
- Nebius API key from [Nebius Token Factory](https://tokenfactory.nebius.com/)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd simple_ai_agents/agent_discovery_agent
```

2. Install dependencies:

```bash
# Using pip
pip install -r requirements.txt

# Or using uv (recommended)
uv sync
```

3. Create a `.env` file with your API key:

```bash
cp .env.example .env
# Edit .env and add your NEBIUS_API_KEY
```

## Usage

Run the agent:

```bash
python main.py
```

### Example Queries

- "Find code review agents"
- "Show me trading bots on Virtuals Protocol"
- "What MCP servers are available for databases?"
- "Get details about agent [UAID]"
- "Find agents similar to [agent name]"
- "What categories of agents are available?"

## Technical Details

The agent uses:

- [Agno Framework](https://www.agno.com/) for AI agent development
- [Nebius AI](https://tokenfactory.nebius.com/) Qwen model for natural language understanding
- [Registry Broker API](https://hol.org/registry/docs) for multi-registry agent discovery

## API Reference

The Registry Broker API provides:

- `GET /api/v1/search` - Search agents across all registries
- `GET /api/v1/agents/{uaid}` - Get agent details by Universal Agent ID
- `GET /api/v1/agents/{uaid}/similar` - Find similar agents
- `GET /api/v1/search/facets` - Get available categories and filters

Full API documentation: [hol.org/registry/docs](https://hol.org/registry/docs)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License

## Acknowledgments

- [Registry Broker](https://hol.org/registry) - Universal AI Agent Index
- [Agno Framework](https://www.agno.com/)
- [Nebius Token Factory](https://tokenfactory.nebius.com/)
