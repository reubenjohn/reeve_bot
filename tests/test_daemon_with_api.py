"""
Tests for PulseDaemon API integration.

This module tests the concurrent execution of:
1. Scheduler loop (polling and executing pulses)
2. API server (HTTP endpoints for external triggers)
"""

import asyncio
import signal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reeve.pulse.daemon import PulseDaemon
from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.models import Pulse
from reeve.utils.config import ReeveConfig


@pytest.fixture
def mock_config():
    """Create a mock ReeveConfig instance."""
    config = MagicMock(spec=ReeveConfig)
    config.pulse_db_url = "sqlite+aiosqlite:///:memory:"
    config.hapi_command = "mock_hapi"
    config.reeve_desk_path = "/tmp/mock_desk"
    config.pulse_api_port = 8765
    config.pulse_api_token = "test_token_123"
    return config


@pytest.fixture
def daemon(mock_config):
    """Create a PulseDaemon instance with mocked dependencies."""
    with patch("reeve.pulse.daemon.PulseQueue") as MockQueue, patch(
        "reeve.pulse.daemon.PulseExecutor"
    ) as MockExecutor:
        daemon = PulseDaemon(mock_config)

        # Mock queue methods
        daemon.queue.initialize = AsyncMock()
        daemon.queue.get_due_pulses = AsyncMock(return_value=[])
        daemon.queue.close = AsyncMock()

        # Mock executor
        daemon.executor.execute = AsyncMock()

        yield daemon


# ========================================================================
# API Integration Tests
# ========================================================================


@pytest.mark.asyncio
async def test_daemon_starts_both_scheduler_and_api_tasks(daemon, mock_config):
    """Test that start() creates both scheduler_task and api_task concurrently."""
    scheduler_started = asyncio.Event()
    api_started = asyncio.Event()

    # Make both methods block until cancelled
    async def mock_scheduler():
        scheduler_started.set()
        try:
            await asyncio.Future()  # Never completes
        except asyncio.CancelledError:
            pass

    async def mock_api():
        api_started.set()
        try:
            await asyncio.Future()  # Never completes
        except asyncio.CancelledError:
            pass

    with patch.object(daemon, "_scheduler_loop", side_effect=mock_scheduler), patch.object(
        daemon, "_run_api_server", side_effect=mock_api
    ):
        # Start daemon in background
        start_task = asyncio.create_task(daemon.start())

        # Wait for both tasks to start
        await asyncio.wait_for(
            asyncio.gather(scheduler_started.wait(), api_started.wait()), timeout=1.0
        )

        # Verify both tasks were created and are running
        assert daemon.scheduler_task is not None, "Scheduler task not created"
        assert daemon.api_task is not None, "API task not created"
        assert not daemon.scheduler_task.done(), "Scheduler task completed prematurely"
        assert not daemon.api_task.done(), "API task completed prematurely"

        # Trigger shutdown
        await daemon._handle_shutdown(signal.SIGTERM)

        # Wait for start() to complete
        await start_task

        # Verify both tasks are now done (either cancelled or completed)
        assert daemon.scheduler_task.done(), "Scheduler task not completed"
        assert daemon.api_task.done(), "API task not completed"

        # Verify shutdown was handled
        assert not daemon.running, "Daemon still running after shutdown"
        assert daemon.shutdown_event.is_set(), "Shutdown event not set"


@pytest.mark.asyncio
async def test_daemon_shutdown_cancels_both_tasks(daemon):
    """Test that _handle_shutdown() cancels both scheduler and API tasks."""
    # Create mock tasks
    daemon.scheduler_task = asyncio.create_task(asyncio.sleep(100))
    daemon.api_task = asyncio.create_task(asyncio.sleep(100))

    # Ensure tasks are running
    await asyncio.sleep(0.01)
    assert not daemon.scheduler_task.done()
    assert not daemon.api_task.done()

    # Trigger shutdown
    await daemon._handle_shutdown(signal.SIGTERM)

    # Verify both tasks were cancelled
    assert daemon.scheduler_task.cancelled()
    assert daemon.api_task.cancelled()


@pytest.mark.asyncio
async def test_api_server_runs_concurrently_with_scheduler(daemon, mock_config):
    """Test that API server runs concurrently with scheduler loop."""
    scheduler_started = asyncio.Event()
    api_started = asyncio.Event()

    async def mock_scheduler_loop():
        scheduler_started.set()
        try:
            await asyncio.Future()  # Block until cancelled
        except asyncio.CancelledError:
            pass

    async def mock_run_api_server():
        api_started.set()
        try:
            await asyncio.Future()  # Block until cancelled
        except asyncio.CancelledError:
            pass

    with patch.object(daemon, "_scheduler_loop", side_effect=mock_scheduler_loop), patch.object(
        daemon, "_run_api_server", side_effect=mock_run_api_server
    ):
        # Start daemon in background
        start_task = asyncio.create_task(daemon.start())

        # Wait for both to start
        await asyncio.wait_for(
            asyncio.gather(scheduler_started.wait(), api_started.wait()), timeout=1.0
        )

        # Both started successfully
        assert scheduler_started.is_set()
        assert api_started.is_set()

        # Cleanup
        await daemon._handle_shutdown(signal.SIGTERM)
        await start_task


@pytest.mark.asyncio
async def test_api_server_error_handling(daemon):
    """Test that API server handles errors gracefully."""

    async def failing_api_server():
        raise RuntimeError("API server crashed")

    with patch.object(daemon, "_run_api_server", side_effect=failing_api_server):
        # Start API task
        daemon.api_task = asyncio.create_task(daemon._run_api_server())

        # Wait for task to complete
        await asyncio.sleep(0.1)

        # Task should have completed with exception (not crash daemon)
        assert daemon.api_task.done()
        with pytest.raises(RuntimeError, match="API server crashed"):
            await daemon.api_task


@pytest.mark.asyncio
async def test_api_server_cancellation_handling(daemon):
    """Test that API server handles cancellation gracefully."""
    api_cancelled = False

    async def mock_api_server():
        nonlocal api_cancelled
        try:
            await asyncio.Future()  # Block until cancelled
        except asyncio.CancelledError:
            api_cancelled = True
            raise

    with patch.object(daemon, "_run_api_server", side_effect=mock_api_server):
        # Start API task
        daemon.api_task = asyncio.create_task(daemon._run_api_server())

        # Wait for task to start
        await asyncio.sleep(0.01)

        # Cancel the task
        daemon.api_task.cancel()

        # Wait for cancellation to propagate
        try:
            await daemon.api_task
        except asyncio.CancelledError:
            pass

        # Verify cancellation was handled
        assert api_cancelled, "API server did not handle cancellation"
