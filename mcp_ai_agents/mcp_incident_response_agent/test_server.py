"""Offline smoke test for the mock MCP server (no LLM or credentials needed)."""
import asyncio

from fastmcp import Client

from incident_server import mcp


async def run():
    async with Client(mcp) as c:
        tools = {t.name for t in await c.list_tools()}
        assert tools == {"list_alerts", "get_service_status", "search_runbooks"}, tools
        alerts = (await c.call_tool("list_alerts", {"service": "checkout-api"})).data
        assert len(alerts) == 2
        svc = (await c.call_tool("get_service_status", {"service": "payments-db"})).data
        assert svc["status"] == "degraded"
        rb = (await c.call_tool("search_runbooks", {"query": "connection pool saturated"})).data
        assert rb[0]["runbook"] == "database-connection-pool"
    print("ok")


if __name__ == "__main__":
    asyncio.run(run())
