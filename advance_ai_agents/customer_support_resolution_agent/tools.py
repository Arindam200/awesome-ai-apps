"""LangChain tools the support agent can call."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from ingest import load_index

ROOT = Path(__file__).parent
ORDERS_PATH = ROOT / "data" / "orders.json"
TICKETS_PATH = ROOT / "data" / "tickets.json"

_kb = None


def _get_kb():
    global _kb
    if _kb is None:
        _kb = load_index()
    return _kb


@tool
def lookup_order(order_id: str, customer_email: Optional[str] = None) -> str:
    """Look up an order by its ID (e.g. 'NC-10234').

    If `customer_email` is provided, the order is only returned when the
    email matches the order's customer — use this whenever the user has
    given their email so the agent does not leak another customer's data.
    Returns a JSON string with order status, items, totals, and tracking
    info, or an error message if the order is not found / mismatched.
    """
    orders = json.loads(ORDERS_PATH.read_text())
    order = orders.get(order_id.strip().upper())
    if not order:
        return json.dumps({"error": f"Order {order_id} not found."})
    if customer_email and customer_email.lower() != order["customer_email"].lower():
        return json.dumps(
            {
                "error": "Email does not match this order. Ask the customer "
                "to confirm the email used at checkout."
            }
        )
    return json.dumps({"order_id": order_id.upper(), **order}, indent=2)


@tool
def kb_search(query: str, k: int = 4) -> str:
    """Semantic search over FAQ, refund policy, and shipping policy docs.

    Use for any question about policies, process, timing, eligibility, or
    "how do I…" — anything not specific to a single order. Returns the
    top `k` most relevant passages with their source filenames.
    """
    kb = _get_kb()
    hits = kb.similarity_search(query, k=k)
    if not hits:
        return "No relevant passages found in the knowledge base."
    blocks = []
    for i, doc in enumerate(hits, 1):
        src = doc.metadata.get("source", "unknown")
        blocks.append(f"[{i}] ({src})\n{doc.page_content.strip()}")
    return "\n\n".join(blocks)


@tool
def refund_policy_search(query: str) -> str:
    """Shortcut search restricted to the refund / returns policy.

    Use when the customer's question is clearly about refunds, returns,
    return windows, refund timing, or non-returnable items.
    """
    kb = _get_kb()
    hits = kb.similarity_search(query, k=4, filter={"source": "refund_policy.md"})
    if not hits:
        return "No relevant refund-policy passages found."
    return "\n\n".join(d.page_content.strip() for d in hits)


@tool
def create_ticket(
    summary: str,
    customer_email: str,
    priority: str = "normal",
    order_id: Optional[str] = None,
) -> str:
    """Create a human support ticket and escalate the conversation.

    Call this when the customer's request cannot be resolved with the
    available tools — for example: refund disputes, damaged items needing
    visual review, account access issues, anything requiring a human, or
    any question where the knowledge base does not contain a confident
    answer. `priority` must be one of: low, normal, high, urgent.
    """
    priority = priority.lower()
    if priority not in {"low", "normal", "high", "urgent"}:
        priority = "normal"

    ticket = {
        "ticket_id": f"TCK-{uuid.uuid4().hex[:8].upper()}",
        "summary": summary.strip(),
        "customer_email": customer_email.strip(),
        "order_id": order_id.strip().upper() if order_id else None,
        "priority": priority,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    tickets = json.loads(TICKETS_PATH.read_text())
    tickets.append(ticket)
    TICKETS_PATH.write_text(json.dumps(tickets, indent=2))
    return json.dumps(
        {
            "ticket_id": ticket["ticket_id"],
            "message": (
                f"Ticket {ticket['ticket_id']} created with priority "
                f"{ticket['priority']}. A human agent will follow up at "
                f"{ticket['customer_email']}."
            ),
        }
    )


ALL_TOOLS = [lookup_order, kb_search, refund_policy_search, create_ticket]
