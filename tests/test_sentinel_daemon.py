"""Tests for sentinel alert integration in PulseDaemon."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reeve.pulse.daemon import PulseDaemon
from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.executor import ExecutionResult
from reeve.pulse.models import Pulse


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
    config.pulse_max_concurrent = 5
    return config


@pytest.fixture
def mock_queue():
    """Mock PulseQueue with AsyncMock."""
    queue = AsyncMock()
    queue.mark_completed = AsyncMock()
    queue.mark_failed = AsyncMock(return_value=None)
    queue.close = AsyncMock()
    queue.initialize = AsyncMock()
    return queue


@pytest.fixture
def mock_executor():
    """Mock PulseExecutor that fails."""
    executor = AsyncMock()
    executor.build_prompt = MagicMock(side_effect=lambda p, s: p)
    executor.execute = AsyncMock(side_effect=RuntimeError("Hapi crashed"))
    return executor


@pytest.fixture
def mock_pulse():
    """Create a mock Pulse instance."""
    pulse = Pulse(
        scheduled_at=datetime.now(timezone.utc),
        prompt="Test pulse for sentinel",
        priority=PulsePriority.NORMAL,
        status=PulseStatus.PENDING,
    )
    pulse.id = 42
    pulse.max_retries = 3
    pulse.retry_count = 3
    return pulse


@pytest.fixture
async def daemon(mock_config, mock_queue, mock_executor):
    """Create daemon with mocked dependencies."""
    d = PulseDaemon(mock_config)
    d.queue = mock_queue
    d.executor = mock_executor
    return d


@pytest.mark.asyncio
async def test_permanent_failure_triggers_sentinel(daemon, mock_pulse):
    """Test sentinel alert sent when retries exhausted (mark_failed returns None)."""
    daemon.queue.mark_failed.return_value = None

    with patch("reeve.sentinel.send_alert") as mock_alert:
        await daemon._execute_pulse(mock_pulse)

        mock_alert.assert_called_once()
        call_args = mock_alert.call_args
        message = call_args[0][0]
        assert "failed permanently" in message
        assert "42" in message
        assert call_args[1]["cooldown_key"] == "pulse_failed_42"


@pytest.mark.asyncio
async def test_retried_failure_does_not_trigger_sentinel(daemon, mock_pulse):
    """Test sentinel alert NOT sent when retries remain."""
    daemon.queue.mark_failed.return_value = 999

    with patch("reeve.sentinel.send_alert") as mock_alert:
        await daemon._execute_pulse(mock_pulse)
        mock_alert.assert_not_called()


@pytest.mark.asyncio
async def test_sentinel_failure_does_not_crash_daemon(daemon, mock_pulse):
    """Test daemon continues even if sentinel alert raises."""
    daemon.queue.mark_failed.return_value = None

    with patch("reeve.sentinel.send_alert", side_effect=Exception("Sentinel broken")):
        await daemon._execute_pulse(mock_pulse)
        daemon.queue.mark_failed.assert_called_once()


@pytest.mark.asyncio
async def test_successful_pulse_does_not_trigger_sentinel(daemon, mock_pulse):
    """Test sentinel alert NOT sent on successful pulse execution."""

    async def success_execute(*args, **kwargs):
        await asyncio.sleep(0.01)
        return ExecutionResult(
            stdout="OK",
            stderr="",
            return_code=0,
            timed_out=False,
            session_id="test-session",
        )

    daemon.executor.execute = AsyncMock(side_effect=success_execute)
    daemon.queue.mark_completed = AsyncMock()

    with patch("reeve.sentinel.send_alert") as mock_alert:
        await daemon._execute_pulse(mock_pulse)
        mock_alert.assert_not_called()
        daemon.queue.mark_completed.assert_called_once()
