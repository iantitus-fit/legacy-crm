"""Sprint 19b — background scheduler for the automation engine.

A single asyncio task spawned in the FastAPI lifespan. On each tick it opens
a fresh database session, calls ``process_pending_steps``, and sleeps for
``interval_seconds``. Exceptions are swallowed (logged) so a transient DB
error never kills the loop.

For the volume Legacy Roofing handles (~5-15 leads/week, peak ~100
concurrent enrollments), this simple approach is more than enough — no
Celery, no Redis, no separate worker. If a white-label client outgrows it,
swap in a proper queue.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.database import SessionLocal
from app.services.automation_service import process_pending_steps

logger = logging.getLogger("legacy_crm.automation.scheduler")

DEFAULT_INTERVAL_SECONDS = 60


async def scheduler_loop(
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """Run ``process_pending_steps`` on a loop until cancelled or signalled.

    Each iteration:
      1. Opens a fresh SessionLocal (background-task style).
      2. Calls process_pending_steps and logs the count of messages emitted.
      3. Sleeps interval_seconds, respecting ``stop_event`` for prompt exit.

    The loop is exception-tolerant: anything raised by process_pending_steps
    is logged and swallowed so the next tick still runs.
    """
    logger.info(
        "automation scheduler starting (interval=%.1fs)", interval_seconds
    )
    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            try:
                db = SessionLocal()
                try:
                    logs = process_pending_steps(db)
                    if logs:
                        logger.info(
                            "automation scheduler processed %d step(s)",
                            len(logs),
                        )
                finally:
                    db.close()
            except Exception:  # pragma: no cover — exercised via tests
                logger.exception("automation scheduler tick failed")

            if stop_event is not None:
                try:
                    await asyncio.wait_for(
                        stop_event.wait(), timeout=interval_seconds
                    )
                    break
                except asyncio.TimeoutError:
                    continue
            else:
                await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("automation scheduler cancelled")
        raise
    finally:
        logger.info("automation scheduler stopped")


def start_scheduler(
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
) -> asyncio.Task:
    """Spawn the scheduler loop as an asyncio task and return its handle."""
    return asyncio.create_task(scheduler_loop(interval_seconds))
