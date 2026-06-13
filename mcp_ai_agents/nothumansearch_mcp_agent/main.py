import argparse
import asyncio
import json
import os
from typing import Any

import httpx


DEFAULT_MCP_URL = "https://nothumansearch.ai/mcp"


class NotHumanSearchMCP:
    def __init__(self, url: str = DEFAULT_MCP_URL) -> None:
        self.url = url
        self._next_id = 1

    async def call_rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params

        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(self.url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            raise RuntimeError(json.dumps(data["error"], indent=2))
        return data["result"]

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self.call_rpc("tools/list", {})
        return result["tools"]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.call_rpc(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )


async def run(query: str, limit: int, verify_url: str | None, mcp_url: str) -> None:
    client = NotHumanSearchMCP(mcp_url)

    tools = await client.list_tools()
    print(f"Connected to {mcp_url}")
    print("Available NHS tools:", ", ".join(tool["name"] for tool in tools))
    print()

    search_result = await client.call_tool(
        "search_agents",
        {
            "query": query,
            "limit": limit,
        },
    )
    print(f"Top agent-ready sites for: {query}")
    for item in search_result.get("structuredContent", {}).get("results", []):
        signals = [
            label
            for label, enabled in [
                ("llms.txt", item.get("has_llms_txt")),
                ("OpenAPI", item.get("has_openapi")),
                ("API", item.get("has_structured_api")),
                ("MCP", item.get("has_mcp_server")),
            ]
            if enabled
        ]
        print(
            f"- {item['name']} ({item['domain']}) "
            f"score={item['agentic_score']}/100 signals={', '.join(signals) or 'none'}"
        )
        print(f"  {item['url']}")
        print(f"  {item['description']}")

    if verify_url:
        print()
        print(f"Verifying MCP endpoint: {verify_url}")
        verify_result = await client.call_tool("verify_mcp", {"url": verify_url})
        text_blocks = verify_result.get("content", [])
        if text_blocks:
            print(text_blocks[0].get("text", "").strip())
        else:
            print(json.dumps(verify_result.get("structuredContent", verify_result), indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search agent-ready sites and verify MCP endpoints through Not Human Search."
    )
    parser.add_argument("--query", default="payment api", help="Search query for agent-ready tools.")
    parser.add_argument("--limit", type=int, default=5, help="Number of search results to show.")
    parser.add_argument("--verify-url", help="Optional MCP endpoint URL to verify.")
    parser.add_argument(
        "--mcp-url",
        default=os.getenv("NHS_MCP_URL", DEFAULT_MCP_URL),
        help="Not Human Search MCP endpoint.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run(args.query, args.limit, args.verify_url, args.mcp_url))
