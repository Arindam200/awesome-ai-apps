# DeFi Portfolio Analyst Agent

> An AI-powered DeFi portfolio analyst that provides real-time crypto prices, multi-chain wallet balances, and DEX swap quotes using the defi-mcp server.

An interactive agent that connects to the [defi-mcp](https://github.com/OzorOwn/defi-mcp) MCP server to analyze cryptocurrency portfolios, track prices, check wallet balances across 9 blockchains, and get DEX quotes. Built with the OpenAI Agents SDK.

## Features

- **Real-Time Prices**: Get current prices for 275+ cryptocurrencies
- **Multi-Chain Wallets**: Check balances across Ethereum, Solana, Polygon, Arbitrum, Optimism, BSC, Avalanche, Base, and Fantom
- **DEX Quotes**: Get swap quotes from Jupiter (Solana) and Li.Fi (EVM cross-chain)
- **Token Search**: Search for tokens by name or symbol
- **Portfolio Analysis**: Analyze portfolio allocation, value, and diversification
- **Interactive CLI**: Chat-based interface for natural language queries

## Tech Stack

- **Python**: Core programming language
- **OpenAI Agents SDK**: For agent orchestration and MCP integration
- **defi-mcp**: MCP server providing 12 DeFi tools (prices, wallets, DEX, search)
- **OpenAI / Any LLM**: For language model access (supports any OpenAI-compatible API)

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for running the MCP server via npx)
- An OpenAI API key (or any OpenAI-compatible LLM provider)

### Environment Variables

Create a `.env` file in the project directory:

```env
# Use OpenAI (default)
OPENAI_API_KEY=your_openai_api_key

# Or use any OpenAI-compatible provider:
# LLM_BASE_URL=https://api.tokenfactory.nebius.com/v1
# NEBIUS_API_KEY=your_nebius_api_key
# LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
```

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/mcp_ai_agents/defi_mcp_agent
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Run the agent:**

   ```bash
   python main.py
   ```

2. **Ask questions in natural language:**

   ```
   You: What are the current prices of BTC, ETH, and SOL?
   You: Check the balance of 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 on Ethereum
   You: Get a swap quote for 1 SOL to USDC on Jupiter
   You: Search for tokens related to 'pepe'
   You: Analyze a portfolio: 2 BTC, 10 ETH, 100 SOL
   ```

3. **Type `quit` to exit.**

## Available MCP Tools

The defi-mcp server exposes 12 tools to the agent:

| Tool | Description |
|------|-------------|
| `get-crypto-prices` | Get current prices for one or more cryptocurrencies |
| `get-wallet-balance` | Check wallet balance on any of 9 supported chains |
| `get-token-info` | Get detailed information about a specific token |
| `search-tokens` | Search for tokens by name or symbol |
| `get-dex-quote-jupiter` | Get swap quotes on Solana via Jupiter |
| `get-dex-quote-lifi` | Get cross-chain swap quotes via Li.Fi |
| `get-trending-tokens` | Get currently trending tokens |
| `get-token-price-history` | Get historical price data |
| `get-gas-prices` | Get current gas prices on EVM chains |
| `get-chain-info` | Get information about supported chains |
| `get-protocol-tvl` | Get TVL data for DeFi protocols |
| `get-token-holders` | Get top holder data for tokens |

## Project Structure

```
defi_mcp_agent/
├── main.py              # Agent application with interactive CLI
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
└── README.md            # Project documentation
```

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/Arindam200/awesome-ai-apps/blob/main/LICENSE) file for details.

## Acknowledgments

- [defi-mcp](https://github.com/OzorOwn/defi-mcp) for the DeFi MCP server
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) for the agent framework
