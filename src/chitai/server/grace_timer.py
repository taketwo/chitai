"""Resettable countdown timer with expiry callback."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class GraceTimer:
    """Resettable countdown timer that calls a callback on expiry.

    The timer is either running or stopped. When running, it counts down from the last
    refresh. If it reaches zero without being refreshed, it calls the on_expire
    callback.

    Parameters
    ----------
    grace_period_seconds : float
        Countdown duration in seconds
    on_expire : Callable[[datetime], Awaitable[None]]
        Async callback invoked when timer expires. Receives the last refresh timestamp.

    """

    def __init__(
        self,
        grace_period_seconds: float,
        on_expire: Callable[[datetime], Awaitable[None]],
    ) -> None:
        self.grace_period_seconds = grace_period_seconds
        self._on_expire = on_expire
        self._last_refresh: datetime | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def last_refresh(self) -> datetime | None:
        """Timestamp of last refresh, or None if never refreshed."""
        return self._last_refresh

    @property
    def is_running(self) -> bool:
        """True if the timer is currently counting down."""
        return self._task is not None and not self._task.done()

    def refresh(self) -> None:
        """Record a refresh and restart the countdown.

        Each call resets the countdown to the full grace period.
        """
        self._last_refresh = datetime.now(UTC)
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = asyncio.create_task(self._run())
        logger.debug("Grace timer refreshed")

    def stop(self) -> None:
        """Stop the timer. Idempotent."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None
        logger.debug("Grace timer stopped")

    async def _run(self) -> None:
        """Background task that waits for grace period then calls on_expire."""
        try:
            await asyncio.sleep(self.grace_period_seconds)
            logger.info("Grace period expired, calling on_expire callback")
            await self._on_expire(self._last_refresh)  # type: ignore[arg-type]
            self._task = None
        except asyncio.CancelledError:
            logger.debug("Grace timer cancelled")
            raise
