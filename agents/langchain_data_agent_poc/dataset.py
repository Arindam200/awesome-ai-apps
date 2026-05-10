"""Load the bundled CSV sample data into an in-memory SQLite database."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"

TABLE_FILES: dict[str, str] = {
    "products": "products.csv",
    "customers": "customers.csv",
    "orders": "orders.csv",
    "support_tickets": "support_tickets.csv",
}

TABLE_DESCRIPTIONS: dict[str, str] = {
    "products": "Product catalog with price, category, inventory, and reorder threshold.",
    "customers": "Customer profile table with segment, region, and signup date.",
    "orders": "Order line items with date, customer, product, quantity, channel, and status.",
    "support_tickets": "Customer support tickets with category, priority, status, and resolution hours.",
}

COLUMN_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "products": {
        "product_id": "Primary product identifier.",
        "product_name": "Human-readable product name.",
        "category": "Product category.",
        "unit_price": "Current listed unit price in USD.",
        "inventory": "Current units on hand.",
        "reorder_level": "Inventory threshold where replenishment should be considered.",
    },
    "customers": {
        "customer_id": "Primary customer identifier.",
        "customer_name": "Customer display name.",
        "segment": "Customer segment: consumer, small_business, or enterprise.",
        "region": "US sales region.",
        "signup_date": "Customer signup date as YYYY-MM-DD.",
    },
    "orders": {
        "order_id": "Primary order identifier.",
        "order_date": "Order date as YYYY-MM-DD.",
        "customer_id": "Foreign key into customers.",
        "product_id": "Foreign key into products.",
        "quantity": "Number of units ordered.",
        "unit_price": "Unit sale price in USD at order time.",
        "channel": "Sales channel: web, retail, or partner.",
        "status": "Order state such as delivered, shipped, returned, cancelled, or processing.",
    },
    "support_tickets": {
        "ticket_id": "Primary support ticket identifier.",
        "created_date": "Ticket creation date as YYYY-MM-DD.",
        "customer_id": "Foreign key into customers.",
        "category": "Support issue category.",
        "priority": "Ticket priority: low, normal, high, or urgent.",
        "status": "Ticket state: open, closed, or pending_customer.",
        "resolution_hours": "Hours to close the ticket. Open tickets use 0.0.",
    },
}


@dataclass(frozen=True)
class QueryResult:
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]


class DemoDataset:
    """Small SQLite-backed dataset for the PoC.

    The database is rebuilt in memory from CSV files each time the process starts.
    That keeps the repository free of generated database files.
    """

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._load()

    @property
    def table_names(self) -> set[str]:
        return set(TABLE_FILES)

    def schema_text(self, table_names: tuple[str, ...] | list[str] | set[str]) -> str:
        blocks: list[str] = []
        for table_name in table_names:
            columns = self._columns(table_name)
            column_lines = []
            for column in columns:
                description = COLUMN_DESCRIPTIONS.get(table_name, {}).get(column, "")
                suffix = f" - {description}" if description else ""
                column_lines.append(f"  - {column}{suffix}")
            blocks.append(
                "\n".join(
                    [
                        f"Table: {table_name}",
                        f"Description: {TABLE_DESCRIPTIONS.get(table_name, '')}",
                        "Columns:",
                        *column_lines,
                    ]
                )
            )
        return "\n\n".join(blocks)

    def execute(self, sql: str) -> QueryResult:
        cursor = self.connection.execute(sql)
        columns = [description[0] for description in cursor.description or []]
        rows = [dict(row) for row in cursor.fetchall()]
        return QueryResult(sql=sql, columns=columns, rows=rows)

    def preview(self, table_name: str, limit: int = 5) -> list[dict[str, Any]]:
        if table_name not in self.table_names:
            raise ValueError(f"Unknown table: {table_name}")
        cursor = self.connection.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def _load(self) -> None:
        for table_name, filename in TABLE_FILES.items():
            self._load_csv(table_name, self.data_dir / filename)

    def _load_csv(self, table_name: str, path: Path) -> None:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            if not reader.fieldnames:
                raise ValueError(f"{path} has no header row")

        columns = [self._quote_identifier(column) for column in reader.fieldnames]
        self.connection.execute(f"DROP TABLE IF EXISTS {table_name}")
        self.connection.execute(
            f"CREATE TABLE {table_name} ({', '.join(f'{column} TEXT' for column in columns)})"
        )

        placeholders = ", ".join("?" for _ in reader.fieldnames)
        quoted_columns = ", ".join(columns)
        values = [
            tuple(row.get(column, "") for column in reader.fieldnames)
            for row in rows
        ]
        self.connection.executemany(
            f"INSERT INTO {table_name} ({quoted_columns}) VALUES ({placeholders})",
            values,
        )
        self.connection.commit()

    def _columns(self, table_name: str) -> list[str]:
        cursor = self.connection.execute(f"PRAGMA table_info({table_name})")
        return [row["name"] for row in cursor.fetchall()]

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

