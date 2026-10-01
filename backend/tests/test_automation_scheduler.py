"""Sprint 19b — automation_scheduler tests.

The scheduler is a thin asyncio loop around ``process_pending_steps``. These
tests run as plain sync functions that drive an event loop manually with
``asyncio.run`` — no pytest-asyncio needed (only anyio is installed in this
codebase).
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.services import automation_scheduler


@pytest.fixture(autouse=True)
def _shim_session_local(db_session, monkeypatch):
    """Make sure the scheduler's SessionLocal() yields the test session."""

    class _SessionShim:
        def __init__(self, session):
            self._session = session

        def __call__(self):
            return self

        def close(self):
            pass

        def __getattr__(self, name):
            return getattr(self._session, name)

    shim = _SessionShim(db_session)
    monkeypatch.setattr(
        "app.services.automation_scheduler.SessionLocal", shim
    )
    yield


def test_scheduler_loop_ticks_and_stops():
    """scheduler_loop calls process_pending_steps at least once and exits
    cleanly when its stop_event is set."""
    mock_process = MagicMock(return_value=[])

    async def _run():
        stop_event = asyncio.Event()
        with patch(
            "app.services.automation_scheduler.process_pending_steps",
            mock_process,
        ):
            task = asyncio.create_task(
                automation_scheduler.scheduler_loop(
                    interval_seconds=0.05, stop_event=stop_event
                )
            )
            await asyncio.sleep(0.2)
            stop_event.set()
            await asyncio.wait_for(task, timeout=1.0)

    asyncio.run(_run())
    assert mock_process.call_count >= 1


def test_scheduler_loop_swallows_exceptions():
    """An exception in process_pending_steps must not kill the loop."""
    call_count = {"n": 0}

    def _raises_then_succeeds(db):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("boom")
        return []

    async def _run():
        stop_event = asyncio.Event()
        with patch(
            "app.services.automation_scheduler.process_pending_steps",
            side_effect=_raises_then_succeeds,
        ):
            task = asyncio.create_task(
                automation_scheduler.scheduler_loop(
                    interval_seconds=0.05, stop_event=stop_event
                )
            )
            await asyncio.sleep(0.25)
            stop_event.set()
            await asyncio.wait_for(task, timeout=1.0)

    asyncio.run(_run())
    assert call_count["n"] >= 2


def test_scheduler_loop_cancellation():
    """Cancelling the task must exit the loop cleanly."""

    async def _run():
        with patch(
            "app.services.automation_scheduler.process_pending_steps",
            return_value=[],
        ):
            task = asyncio.create_task(
                automation_scheduler.scheduler_loop(interval_seconds=60)
            )
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(_run())


def test_start_scheduler_returns_task():
    """start_scheduler returns an asyncio.Task that runs the loop."""

    async def _run():
        with patch(
            "app.services.automation_scheduler.process_pending_steps",
            return_value=[],
        ):
            task = automation_scheduler.start_scheduler(interval_seconds=60)
            assert isinstance(task, asyncio.Task)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(_run())
