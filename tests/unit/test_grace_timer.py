"""Unit tests for GraceTimer."""

import asyncio

import pytest

from chitai.server.grace_timer import GraceTimer


@pytest.mark.asyncio
async def test_refresh_starts_timer():
    """Test that refresh() starts the timer."""
    callback_called = False

    async def on_expire(_timestamp):
        nonlocal callback_called
        callback_called = True

    timer = GraceTimer(grace_period_seconds=10, on_expire=on_expire)

    assert not timer.is_running
    assert timer.last_refresh is None

    timer.refresh()

    assert timer.is_running
    assert timer.last_refresh is not None
    assert not callback_called

    timer.stop()


@pytest.mark.asyncio
async def test_refresh_restarts_timer():
    """Test that refresh() restarts the timer, cancelling the previous countdown."""
    timer = GraceTimer(grace_period_seconds=0.2, on_expire=lambda _: asyncio.sleep(0))

    timer.refresh()
    first_refresh = timer.last_refresh
    assert first_refresh is not None

    await asyncio.sleep(0.05)

    timer.refresh()
    second_refresh = timer.last_refresh
    assert second_refresh is not None

    assert second_refresh > first_refresh
    assert timer.is_running

    # Wait past original expiry time but not past restarted expiry
    await asyncio.sleep(0.1)
    assert timer.is_running

    timer.stop()


@pytest.mark.asyncio
async def test_stop_stops_timer():
    """Test that stop() stops the timer."""
    timer = GraceTimer(grace_period_seconds=10, on_expire=lambda _: asyncio.sleep(0))

    timer.refresh()
    assert timer.is_running

    timer.stop()

    assert not timer.is_running


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    """Test that stop() can be called multiple times safely."""
    timer = GraceTimer(grace_period_seconds=10, on_expire=lambda _: asyncio.sleep(0))

    # Stop when never started
    timer.stop()
    assert not timer.is_running

    # Start and stop
    timer.refresh()
    timer.stop()
    assert not timer.is_running

    # Stop again
    timer.stop()
    assert not timer.is_running


@pytest.mark.asyncio
async def test_expiry_calls_callback_with_timestamp():
    """Test that timer expiry calls on_expire with the last_refresh timestamp."""
    received_timestamp = None

    async def on_expire(timestamp):
        nonlocal received_timestamp
        received_timestamp = timestamp

    timer = GraceTimer(grace_period_seconds=0.05, on_expire=on_expire)

    timer.refresh()
    expected_timestamp = timer.last_refresh

    await asyncio.sleep(0.1)

    assert received_timestamp == expected_timestamp


@pytest.mark.asyncio
async def test_expiry_clears_running_state():
    """Test that timer expiry sets is_running to False."""
    timer = GraceTimer(grace_period_seconds=0.05, on_expire=lambda _: asyncio.sleep(0))

    timer.refresh()
    assert timer.is_running

    await asyncio.sleep(0.1)

    assert not timer.is_running
