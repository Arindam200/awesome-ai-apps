"""
AI Expense Tracker — chat-based expense tracking with a self-provisioning backend.

Nebius Token Factory handles natural language. Cohesivity provisions and hosts
the database. One API key in .env, everything else sets itself up.
"""

import json
import logging
import os
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import requests as http_requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cohesivity — bootstrap, provision, query
# ---------------------------------------------------------------------------

COH_BASE = "https://cohesivity.ai"
COH_HEADERS = {"User-Agent": "ai-expense-tracker/1.0"}  # WAF requires non-default UA


def _read_cohesivity(path: str = ".cohesivity") -> dict:
    """Parse the .cohesivity file and return a dict of key=value pairs."""
    cfg = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            cfg[k.strip()] = v.strip()
    return cfg


def _bootstrap() -> dict:
    """Ensure .cohesivity exists. Run the Cohesivity quickstart if not."""
    if Path(".cohesivity").exists():
        return _read_cohesivity()

    log.info("No .cohesivity found, bootstrapping Cohesivity project...")
    try:
        subprocess.run(["npx", "@cohesivity/init", "--yes"], check=True, timeout=60)
    except FileNotFoundError:
        subprocess.run(
            ["bash", "-c", "curl -fsSL https://cohesivity.ai/quickstart.sh | bash"],
            check=True, timeout=60,
        )

    if not Path(".cohesivity").exists():
        sys.exit("Bootstrap failed: .cohesivity was not created.")
    return _read_cohesivity()


def _provision(mgmt_key: str) -> None:
    """Provision a Postgres database for this tenant. Idempotent."""
    r = http_requests.post(
        f"{COH_BASE}/api/resources/postgres",
        headers={**COH_HEADERS, "Authorization": f"Bearer {mgmt_key}"},
        timeout=30,
    )
    if r.status_code != 409:  # 409 = already provisioned
        r.raise_for_status()


def _sql(app_key: str, query: str, params: list | None = None) -> list[dict]:
    """Execute a single SQL statement over Cohesivity's HTTP edge and return rows."""
    body = {"query": query}
    if params:
        body["params"] = params
    r = http_requests.post(
        f"{COH_BASE}/edge/postgres?key={app_key}",
        json=body, headers=COH_HEADERS, timeout=15,
    )
    r.raise_for_status()
    return r.json().get("rows", [])


def init_db() -> str:
    """Bootstrap, provision Postgres, and create the expenses table. Returns the application key."""
    cfg = _bootstrap()
    mgmt = cfg.get("coh_management_key", "")
    app = cfg.get("coh_application_key", "")
    if not mgmt or not app:
        sys.exit(".cohesivity is missing keys. Delete it and re-run.")
    _provision(mgmt)
    _sql(app, """
        CREATE TABLE IF NOT EXISTS expenses (
            id           BIGSERIAL PRIMARY KEY,
            amount       NUMERIC(12,2) NOT NULL,
            category     TEXT NOT NULL DEFAULT 'other',
            description  TEXT NOT NULL DEFAULT '',
            expense_date DATE NOT NULL DEFAULT CURRENT_DATE,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    return app

# ---------------------------------------------------------------------------
# Nebius LLM
# ---------------------------------------------------------------------------

NEBIUS_URL = os.getenv("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1/")
NEBIUS_MODEL = os.getenv("NEBIUS_MODEL", "meta-llama/Llama-3.3-70B-Instruct")


def _system_prompt() -> str:
    """Build the system prompt with today's date."""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return f"""\
You are an expense tracking assistant. Today is {today}.

When the user describes spending, respond with EXACTLY this JSON:
{{"action":"add","amount":<number>,"category":"<string>","description":"<string>","date":"<YYYY-MM-DD or null>"}}

Categories: food, transport, entertainment, shopping, bills, health, travel, education, other.
If no date is mentioned, set date to null. "yesterday" = {yesterday}.

When the user asks about their spending, respond with EXACTLY this JSON:
{{"action":"query","sql":"<SELECT ...>","description":"<what you're looking up>"}}

Table: expenses(id, amount NUMERIC, category TEXT, description TEXT, expense_date DATE, created_at TIMESTAMPTZ).
Use PostgreSQL syntax with $1/$2 params if needed. Only SELECT.
"this month": expense_date >= date_trunc('month', CURRENT_DATE)
"this week": expense_date >= date_trunc('week', CURRENT_DATE)

For greetings or off-topic messages, respond in plain text.\
"""


def _parse_json(text: str) -> dict | None:
    """Try to extract a JSON object from the LLM response text."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[^{}]+\}", text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None

# ---------------------------------------------------------------------------
# Streamlit app
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the Streamlit expense tracker app."""
    st.set_page_config(page_title="AI Expense Tracker", page_icon="💰")
    st.title("💰 AI Expense Tracker")
    st.caption("Tell me what you spent, or ask about your spending.")

    # Init backend on first run
    if "app_key" not in st.session_state:
        with st.spinner("Setting up backend..."):
            st.session_state["app_key"] = init_db()
    app_key = st.session_state["app_key"]

    # Sidebar: recent expenses
    try:
        recent = _sql(app_key, "SELECT * FROM expenses ORDER BY expense_date DESC, id DESC LIMIT 10")
    except Exception:
        recent = []
    if recent:
        st.sidebar.markdown("### Recent expenses")
        for e in recent:
            st.sidebar.markdown(
                f"**${float(e['amount']):.2f}** {e['category']} — {e['description']}  \n`{e['expense_date']}`"
            )
    else:
        st.sidebar.info("No expenses yet. Start by telling me what you spent!")

    # Chat
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("e.g. 'Spent $12 on lunch' or 'How much this week?'")
    if not user_input:
        return

    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # LLM
    api_key = os.getenv("NEBIUS_API_KEY", "")
    if not api_key:
        st.error("Set NEBIUS_API_KEY in your .env file.")
        st.stop()

    llm = OpenAI(base_url=NEBIUS_URL, api_key=api_key, timeout=30)
    try:
        with st.spinner("Thinking..."):
            resp = llm.chat.completions.create(
                model=NEBIUS_MODEL,
                messages=[{"role": "system", "content": _system_prompt()}, *st.session_state["messages"]],
                temperature=0.1,
            )
        reply = resp.choices[0].message.content or ""
    except Exception as e:
        st.error(f"LLM request failed: {e}")
        return

    action = _parse_json(reply)

    # Route action
    if action and action.get("action") == "add":
        amt = action.get("amount", 0)
        if not isinstance(amt, (int, float)) or amt <= 0:
            result = "Couldn't parse the amount. Could you rephrase?"
        else:
            cat = action.get("category", "other")
            desc = action.get("description", "")
            d = action.get("date")
            params = [amt, cat, desc, d] if d else [amt, cat, desc]
            q = ("INSERT INTO expenses (amount,category,description,expense_date) VALUES ($1,$2,$3,$4) RETURNING *"
                 if d else "INSERT INTO expenses (amount,category,description) VALUES ($1,$2,$3) RETURNING *")
            try:
                rows = _sql(app_key, q, params)
                row = rows[0] if rows else {}
                result = f"✅ **${amt:.2f}** in **{cat}** — \"{desc}\" ({row.get('expense_date', d or 'today')})"
            except Exception as e:
                result = f"Failed to save expense: {e}"

    elif action and action.get("action") == "query":
        sql = action.get("sql", "")
        desc = action.get("description", "Query result")
        if not sql.strip().upper().startswith("SELECT"):
            result = "I can only run read queries."
        else:
            try:
                rows = _sql(app_key, sql)
            except Exception as e:
                result = f"Query failed: {e}"
                rows = None
            if rows is not None:
                if not rows:
                    result = f"📊 **{desc}** — no data found."
                elif len(rows) == 1 and len(rows[0]) <= 3:
                    parts = [f"📊 **{desc}**"]
                    for k, v in rows[0].items():
                        parts.append(f"**{k}:** ${v:,.2f}" if isinstance(v, (int, float)) else f"**{k}:** {v}")
                    result = "\n\n".join(parts)
                else:
                    hdrs = list(rows[0].keys())
                    lines = [f"📊 **{desc}**\n", "| " + " | ".join(hdrs) + " |", "| " + " | ".join(["---"] * len(hdrs)) + " |"]
                    for r in rows[:20]:
                        lines.append("| " + " | ".join(str(r.get(h, "")) for h in hdrs) + " |")
                    result = "\n".join(lines)
    else:
        result = reply

    st.session_state["messages"].append({"role": "assistant", "content": result})
    with st.chat_message("assistant"):
        st.markdown(result)


if __name__ == "__main__":
    main()
