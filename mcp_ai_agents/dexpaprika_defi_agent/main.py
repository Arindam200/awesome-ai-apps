"""DexPaprika DeFi agent.

A LangChain agent that answers on-chain DEX questions (token prices, liquidity
pools, OHLCV history) by calling the DexPaprika MCP server. The DexPaprika API
is keyless, so the only credential you need is your LLM provider key.
"""

import asyncio
import logging
import os
import sys
import warnings

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()

# create_react_agent is being renamed to langchain.agents.create_agent; the
# prebuilt helper still works and is the clearest fit for this example.
warnings.filterwarnings("ignore", message="create_react_agent has been moved")

# The DexPaprika MCP server prints a startup banner before the JSON-RPC
# handshake; the stdio client logs a harmless parse warning for it. Silence that
# so the demo output stays clean.
logging.getLogger("mcp.client.stdio").setLevel(logging.CRITICAL)

SYSTEM_PROMPT = (
    "You are a DeFi market-data assistant backed by the DexPaprika tools "
    "(on-chain DEX prices, liquidity pools, and OHLCV history).\n\n"
    "Rules:\n"
    "1. To look up a token by name or symbol (e.g. 'WETH', 'USDC'), FIRST call "
    "`search`. The token and pool tools require the on-chain contract address, "
    "not the symbol. In each search result, the token's `id` is the contract "
    "address and `chain` is the network id.\n"
    "2. Then call getTokenPools with that contract address and network to list "
    "its pools.\n"
    "3. For 'most liquid' or 'most active', rank by 24h volume (`volume_usd_24h`), "
    "not raw liquidity: a pool with huge reported liquidity but near-zero volume "
    "is inactive or malformed, so skip it.\n"
    "4. Cite the DEX name and the exact numbers you retrieved. Never invent values."
)

DEFAULT_QUESTION = (
    "What are the top 3 WETH liquidity pools on Ethereum by 24h volume, "
    "and what DEX is each on? Also give WETH's current USD price."
)


async def main() -> None:
    question = " ".join(sys.argv[1:]).strip() or DEFAULT_QUESTION

    # The keyless DexPaprika MCP server over stdio (needs Node.js). Pinning
    # @latest keeps a stale npx cache from serving an old build.
    client = MultiServerMCPClient(
        {
            "dexpaprika": {
                "command": "npx",
                "args": ["-y", "dexpaprika-mcp@latest"],
                "transport": "stdio",
            }
        }
    )

    # Keep one MCP server alive for the whole run instead of spawning a fresh
    # process on every tool call.
    async with client.session("dexpaprika") as session:
        tools = await load_mcp_tools(session)
        # gpt-4o handles the multi-step tool use reliably; set OPENAI_MODEL to a
        # cheaper model (e.g. gpt-4o-mini) if you prefer.
        model = ChatOpenAI(model=os.environ.get("OPENAI_MODEL", "gpt-4o"), temperature=0)
        agent = create_react_agent(model, tools, prompt=SYSTEM_PROMPT)
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": question}]},
            {"recursion_limit": 15},
        )

    tool_calls = sum(
        len(getattr(m, "tool_calls", []) or []) for m in result["messages"]
    )
    print(f"\nQuestion: {question}\n")
    print(f"(agent made {tool_calls} DexPaprika tool call(s))\n")
    print(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
