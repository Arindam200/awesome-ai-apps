"""Offline smoke test for the mock evidence MCP server (no LLM or credentials)."""
import asyncio

from fastmcp import Client

from evidence_server import mcp


async def run():
    async with Client(mcp) as c:
        tools = {t.name for t in await c.list_tools()}
        assert {"list_controls", "get_policy_documents", "get_tickets", "get_deploy_logs", "get_access_reviews"} <= tools
        assert len((await c.call_tool("list_controls", {})).data) == 3
        logs = (await c.call_tool("get_deploy_logs", {})).data
        assert any(l["change_ticket"] is None for l in logs)
        tickets = (await c.call_tool("get_tickets", {"ticket_type": "change"})).data
        assert any(t["author"] == t["approved_by"] for t in tickets)
    print("ok")


if __name__ == "__main__":
    asyncio.run(run())
