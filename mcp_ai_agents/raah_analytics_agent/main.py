import asyncio
import json
import os

import streamlit as st
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import OpenAI

load_dotenv()

RAAH_MCP_URL = "https://mcp.raah.dev/mcp"
# Llama 3.3 70B via Cloudflare Workers AI — supports tool calling
CF_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"


def _get_cf_client(account_id: str, api_token: str) -> OpenAI:
    return OpenAI(
        api_key=api_token,
        base_url=f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
    )


async def run_analytics_agent(
    raah_token: str,
    cf_account_id: str,
    cf_api_token: str,
    user_query: str,
    project_id: str = "",
) -> str:
    """Connect to the Raah MCP server and answer an analytics question via Llama tool-use."""

    headers = {"Authorization": f"Bearer {raah_token}"}
    client = _get_cf_client(cf_account_id, cf_api_token)

    async with streamablehttp_client(RAAH_MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_resp = await session.list_tools()

            # Convert MCP tools to OpenAI function-calling format
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or t.name,
                        "parameters": t.inputSchema or {"type": "object", "properties": {}},
                    },
                }
                for t in tools_resp.tools
            ]

            system = (
                "You are a web analytics expert with live access to Raah Analytics data.\n\n"
                "Your workflow:\n"
                "1. Call list_tools to discover available analytics capabilities.\n"
                "2. Call describe_tool to inspect a capability's parameters before using it.\n"
                "3. Call run_tool to execute the capability and retrieve real data.\n"
                "4. Synthesise the results into clear, actionable insights.\n\n"
                "Formatting: use markdown tables for multi-row comparisons; highlight metrics "
                "outside healthy ranges (LCP > 2.5 s, CLS > 0.1, INP > 200 ms); lead with the "
                "headline finding.\n\n"
                + (
                    f"Use project_id='{project_id}' when calling run_tool capabilities."
                    if project_id
                    else "Start with whoami or run_tool list_projects to discover projects."
                )
            )

            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_query},
            ]

            for _ in range(12):
                response = client.chat.completions.create(
                    model=CF_MODEL,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )

                choice = response.choices[0]

                if choice.finish_reason == "stop":
                    return choice.message.content or "Analysis complete."

                if choice.finish_reason != "tool_calls":
                    break

                # Append assistant message with tool_calls
                messages.append(choice.message)

                # Execute each tool call via MCP
                for tc in choice.message.tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    try:
                        result = await session.call_tool(fn_name, fn_args)
                        text = "\n".join(
                            p.text if hasattr(p, "text") else json.dumps(p)
                            for p in (result.content or [])
                        )
                        tool_content = text or "(empty response)"
                    except Exception as exc:
                        tool_content = f"Error calling {fn_name}: {exc}"

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_content,
                        }
                    )

    return "Analysis complete."


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Raah Analytics Agent", page_icon="📊", layout="wide")

st.title("📊 Raah Analytics AI Agent")
st.caption(
    "Ask natural-language questions about your website performance — powered by "
    "[Raah.dev](https://raah.dev) analytics and **Llama 3.3 70B** via "
    "[Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/)."
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔑 API Keys")

    raah_token = st.text_input(
        "Raah API Token",
        type="password",
        value=os.getenv("RAAH_API_TOKEN", ""),
        help="raah.dev → Settings → API → Generate token",
    )

    cf_account_id = st.text_input(
        "Cloudflare Account ID",
        value=os.getenv("CLOUDFLARE_ACCOUNT_ID", ""),
        help="dash.cloudflare.com → right sidebar → Account ID",
    )

    cf_api_token = st.text_input(
        "Cloudflare API Token",
        type="password",
        value=os.getenv("CLOUDFLARE_API_TOKEN", ""),
        help="dash.cloudflare.com → My Profile → API Tokens → Create Token (Workers AI template)",
    )

    st.divider()
    st.header("⚙️ Project")
    project_id = st.text_input(
        "Raah Project ID (optional)",
        value=os.getenv("RAAH_PROJECT_ID", ""),
        help="Leave blank to auto-discover. Find it in the Raah dashboard URL.",
    )

# ── Quick Insight Buttons ─────────────────────────────────────────────────────
QUICK_QUERIES: dict[str, str] = {
    "📈 Site Overview": (
        "Give me a full health overview of my website: total requests, session count, "
        "error rate, and p95 latency for the last 24 hours."
    ),
    "⚡ Web Vitals": (
        "Analyse my Core Web Vitals — LCP, INP, CLS, FCP, TTFB. "
        "Which metrics are outside healthy thresholds and what is causing them?"
    ),
    "🐛 Top Errors": (
        "List the most frequent JavaScript and HTTP errors on my site. "
        "Group them by type and suggest how to fix the top three."
    ),
    "🐌 Slow Endpoints": (
        "Show the five slowest API endpoints by p95 latency. "
        "What might be causing the slowness and how can I improve them?"
    ),
    "🌍 Geo Performance": (
        "Break down my traffic and page-load latency by geography. "
        "Which regions have the worst performance and why?"
    ),
    "📊 Week-over-Week": (
        "Compare my site performance between last 7 days and the 7 days before that. "
        "Highlight any regressions or improvements."
    ),
}

st.subheader("Quick Insights")
cols = st.columns(3)
for i, (label, query_text) in enumerate(QUICK_QUERIES.items()):
    with cols[i % 3]:
        if st.button(label, use_container_width=True):
            st.session_state["prefilled_query"] = query_text

# ── Query Input ───────────────────────────────────────────────────────────────
query = st.text_area(
    "Ask anything about your analytics:",
    value=st.session_state.get("prefilled_query", ""),
    placeholder=(
        "e.g. What is the p95 latency for /api/checkout? "
        "Are there any regressions compared to last week?"
    ),
    height=110,
)

if st.button("🔍 Analyse", type="primary", use_container_width=True):
    if not raah_token:
        st.error("Please enter your Raah API token in the sidebar.")
    elif not cf_account_id or not cf_api_token:
        st.error("Please enter your Cloudflare Account ID and API token in the sidebar.")
    elif not query.strip():
        st.error("Please enter a query or click a Quick Insight button.")
    else:
        with st.spinner("Querying Raah analytics and reasoning with Llama…"):
            try:
                result = asyncio.run(
                    run_analytics_agent(
                        raah_token,
                        cf_account_id,
                        cf_api_token,
                        query.strip(),
                        project_id.strip(),
                    )
                )
                st.markdown("---")
                st.markdown("### Analysis")
                st.markdown(result)
            except Exception as exc:
                st.error(f"Error: {exc}")
