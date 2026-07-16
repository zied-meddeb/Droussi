"""Minimal in-process background job runner.

This decouples long-running work (exam generation) from the HTTP request that
starts it: the request enqueues a coroutine and returns immediately, while the
job runs to completion on the event loop and writes its result to the database.
Clients observe progress by polling the exam row's ``status``.

Scope / limitations: jobs live only in this process, so a restart loses any
in-flight job (its exam stays ``generating`` until retried). That is acceptable
for a single free-tier instance. For horizontal scaling, swap ``spawn`` for a
durable queue (e.g. Render Key Value / Redis with arq) consumed by a dedicated
worker service — the call sites here do not need to change.
"""
import asyncio
import logging
from typing import Coroutine

logger = logging.getLogger(__name__)

# Hold strong references so fire-and-forget tasks aren't garbage-collected while
# they run (asyncio only keeps weak references to tasks).
_background_tasks: set[asyncio.Task] = set()


def _on_done(task: asyncio.Task) -> None:
    _background_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("Background job crashed: %s", exc, exc_info=exc)


def spawn(coro: Coroutine) -> asyncio.Task:
    """Schedule ``coro`` to run in the background, independent of any request."""
    task = asyncio.ensure_future(coro)
    _background_tasks.add(task)
    task.add_done_callback(_on_done)
    return task


async def drain() -> None:
    """Await all outstanding background jobs. Intended for tests and graceful
    shutdown; not used on the hot request path."""
    while _background_tasks:
        await asyncio.gather(*list(_background_tasks), return_exceptions=True)
