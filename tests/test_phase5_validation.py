"""
Phase 5 validation test: End-to-end Pulse Daemon integration.

This test validates the complete Phase 5 implementation:
1. Daemon starts successfully
2. Scheduler polls for due pulses
3. Pulses execute via PulseExecutor
4. Database updated correctly (COMPLETED)
5. Graceful shutdown works
"""

import asyncio
import signal
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from reeve.pulse.daemon import PulseDaemon
from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.executor import ExecutionResult
from reeve.pulse.models import Base, Pulse
from reeve.pulse.queue import PulseQueue


@pytest.mark.asyncio
async def test_phase5_integration():
    """
    End-to-end validation of Phase 5: Pulse Daemon.

    This test validates:
    1. Daemon starts successfully with in-memory database
    2. Scheduler polls for due pulses every 1 second
    3. Pulses execute via PulseExecutor (mocked)
    4. Database updated correctly (status: COMPLETED, duration tracked)
    5. Graceful shutdown works (waits for in-flight, closes resources)
    """
    # ========================================================================
    # Setup: In-memory database and queue
    # ========================================================================
    db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(db_url, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create queue
    queue = PulseQueue(db_url)
    await queue.initialize()

    # Schedule a test pulse (due immediately)
    pulse_id = await queue.schedule_pulse(
        scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=1),  # Already due
        prompt="Test pulse for Phase 5 validation",
        priority=PulsePriority.NORMAL,
        sticky_notes=["Validation test note"],
    )

    # ========================================================================
    # Setup: Mock config and executor
    # ========================================================================
    mock_config = MagicMock()
    mock_config.pulse_db_url = db_url
    mock_config.hapi_command = "mock_hapi"
    mock_config.reeve_desk_path = "/tmp/test_desk"
    mock_config.reeve_home = "/tmp/test_home"
    mock_config.pulse_api_port = 8765
    mock_config.pulse_api_token = "test_token"

    # Create daemon with real queue but mocked executor
    daemon = PulseDaemon(mock_config)
    daemon.queue = queue  # Use real queue instead of mock

    # Mock executor to avoid actual Hapi execution
    mock_executor = AsyncMock()
    mock_executor.build_prompt = MagicMock(
        side_effect=lambda p, s: f"{p}\n\nSTICKY: {s}" if s else p
    )

    # Add delay to make duration > 0
    async def execute_with_delay(*args, **kwargs):
        await asyncio.sleep(0.01)  # 10ms delay
        return ExecutionResult(
            stdout="Phase 5 validation success",
            stderr="",
            return_code=0,
            timed_out=False,
            session_id="phase5-validation-session",
        )

    mock_executor.execute = AsyncMock(side_effect=execute_with_delay)
    daemon.executor = mock_executor

    # ========================================================================
    # Test: Start daemon and execute pulse
    # ========================================================================
    # Mock the API server since this test is for Phase 5 (not Phase 6)
    with patch.object(daemon, "_run_api_server", new_callable=AsyncMock):
        try:
            # Start daemon in background
            start_task = asyncio.create_task(daemon.start())

            # Wait for scheduler to start and process pulse
            await asyncio.sleep(2.0)  # Give it time to poll and execute

            # Verify executor was called
            assert mock_executor.build_prompt.called, "Executor.build_prompt() not called"
            assert mock_executor.execute.called, "Executor.execute() not called"

            # Verify prompt building with sticky notes
            build_prompt_call = mock_executor.build_prompt.call_args
            assert build_prompt_call[0][0] == "Test pulse for Phase 5 validation"
            assert build_prompt_call[0][1] == ["Validation test note"]

            # ========================================================================
            # Test: Verify database updated correctly
            # ========================================================================
            executed_pulse = await queue.get_pulse(pulse_id)
            assert executed_pulse is not None, "Pulse not found in database"
            assert (
                executed_pulse.status == PulseStatus.COMPLETED
            ), f"Pulse status should be COMPLETED, got {executed_pulse.status}"
            assert executed_pulse.executed_at is not None, "executed_at not set"
            assert executed_pulse.execution_duration_ms is not None, "execution_duration_ms not set"
            assert executed_pulse.execution_duration_ms > 0, "execution_duration_ms should be positive"

            # ========================================================================
            # Test: Graceful shutdown
            # ========================================================================
            # Trigger shutdown via signal handler
            await daemon._handle_shutdown(signal.SIGTERM)

            # Wait for daemon to stop
            await asyncio.wait_for(start_task, timeout=5.0)

            # Verify shutdown completed
            assert daemon.shutdown_event.is_set(), "Shutdown event not set"
            assert daemon.running is False, "Daemon still running after shutdown"

            # ========================================================================
            # Test: Resources closed properly
            # ========================================================================
            # Queue should be closed (can't verify directly, but no errors should occur)

        finally:
            # Cleanup
            await queue.close()
            await engine.dispose()


@pytest.mark.asyncio
async def test_phase5_validation_summary():
    """
    Summary validation: Verify all Phase 5 components exist and are importable.

    This test ensures:
    1. PulseDaemon class exists and has required methods
    2. Logging configuration exists
    3. Entry point exists (__main__.py)
    """
    # Test 1: PulseDaemon class
    from reeve.pulse.daemon import PulseDaemon

    assert hasattr(PulseDaemon, "__init__"), "PulseDaemon.__init__() missing"
    assert hasattr(PulseDaemon, "_execute_pulse"), "PulseDaemon._execute_pulse() missing"
    assert hasattr(PulseDaemon, "_scheduler_loop"), "PulseDaemon._scheduler_loop() missing"
    assert hasattr(
        PulseDaemon, "_register_signal_handlers"
    ), "PulseDaemon._register_signal_handlers() missing"
    assert hasattr(PulseDaemon, "_handle_shutdown"), "PulseDaemon._handle_shutdown() missing"
    assert hasattr(PulseDaemon, "start"), "PulseDaemon.start() missing"

    # Test 2: Logging configuration
    from reeve.utils.logging import setup_logging

    assert callable(setup_logging), "setup_logging() not callable"

    # Test 3: Entry point
    import importlib.util

    spec = importlib.util.find_spec("reeve.pulse.__main__")
    assert spec is not None, "__main__.py not found in reeve.pulse package"
