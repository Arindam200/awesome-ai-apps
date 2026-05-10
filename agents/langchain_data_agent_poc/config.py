"""Domain configuration for the data agent PoC."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainConfig:
    name: str
    description: str
    tables: tuple[str, ...]
    sample_questions: tuple[str, ...]


DOMAINS: dict[str, DomainConfig] = {
    "sales": DomainConfig(
        name="sales",
        description=(
            "Revenue, order trends, product sales, customer segments, regions, "
            "channels, and inventory questions."
        ),
        tables=("orders", "customers", "products"),
        sample_questions=(
            "What is revenue by region?",
            "Which products generated the most revenue?",
            "Show monthly revenue by channel.",
            "Which products are below reorder level?",
        ),
    ),
    "support": DomainConfig(
        name="support",
        description=(
            "Support ticket volume, ticket status, priority, resolution time, "
            "categories, and customer support operations."
        ),
        tables=("support_tickets", "customers", "orders", "products"),
        sample_questions=(
            "How many open support tickets are there by priority?",
            "What is the average resolution time by ticket category?",
            "Which customer segments have the most urgent tickets?",
            "Show support tickets by status.",
        ),
    ),
}


DEFAULT_DOMAIN = "sales"

