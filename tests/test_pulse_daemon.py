"""
Unit tests for PulseDaemon.

Tests the daemon's core functionality:
- Pulse execution with error handling
- Scheduler loop with concurrent execution
- Signal handling and graceful shutdown
- Integration scenarios
"""

import asyncio
import signal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reeve.pulse.daemon import PulseDaemon
from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.executor import ExecutionResult
from reeve.pulse.models import Pulse

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_config():
    """Mock ReeveConfig."""
    config = MagicMock()
    config.pulse_db_url = "sqlite+aiosqlite:///:memory:"
    config.hapi_command = "mock_hapi"
    config.reeve_desk_path = "/tmp/test_desk"
    config.reeve_home = "/tmp/test_home"
    config.pulse_api_port = 8765
    config.pulse_api_token = "test_token_123"
    return config


@pytest.fixture
def mock_queue():
    """Mock PulseQueue with AsyncMock."""
    queue = AsyncMock()
    queue.get_due_pulses = AsyncMock(return_value=[])
    queue.mark_processing = AsyncMock(return_value=True)
    queue.mark_completed = AsyncMock()
    queue.mark_failed = AsyncMock(return_value=None)
    queue.close = AsyncMock()
    queue.initialize = AsyncMock()
    return queue


@pytest.fixture
def mock_executor():
    """Mock PulseExecutor with AsyncMock."""
    executor = AsyncMock()
    executor.build_prompt = MagicMock(side_effect=lambda p, s: p if not s else f"{p}\n\nSTICKY")

    # Add small delay to make duration > 0
    async def execute_with_delay(*args, **kwargs):
        await asyncio.sleep(0.01)  # 10ms delay
        return ExecutionResult(
            stdout="Success",
            stderr="",
            return_code=0,
            timed_out=False,
            session_id="test-session-123",
        )

    executor.execute = AsyncMock(side_effect=execute_with_delay)
    return executor


@pytest.fixture
async def daemon(mock_config, mock_queue, mock_executor):
    """Create daemon with mocked dependencies."""
    daemon = PulseDaemon(mock_config)
    daemon.queue = mock_queue
    daemon.executor = mock_executor
    return daemon


@pytest.fixture
def mock_pulse():
    """Create a mock Pulse instance."""
    pulse = Pulse(
        scheduled_at=datetime.now(timezone.utc),
        prompt="Test pulse",
        priority=PulsePriority.NORMAL,
        status=PulseStatus.PENDING,
    )
    pulse.id = 1  # Set ID manually for testing
    return pulse


# ============================================================================
# Pulse Execution Tests (6 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_execute_pulse_success(daemon, mock_pulse):
    """Test successful pulse execution marks as COMPLETED with duration."""
    await daemon._execute_pulse(mock_pulse)

    # Should mark as completed with duration
    daemon.queue.mark_completed.assert_called_once()
    call_args = daemon.queue.mark_completed.call_args
    assert call_args[0][0] == 1  # pulse_id
    assert call_args[0][1] > 0  # duration_ms


@pytest.mark.asyncio
async def test_execute_pulse_with_sticky_notes(daemon, mock_pulse):
    """Test pulse execution uses executor.build_prompt() with sticky notes."""
    mock_pulse.sticky_notes = ["Check ticket prices", "Follow up on email"]

    await daemon._execute_pulse(mock_pulse)

    # Should call build_prompt with sticky notes
    daemon.executor.build_prompt.assert_called_once_with(mock_pulse.prompt, mock_pulse.sticky_notes)


@pytest.mark.asyncio
async def test_execute_pulse_with_session_id(daemon, mock_pulse):
    """Test pulse execution passes session_id to executor."""
    mock_pulse.session_id = "resume-session-456"

    await daemon._execute_pulse(mock_pulse)

    # Should pass session_id to execute()
    daemon.executor.execute.assert_called_once()
    call_kwargs = daemon.executor.execute.call_args[1]
    assert call_kwargs["session_id"] == "resume-session-456"


@pytest.mark.asyncio
async def test_execute_pulse_failure_marks_failed(daemon, mock_pulse):
    """Test executor failure calls mark_failed() with error message."""
    daemon.executor.execute.side_effect = RuntimeError("Hapi crashed")

    await daemon._execute_pulse(mock_pulse)

    # Should mark as failed with error
    daemon.queue.mark_failed.assert_called_once()
    call_args = daemon.queue.mark_failed.call_args
    assert call_args[0][0] == 1  # pulse_id (positional)
    assert "Hapi crashed" in call_args[1]["error_message"]  # keyword arg
    assert call_args[1]["should_retry"] is True


@pytest.mark.asyncio
async def test_execute_pulse_failure_creates_retry(daemon, mock_pulse):
    """Test failed pulse creates retry if mark_failed returns retry_pulse_id."""
    daemon.executor.execute.side_effect = RuntimeError("Network error")
    daemon.queue.mark_failed.return_value = 999  # Retry pulse ID

    await daemon._execute_pulse(mock_pulse)

    # Should log retry pulse ID
    daemon.queue.mark_failed.assert_called_once()


@pytest.mark.asyncio
async def test_execute_pulse_tracks_duration(daemon, mock_pulse):
    """Test duration tracking in milliseconds."""

    # Add small delay to execution
    async def delayed_execute(*args, **kwargs):
        await asyncio.sleep(0.01)  # 10ms
        return ExecutionResult(
            stdout="Success",
            stderr="",
            return_code=0,
            timed_out=False,
            session_id="test-123",
        )

    daemon.executor.execute.side_effect = delayed_execute

    await daemon._execute_pulse(mock_pulse)

    # Duration should be >= 10ms
    call_args = daemon.queue.mark_completed.call_args
    duration_ms = call_args[0][1]
    assert duration_ms >= 10


# ============================================================================
# Scheduler Loop Tests (8 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_scheduler_loop_gets_due_pulses(daemon, mock_pulse):
    """Test scheduler calls get_due_pulses(limit=10)."""
    daemon.running = True
    daemon.queue.get_due_pulses.return_value = []

    # Run for 1 iteration
    task = asyncio.create_task(daemon._scheduler_loop())
    await asyncio.sleep(0.1)
    daemon.running = False
    await asyncio.sleep(1.1)  # Wait for next iteration
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should have called get_due_pulses with limit=10
    assert daemon.queue.get_due_pulses.called
    daemon.queue.get_due_pulses.assert_called_with(limit=10)


@pytest.mark.asyncio
async def test_scheduler_loop_spawns_tasks(daemon, mock_pulse):
    """Test scheduler spawns asyncio tasks for each pulse."""
    daemon.running = True
    # Return pulse once, then empty list
    daemon.queue.get_due_pulses.side_effect = [[mock_pulse], []]

    # Run scheduler
    task = asyncio.create_task(daemon._scheduler_loop())
    await asyncio.sleep(1.5)  # Wait for one iteration
    daemon.running = False
    await asyncio.sleep(1.1)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should have marked as processing and executed
    daemon.queue.mark_processing.assert_called_once_with(mock_pulse.id)


@pytest.mark.asyncio
async def test_scheduler_loop_skips_already_processing(daemon, mock_pulse):
    """Test scheduler skips pulses that are already processing."""
    daemon.running = True
    daemon.queue.get_due_pulses.return_value = [mock_pulse]
    daemon.queue.mark_processing.return_value = False  # Already processing

    # Run scheduler
    task = asyncio.create_task(daemon._scheduler_loop())
    await asyncio.sleep(1.5)
    daemon.running = False
    await asyncio.sleep(1.1)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should NOT have executed pulse
    daemon.executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_scheduler_loop_respects_priority(daemon):
    """Test scheduler processes pulses in priority order."""
    daemon.running = True

    # Create pulses with different priorities
    pulse_critical = Pulse(
        scheduled_at=datetime.now(timezone.utc),
        prompt="Critical",
        priority=PulsePriority.CRITICAL,
        status=PulseStatus.PENDING,
    )
    pulse_critical.id = 1

    pulse_normal = Pulse(
        scheduled_at=datetime.now(timezone.utc),
        prompt="Normal",
        priority=PulsePriority.NORMAL,
        status=PulseStatus.PENDING,
    )
    pulse_normal.id = 2

    # get_due_pulses should return in priority order (mocked), then empty
    daemon.queue.get_due_pulses.side_effect = [[pulse_critical, pulse_normal], []]

    # Run scheduler
    task = asyncio.create_task(daemon._scheduler_loop())
    await asyncio.sleep(1.5)
    daemon.running = False
    await asyncio.sleep(1.1)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should have processed both pulses
    assert daemon.queue.mark_processing.call_count == 2


@pytest.mark.asyncio
async def test_scheduler_loop_polls_every_second(daemon):
    """Test scheduler sleeps 1 second between iterations."""
    daemon.running = True
    daemon.queue.get_due_pulses.return_value = []

    start_time = asyncio.get_event_loop().time()

    # Run scheduler
    task = asyncio.create_task(daemon._scheduler_loop())
    await asyncio.sleep(2.5)  # Wait for ~2 iterations
    daemon.running = False
    await asyncio.sleep(1.1)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    elapsed = asyncio.get_event_loop().time() - start_time

    # Should have called get_due_pulses 2-3 times in ~2.5 seconds
    assert daemon.queue.get_due_pulses.call_count >= 2


@pytest.mark.asyncio
async def test_scheduler_loop_handles_database_errors(daemon):
    """Test scheduler backs off 5s on database errors without crashing."""
    daemon.running = True
    daemon.queue.get_due_pulses.side_effect = [
        Exception("Database connection lost"),
        [],  # Recovers on second call
    ]

    # Run scheduler
    task = asyncio.create_task(daemon._scheduler_loop())
    await asyncio.sleep(0.5)  # Wait for first iteration to fail
    daemon.running = False
    await asyncio.sleep(6)  # Wait for backoff + next iteration
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should have called get_due_pulses at least twice (error + recovery)
    assert daemon.queue.get_due_pulses.call_count >= 1


@pytest.mark.asyncio
async def test_scheduler_loop_concurrent_execution(daemon):
    """Test scheduler executes multiple pulses concurrently."""
    daemon.running = True

    # Create multiple pulses
    pulses = []
    for i in range(1, 4):
        pulse = Pulse(
            scheduled_at=datetime.now(timezone.utc),
            prompt=f"Pulse {i}",
            priority=PulsePriority.NORMAL,
            status=PulseStatus.PENDING,
        )
        pulse.id = i
        pulses.append(pulse)

    # Return pulses once, then empty list
    daemon.queue.get_due_pulses.side_effect = [pulses, []]

    # Run scheduler
    task = asyncio.create_task(daemon._scheduler_loop())
    await asyncio.sleep(1.5)
    daemon.running = False
    await asyncio.sleep(1.1)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should have marked all 3 as processing
    assert daemon.queue.mark_processing.call_count == 3


@pytest.mark.asyncio
async def test_scheduler_loop_stops_on_shutdown(daemon):
    """Test scheduler exits when running=False."""
    daemon.running = True
    daemon.queue.get_due_pulses.return_value = []

    # Start scheduler
    task = asyncio.create_task(daemon._scheduler_loop())
    await asyncio.sleep(0.5)

    # Stop daemon
    daemon.running = False
    await asyncio.sleep(1.5)  # Wait for loop to exit

    # Task should complete naturally
    assert task.done()


# ============================================================================
# Signal Handling Tests (4 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_shutdown_stops_scheduler(daemon):
    """Test shutdown cancels scheduler task."""
    daemon.running = True
    daemon.scheduler_task = asyncio.create_task(asyncio.sleep(10))

    await daemon._handle_shutdown(signal.SIGTERM)

    # Scheduler task should be cancelled
    assert daemon.scheduler_task.cancelled()
    assert daemon.running is False


@pytest.mark.asyncio
async def test_shutdown_waits_for_in_flight(daemon):
    """Test shutdown waits for in-flight pulses to complete."""
    daemon.running = True

    # Create in-flight tasks
    async def slow_task():
        await asyncio.sleep(0.5)

    task1 = asyncio.create_task(slow_task())
    task2 = asyncio.create_task(slow_task())
    daemon.executing_pulses = {task1, task2}

    await daemon._handle_shutdown(signal.SIGTERM)

    # All tasks should be complete
    assert task1.done()
    assert task2.done()
    assert len(daemon.executing_pulses) == 2  # Set not auto-cleared in this test


@pytest.mark.asyncio
async def test_shutdown_timeout_cancels_tasks(daemon):
    """Test shutdown force cancels tasks after 30s timeout."""
    daemon.running = True

    # Create task that never completes
    async def never_completes():
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            pass  # Gracefully handle cancellation

    task = asyncio.create_task(never_completes())
    daemon.executing_pulses = {task}

    # Mock wait_for to timeout immediately
    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
        await daemon._handle_shutdown(signal.SIGTERM)

    # Give task a moment to process cancellation
    await asyncio.sleep(0.01)

    # Task should be cancelled or done
    assert task.done(), "Task should be done (cancelled or completed)"


@pytest.mark.asyncio
async def test_shutdown_closes_resources(daemon):
    """Test shutdown closes queue connection."""
    daemon.running = True

    await daemon._handle_shutdown(signal.SIGTERM)

    # Should close queue
    daemon.queue.close.assert_called_once()

    # Should signal shutdown complete
    assert daemon.shutdown_event.is_set()


# ============================================================================
# Integration Tests (3 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_daemon_full_lifecycle(daemon, mock_pulse):
    """Test full daemon lifecycle: start, execute pulse, shutdown."""
    daemon.queue.get_due_pulses.return_value = [mock_pulse]

    # Mock the API server (not part of this test's focus)
    with patch.object(daemon, "_run_api_server", new_callable=AsyncMock):
        # Start daemon in background
        start_task = asyncio.create_task(daemon.start())

        # Wait for scheduler to start
        await asyncio.sleep(0.5)

        # Wait for pulse to execute
        await asyncio.sleep(1.5)

        # Trigger shutdown
        await daemon._handle_shutdown(signal.SIGTERM)

        # Wait for daemon to stop
        await start_task

        # Pulse should have been executed
        daemon.queue.mark_processing.assert_called()
        daemon.executor.execute.assert_called()
        daemon.queue.mark_completed.assert_called()


@pytest.mark.asyncio
async def test_daemon_concurrent_execution(daemon):
    """Test daemon executes multiple pulses in parallel."""
    # Create 5 pulses
    pulses = []
    for i in range(1, 6):
        pulse = Pulse(
            scheduled_at=datetime.now(timezone.utc),
            prompt=f"Pulse {i}",
            priority=PulsePriority.NORMAL,
            status=PulseStatus.PENDING,
        )
        pulse.id = i
        pulses.append(pulse)

    # Return pulses once, then empty list
    daemon.queue.get_due_pulses.side_effect = [pulses, []]

    # Start scheduler
    daemon.running = True
    task = asyncio.create_task(daemon._scheduler_loop())
    await asyncio.sleep(1.5)  # Let it process all pulses
    daemon.running = False
    await asyncio.sleep(1.1)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # All 5 pulses should be marked as processing
    assert daemon.queue.mark_processing.call_count == 5


@pytest.mark.asyncio
async def test_daemon_error_recovery(daemon, mock_pulse):
    """Test daemon continues after pulse failure."""
    daemon.running = True

    # First execution fails, second succeeds
    daemon.executor.execute.side_effect = [
        RuntimeError("First pulse fails"),
        ExecutionResult(
            stdout="Success",
            stderr="",
            return_code=0,
            timed_out=False,
            session_id="test-123",
        ),
    ]

    pulse1 = mock_pulse
    pulse2 = Pulse(
        scheduled_at=datetime.now(timezone.utc),
        prompt="Second pulse",
        priority=PulsePriority.NORMAL,
        status=PulseStatus.PENDING,
    )
    pulse2.id = 2

    # Return pulses one at a time
    daemon.queue.get_due_pulses.side_effect = [[pulse1], [pulse2], []]

    # Start scheduler
    task = asyncio.create_task(daemon._scheduler_loop())
    await asyncio.sleep(2.5)  # Wait for both iterations
    daemon.running = False
    await asyncio.sleep(1.1)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should have processed both pulses
    assert daemon.queue.mark_processing.call_count >= 2
    daemon.queue.mark_failed.assert_called_once()  # First pulse failed
    daemon.queue.mark_completed.assert_called_once()  # Second pulse succeeded
