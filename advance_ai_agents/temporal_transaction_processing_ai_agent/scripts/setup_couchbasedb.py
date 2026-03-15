"""Alias for setup_couchbase.py for backward compatibility."""

from scripts.setup_couchbase import setup_couchbase
import asyncio

if __name__ == "__main__":
    asyncio.run(setup_couchbase())

