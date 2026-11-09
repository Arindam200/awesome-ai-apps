"""Synchronous, non-streaming Chat Completions instrumentation backed by local SQLite."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from contextlib import closing
from datetime import UTC, datetime
from decimal import Decimal, DecimalException, InvalidOperation
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent


def project_path(value: str | Path) -> Path:
    """Resolve example configuration against its directory, preserving absolute paths."""
    return PROJECT_DIR / Path(value).expanduser()


SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    tag TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    status TEXT NOT NULL,
    error_type TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost_usd TEXT
)
"""


def load_pricing(path: Path) -> dict[tuple[str, str], tuple[Decimal, Decimal]]:
    """Read provider/model rates in USD per million tokens, rejecting invalid prices."""
    raw = json.loads(path.read_text(encoding="utf-8-sig"), parse_float=Decimal)
    if not isinstance(raw, dict):
        raise ValueError("Pricing must be an object keyed by provider and model")
    prices = {}
    for provider, models in raw.items():
        if not isinstance(models, dict):
            raise ValueError("Each provider must contain a model-rate object")
        for model, rates in models.items():
            if not isinstance(rates, dict):
                raise ValueError("Each model must specify input and output rates")
            values = []
            for name in ["input_per_million_usd", "output_per_million_usd"]:
                value = rates.get(name)
                if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
                    raise ValueError(f"{name} must be a finite non-negative rate")
                try:
                    rate = Decimal(value)
                except InvalidOperation as error:
                    raise ValueError(f"Invalid {name}") from error
                if not rate.is_finite() or rate < 0:
                    raise ValueError(f"Invalid {name}")
                values.append(rate)
            prices[(provider, model)] = (values[0], values[1])
    return prices


def _token_count(value: Any) -> int | None:
    """Accept actual non-negative integers that fit SQLite's signed integer storage."""
    return value if type(value) is int and 0 <= value <= 2**63 - 1 else None


def load_rows(path: Path) -> list[dict[str, Any]]:
    """Read metadata without creating an empty database if the selected path is wrong."""
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM requests ORDER BY id")]


class PricingFileNotFoundError(FileNotFoundError):
    """Distinguish a missing pricing file from a database initialization error."""


class CostTracker:
    """Wrap an existing client's create method, preserving response and exception objects."""

    def __init__(self, client: Any, database: Path, provider: str, pricing: Path):
        """Load a rate snapshot and initialize the local metadata table."""
        self.client = client
        self.database = database
        self.provider = provider
        try:
            self.prices = load_pricing(pricing)
        except FileNotFoundError as error:
            raise PricingFileNotFoundError("Pricing file not found") from error
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute(SCHEMA)

    def _record(self, model: str, tag: str, start: float, response: Any, error: Exception | None):
        """Persist request metadata without replacing a provider result on storage failure."""
        try:
            self._record_metadata(model, tag, start, response, error)
        except Exception:
            # Metadata encoding and SDK usage access can fail outside SQLite's exception family.
            logging.getLogger(__name__).warning("Request metadata could not be saved")

    def _record_metadata(
        self, model: str, tag: str, start: float, response: Any, error: Exception | None
    ) -> None:
        """Calculate and persist metadata; the caller isolates all recording failures."""
        usage = getattr(response, "usage", None)
        incoming = _token_count(getattr(usage, "prompt_tokens", None))
        outgoing = _token_count(getattr(usage, "completion_tokens", None))
        rates = self.prices.get((self.provider, model))
        cost = None
        if error is None and rates is not None and incoming is not None and outgoing is not None:
            try:
                cost = str((incoming * rates[0] + outgoing * rates[1]) / Decimal(1_000_000))
            except DecimalException:
                logging.getLogger(__name__).warning("Request cost could not be estimated")
        row = (
            datetime.now(UTC).isoformat(),
            self.provider,
            model,
            tag,
            max(0, (time.perf_counter() - start) * 1000),
            "error" if error else "success",
            type(error).__name__ if error else None,
            incoming,
            outgoing,
            cost,
        )
        with closing(sqlite3.connect(self.database, timeout=5)) as connection, connection:
            connection.execute(
                "INSERT INTO requests (timestamp,provider,model,tag,latency_ms,status,"
                "error_type,"
                "input_tokens,output_tokens,estimated_cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?)",
                row,
            )

    def create(self, *, model: str, tag: str = "default", **kwargs: Any) -> Any:
        """Call chat.completions.create and record usage; streaming and async are unsupported."""
        if kwargs.get("stream"):
            raise ValueError("Streaming is unsupported; no request was sent")
        start = time.perf_counter()
        try:
            response = self.client.chat.completions.create(model=model, **kwargs)
        except Exception as error:
            self._record(model, tag, start, None, error)
            raise
        self._record(model, tag, start, response, None)
        return response
