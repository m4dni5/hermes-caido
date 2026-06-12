"""Shared helper for sync wrappers.

Runs async functions synchronously and closes the aiohttp session after each
call. This is correct — asyncio.run() creates a new event loop each time, so
the singleton session can't be reused across calls anyway.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine, TypeVar

from graphql.client import close as _close_client

T = TypeVar("T")


def sync_run(coro_fn: Callable[..., Coroutine[Any, Any, T]], *args: Any, **kwargs: Any) -> T:
    """Run an async function synchronously and close the client session after."""

    async def _wrapper() -> T:
        try:
            return await coro_fn(*args, **kwargs)
        finally:
            await _close_client()

    return asyncio.run(_wrapper())
