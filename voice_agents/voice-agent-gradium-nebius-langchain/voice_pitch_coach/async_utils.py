from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")


def run_async(awaitable: Awaitable[T]) -> T:
    """Run async Gradium calls from CLI or Streamlit contexts."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, awaitable)
        return future.result()
