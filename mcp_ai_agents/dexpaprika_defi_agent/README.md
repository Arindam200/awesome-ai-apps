# DexPaprika DeFi Agent

> An agent that answers on-chain DEX questions (token prices, liquidity pools, OHLCV history) by calling the keyless DexPaprika MCP server.

Ask it things like "what are the top WETH pools on Ethereum by volume?" or "what is PEPE trading at, and on which chain?" and it works out which DexPaprika tools to call and reads the answer back. DexPaprika's API is keyless, so the only credential you supply is your Nebius key.

## Features

- **Keyless data source.** DexPaprika needs no API key or signup. The only credential in this project is your Nebius key.
- **Real DEX market data.** Token search, pool discovery, current prices, and OHLCV history across the chains DexPaprika covers.
- **MCP over stdio.** The agent loads the DexPaprika MCP server (`npx dexpaprika-mcp`) as its toolset, so there is no custom tool wiring to maintain.
- **Ask your own question.** Pass a question as a command-line argument, or run with no arguments for a default query.

## Tech Stack

- **Python** with `asyncio`
- **LangChain / LangGraph** for the ReAct agent loop (`create_react_agent`)
- **langchain-mcp-adapters** to load the MCP server's tools
- **DexPaprika MCP** (`dexpaprika-mcp`, keyless) as the data source
- **Nebius Token Factory** (`Qwen/Qwen3-235B-A22B-Instruct-2507` by default) for the model

## Workflow

The agent opens one persistent connection to the DexPaprika MCP server over stdio, loads its tools, and runs a standard ReAct loop. It resolves a token name or symbol to a contract address with `search` first, then calls the pool and price tools, and writes a plain-language answer. Everything on the data side is keyless.

## Getting Started

### Prerequisites

- Python 3.10+
- [Node.js](https://nodejs.org) (the DexPaprika MCP server runs through `npx`)
- A [Nebius Token Factory API key](https://tokenfactory.nebius.com/project/api-keys)

### Environment Variables

Copy `.env.example` to `.env` and add your key:

```env
NEBIUS_API_KEY="your_nebius_api_key"

# Optional, defaults to Qwen/Qwen3-235B-A22B-Instruct-2507:
# NEBIUS_MODEL="openai/gpt-oss-120b"
```

The DexPaprika side needs nothing. The API is public and keyless.

### Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/mcp_ai_agents/dexpaprika_defi_agent

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Usage

Run the default question:

```bash
python main.py
```

Or ask your own:

```bash
python main.py "Which DEX has the most liquid WETH/USDC pool on Ethereum, and what is its 24h volume?"
```

Sample run:

```
Question: What are the top 3 WETH liquidity pools on Ethereum by 24h volume, and what DEX is each on? Also give WETH's current USD price.

(agent made 3 DexPaprika tool call(s))

The top 3 WETH liquidity pools on Ethereum by 24h volume are:
1. Uniswap V3, WETH/USDC 0.05%, 24h volume $115,546,896.64
2. Uniswap V3, WETH/USDC 0.3%, 24h volume $30,334,025.60
3. Curve, WETH/stETH, 24h volume $14,129,442.68
WETH's current price is about $1,922.39.
```

(Numbers are live, so your run will differ.)

The first run downloads the DexPaprika MCP server through `npx`, so give it a few extra seconds.

## Notes

- The MCP server is pinned to `@latest` so `npx` never serves a stale cached build.
- A large, capable model handles the multi-step pool queries reliably. Very small models sometimes send numeric arguments (like a result limit) as strings, which the MCP rejects, so they can stall. `openai/gpt-oss-120b` is a good lighter alternative; set `NEBIUS_MODEL` to switch.
- More on the data source: [DexPaprika API docs](https://docs.dexpaprika.com) and the [MCP server](https://github.com/coinpaprika/dexpaprika-mcp).
