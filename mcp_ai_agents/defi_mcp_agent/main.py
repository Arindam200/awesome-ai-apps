import asyncio
import os
from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    Runner,
    set_tracing_disabled,
)
from agents.mcp import MCPServer, MCPServerStdio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("NEBIUS_API_KEY")
base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")

client = AsyncOpenAI(base_url=base_url, api_key=api_key)
set_tracing_disabled(disabled=True)


async def run(mcp_server: MCPServer):
    agent = Agent(
        name="DeFi Portfolio Analyst",
        instructions="""You are a DeFi portfolio analyst with access to real-time crypto market data.

You can:
- Look up current prices for any cryptocurrency
- Check wallet balances across 9 blockchains (Ethereum, Solana, Polygon, Arbitrum, Optimism, BSC, Avalanche, Base, Fantom)
- Get DEX swap quotes from Jupiter (Solana) and Li.Fi (EVM chains)
- Search for tokens by name or symbol

When analyzing a portfolio:
1. First get the current prices of requested tokens
2. If a wallet address is provided, check balances across relevant chains
3. Calculate total portfolio value and allocation percentages
4. Provide insights on diversification and market trends

Always format currency values with $ signs and use commas for thousands.
Present data in clear, organized tables when possible.""",
        mcp_servers=[mcp_server],
        model=OpenAIChatCompletionsModel(
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            openai_client=client,
        ),
    )

    print("\nDeFi Portfolio Analyst Ready!")
    print("=" * 50)
    print("Example queries:")
    print("  - What are the current prices of BTC, ETH, and SOL?")
    print("  - Check the balance of 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 on Ethereum")
    print("  - Get a swap quote for 1 SOL to USDC on Jupiter")
    print("  - Search for tokens related to 'pepe'")
    print("  - Analyze a portfolio: 2 BTC, 10 ETH, 100 SOL")
    print("\nType 'quit' to exit.\n")

    while True:
        query = input("You: ").strip()
        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        print("\nAnalyzing...\n")
        try:
            result = await Runner.run(starting_agent=agent, input=query)
            print(result.final_output)
            print()
        except Exception as e:
            print(f"Error: {e}\n")


async def main():
    print("DeFi Portfolio Analyst")
    print("-" * 30)
    print("Connecting to defi-mcp server...\n")

    async with MCPServerStdio(
        cache_tools_list=True,
        params={
            "command": "npx",
            "args": ["-y", "defi-mcp@latest"],
        },
    ) as server:
        await run(server)


if __name__ == "__main__":
    asyncio.run(main())
