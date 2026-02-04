"""
Unit tests for the HTTP API server.

Tests all endpoints, authentication, validation, and error handling.
Uses mocked PulseQueue to avoid database dependencies.
"""

import os
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from reeve.api.server import create_app
from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.models import Pulse
from reeve.pulse.queue import PulseQueue
from reeve.utils.config import ReeveConfig


@pytest.fixture
def mock_queue() -> PulseQueue:
    """Create a mocked PulseQueue instance."""
    queue = MagicMock(spec=PulseQueue)

    # Mock schedule_pulse to return a pulse ID
    async def mock_schedule_pulse(*args, **kwargs):
        return 42

    queue.schedule_pulse = AsyncMock(side_effect=mock_schedule_pulse)

    # Mock get_upcoming_pulses to return sample pulses
    async def mock_get_upcoming_pulses(limit=20):
        pulse = Pulse(
            id=1,
            scheduled_at=datetime(2026, 1, 20, 9, 0, tzinfo=timezone.utc),
            prompt="Daily morning briefing: review calendar and tasks",
            priority=PulsePriority.NORMAL,
            status=PulseStatus.PENDING,
            created_by="system",
        )
        return [pulse]

    queue.get_upcoming_pulses = AsyncMock(side_effect=mock_get_upcoming_pulses)

    return queue


@pytest.fixture
def mock_config() -> ReeveConfig:
    """Create a mocked ReeveConfig instance."""
    config = MagicMock(spec=ReeveConfig)
    config.pulse_api_token = "test_token_123"
    config.pulse_db_url = "sqlite+aiosqlite:///:memory:"
    config.reeve_desk_path = "/home/user/reeve_desk"
    config.pulse_api_port = 8765
    return config


@pytest.fixture
def client(mock_queue: PulseQueue, mock_config: ReeveConfig) -> TestClient:
    """Create a test client with mocked dependencies."""
    app = create_app(mock_queue, mock_config)
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict:
    """Create valid authorization headers."""
    return {"Authorization": "Bearer test_token_123"}


# ========================================================================
# POST /api/pulse/schedule - Success Cases
# ========================================================================


def test_schedule_pulse_success_now(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test scheduling a pulse with 'now' time."""
    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "Test pulse execution right away",
            "scheduled_at": "now",
            "priority": "high",
            "source": "test",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["pulse_id"] == 42
    assert "scheduled_at" in data
    assert data["message"] == "Pulse 42 scheduled successfully"

    # Verify queue.schedule_pulse was called
    mock_queue.schedule_pulse.assert_called_once()
    call_kwargs = mock_queue.schedule_pulse.call_args.kwargs
    assert call_kwargs["prompt"] == "Test pulse execution right away"
    assert call_kwargs["priority"] == PulsePriority.HIGH
    assert call_kwargs["created_by"] == "test"


def test_schedule_pulse_success_relative_time(
    client: TestClient, auth_headers: dict, mock_queue: PulseQueue
):
    """Test scheduling a pulse with relative time ('in 2 hours')."""
    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "Follow up on user message in 2 hours",
            "scheduled_at": "in 2 hours",
            "priority": "normal",
            "source": "telegram",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["pulse_id"] == 42

    # Verify scheduled_at is a valid ISO datetime
    scheduled_at = datetime.fromisoformat(data["scheduled_at"])
    assert scheduled_at.tzinfo == timezone.utc

    # Verify queue was called
    mock_queue.schedule_pulse.assert_called_once()
    call_kwargs = mock_queue.schedule_pulse.call_args.kwargs
    assert call_kwargs["priority"] == PulsePriority.NORMAL
    assert call_kwargs["created_by"] == "telegram"


def test_schedule_pulse_success_iso_timestamp(
    client: TestClient, auth_headers: dict, mock_queue: PulseQueue
):
    """Test scheduling a pulse with ISO 8601 timestamp."""
    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "Morning briefing at specific time",
            "scheduled_at": "2026-01-20T09:00:00Z",
            "priority": "normal",
            "source": "scheduler",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["pulse_id"] == 42
    assert data["scheduled_at"] == "2026-01-20T09:00:00+00:00"

    # Verify queue was called with correct datetime
    mock_queue.schedule_pulse.assert_called_once()
    call_kwargs = mock_queue.schedule_pulse.call_args.kwargs
    assert call_kwargs["scheduled_at"] == datetime(2026, 1, 20, 9, 0, tzinfo=timezone.utc)


def test_schedule_pulse_success_with_optional_fields(
    client: TestClient, auth_headers: dict, mock_queue: PulseQueue
):
    """Test scheduling a pulse with all optional fields."""
    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "Complex pulse with all fields",
            "scheduled_at": "in 30 minutes",
            "priority": "critical",
            "session_id": "session-abc-123",
            "sticky_notes": ["Note 1", "Note 2"],
            "tags": ["urgent", "follow_up"],
            "source": "external_api",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["pulse_id"] == 42

    # Verify all fields were passed to queue
    mock_queue.schedule_pulse.assert_called_once()
    call_kwargs = mock_queue.schedule_pulse.call_args.kwargs
    assert call_kwargs["prompt"] == "Complex pulse with all fields"
    assert call_kwargs["priority"] == PulsePriority.CRITICAL
    assert call_kwargs["session_id"] == "session-abc-123"
    assert call_kwargs["sticky_notes"] == ["Note 1", "Note 2"]
    assert call_kwargs["tags"] == ["urgent", "follow_up"]
    assert call_kwargs["created_by"] == "external_api"


# ========================================================================
# POST /api/pulse/schedule - Validation Errors
# ========================================================================


def test_schedule_pulse_prompt_too_short(client: TestClient, auth_headers: dict):
    """Test that prompts shorter than 10 characters are rejected."""
    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "Short",  # Only 5 characters
            "scheduled_at": "now",
        },
        headers=auth_headers,
    )

    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data


def test_schedule_pulse_prompt_too_long(client: TestClient, auth_headers: dict):
    """Test that prompts longer than 2000 characters are rejected."""
    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "x" * 2001,  # 2001 characters
            "scheduled_at": "now",
        },
        headers=auth_headers,
    )

    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data


def test_schedule_pulse_invalid_time_format(client: TestClient, auth_headers: dict):
    """Test that invalid time strings are rejected."""
    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "This should fail due to bad time format",
            "scheduled_at": "tomorrow at noon",  # Not supported
        },
        headers=auth_headers,
    )

    assert response.status_code == 400  # Bad request
    data = response.json()
    assert "detail" in data
    assert "Could not parse time string" in data["detail"]


def test_schedule_pulse_invalid_priority(client: TestClient, auth_headers: dict):
    """Test that invalid priority values are rejected."""
    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "This should fail due to invalid priority",
            "scheduled_at": "now",
            "priority": "super_urgent",  # Not a valid priority
        },
        headers=auth_headers,
    )

    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data


# ========================================================================
# POST /api/pulse/schedule - Authentication Tests
# ========================================================================


def test_schedule_pulse_missing_auth_header(client: TestClient):
    """Test that requests without Authorization header are rejected."""
    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "This should fail due to missing auth",
            "scheduled_at": "now",
        },
    )

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "Not authenticated" in data["detail"]


def test_schedule_pulse_invalid_auth_header_format(client: TestClient):
    """Test that malformed Authorization headers are rejected."""
    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "This should fail due to malformed auth",
            "scheduled_at": "now",
        },
        headers={"Authorization": "Basic some_credentials"},  # Wrong scheme
    )

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "Not authenticated" in data["detail"]


def test_schedule_pulse_invalid_token(client: TestClient):
    """Test that invalid API tokens are rejected."""
    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "This should fail due to wrong token",
            "scheduled_at": "now",
        },
        headers={"Authorization": "Bearer wrong_token_456"},
    )

    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    assert "Invalid API token" in data["detail"]


def test_schedule_pulse_no_token_configured(mock_queue: PulseQueue):
    """Test that requests fail gracefully when API token is not configured."""
    config = MagicMock(spec=ReeveConfig)
    config.pulse_api_token = None  # No token configured
    app = create_app(mock_queue, config)
    client = TestClient(app)

    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "This should fail due to missing config",
            "scheduled_at": "now",
        },
        headers={"Authorization": "Bearer any_token"},
    )

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "not configured" in data["detail"]


# ========================================================================
# GET /api/pulse/upcoming - Success Cases
# ========================================================================


def test_list_upcoming_success(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test listing upcoming pulses."""
    response = client.get("/api/pulse/upcoming", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert len(data["pulses"]) == 1

    pulse = data["pulses"][0]
    assert pulse["id"] == 1
    assert pulse["scheduled_at"] == "2026-01-20T09:00:00+00:00"
    assert pulse["priority"] == "normal"
    assert pulse["status"] == "pending"
    assert "Daily morning briefing" in pulse["prompt"]

    # Verify queue method was called
    mock_queue.get_upcoming_pulses.assert_called_once_with(limit=20)


def test_list_upcoming_with_custom_limit(
    client: TestClient, auth_headers: dict, mock_queue: PulseQueue
):
    """Test listing upcoming pulses with custom limit."""
    response = client.get("/api/pulse/upcoming?limit=5", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "pulses" in data

    # Verify limit was passed to queue
    mock_queue.get_upcoming_pulses.assert_called_once_with(limit=5)


def test_list_upcoming_truncates_long_prompts(
    client: TestClient, auth_headers: dict, mock_queue: PulseQueue
):
    """Test that long prompts are truncated in the response."""

    # Mock a pulse with a very long prompt
    async def mock_get_upcoming_pulses_long_prompt(limit=20):
        pulse = Pulse(
            id=2,
            scheduled_at=datetime(2026, 1, 21, 10, 0, tzinfo=timezone.utc),
            prompt="x" * 150,  # 150 character prompt
            priority=PulsePriority.HIGH,
            status=PulseStatus.PENDING,
            created_by="system",
        )
        return [pulse]

    mock_queue.get_upcoming_pulses = AsyncMock(side_effect=mock_get_upcoming_pulses_long_prompt)

    response = client.get("/api/pulse/upcoming", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    pulse = data["pulses"][0]

    # Prompt should be truncated to 100 chars + "..."
    assert len(pulse["prompt"]) == 103
    assert pulse["prompt"].endswith("...")


# ========================================================================
# GET /api/pulse/upcoming - Authentication Tests
# ========================================================================


def test_list_upcoming_missing_auth(client: TestClient):
    """Test that listing upcoming pulses requires authentication."""
    response = client.get("/api/pulse/upcoming")

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


def test_list_upcoming_invalid_token(client: TestClient):
    """Test that listing upcoming pulses rejects invalid tokens."""
    response = client.get("/api/pulse/upcoming", headers={"Authorization": "Bearer wrong_token"})

    assert response.status_code == 403
    data = response.json()
    assert "Invalid API token" in data["detail"]


# ========================================================================
# GET /api/health - No Authentication Required
# ========================================================================


def test_health_check_no_auth(client: TestClient):
    """Test that health check endpoint does not require authentication."""
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "reeve-pulse-daemon"


def test_health_check_with_auth(client: TestClient, auth_headers: dict):
    """Test that health check endpoint works with authentication too."""
    response = client.get("/api/health", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


# ========================================================================
# GET /api/status - Daemon Status
# ========================================================================


def test_status_success(client: TestClient, auth_headers: dict, mock_config: ReeveConfig):
    """Test daemon status endpoint."""
    response = client.get("/api/status", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["database"] == mock_config.pulse_db_url
    assert data["desk_path"] == mock_config.reeve_desk_path
    assert data["api_port"] == mock_config.pulse_api_port


def test_status_missing_auth(client: TestClient):
    """Test that status endpoint requires authentication."""
    response = client.get("/api/status")

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


def test_status_invalid_token(client: TestClient):
    """Test that status endpoint rejects invalid tokens."""
    response = client.get("/api/status", headers={"Authorization": "Bearer wrong_token"})

    assert response.status_code == 403
    data = response.json()
    assert "Invalid API token" in data["detail"]


# ========================================================================
# Error Handling Tests
# ========================================================================


def test_schedule_pulse_queue_error(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test that queue errors are handled gracefully."""

    # Mock schedule_pulse to raise an exception
    async def mock_schedule_pulse_error(*args, **kwargs):
        raise RuntimeError("Database connection failed")

    mock_queue.schedule_pulse = AsyncMock(side_effect=mock_schedule_pulse_error)

    response = client.post(
        "/api/pulse/schedule",
        json={
            "prompt": "This should trigger an error",
            "scheduled_at": "now",
        },
        headers=auth_headers,
    )

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Failed to schedule pulse" in data["detail"]


def test_list_upcoming_queue_error(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test that queue errors on list are handled gracefully."""

    # Mock get_upcoming_pulses to raise an exception
    async def mock_get_upcoming_pulses_error(limit=20):
        raise RuntimeError("Database query failed")

    mock_queue.get_upcoming_pulses = AsyncMock(side_effect=mock_get_upcoming_pulses_error)

    response = client.get("/api/pulse/upcoming", headers=auth_headers)

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Failed to retrieve pulses" in data["detail"]


# ========================================================================
# GET /api/pulse/{pulse_id} - Pulse Detail Tests
# ========================================================================


def test_get_pulse_detail_success(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test getting full details of a specific pulse."""
    # Create a detailed pulse for the mock
    test_pulse = Pulse(
        id=123,
        scheduled_at=datetime(2026, 1, 20, 9, 0, tzinfo=timezone.utc),
        prompt="This is the full prompt that should not be truncated in the detail view",
        priority=PulsePriority.HIGH,
        status=PulseStatus.PENDING,
        session_id="session-abc-123",
        sticky_notes=["Note 1", "Note 2"],
        tags=["daily", "important"],
        created_by="telegram",
        retry_count=0,
        max_retries=3,
        created_at=datetime(2026, 1, 19, 12, 0, tzinfo=timezone.utc),
    )

    async def mock_get_pulse(pulse_id):
        if pulse_id == 123:
            return test_pulse
        return None

    mock_queue.get_pulse = AsyncMock(side_effect=mock_get_pulse)

    response = client.get("/api/pulse/123", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 123
    assert data["scheduled_at"] == "2026-01-20T09:00:00+00:00"
    # Full prompt should be returned (not truncated)
    assert data["prompt"] == "This is the full prompt that should not be truncated in the detail view"
    assert data["priority"] == "high"
    assert data["status"] == "pending"
    assert data["session_id"] == "session-abc-123"
    assert data["sticky_notes"] == ["Note 1", "Note 2"]
    assert data["tags"] == ["daily", "important"]
    assert data["created_by"] == "telegram"
    assert data["retry_count"] == 0
    assert data["max_retries"] == 3

    # Verify the queue method was called with correct ID
    mock_queue.get_pulse.assert_called_once_with(123)


def test_get_pulse_detail_not_found(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test that requesting a non-existent pulse returns 404."""
    async def mock_get_pulse(pulse_id):
        return None

    mock_queue.get_pulse = AsyncMock(side_effect=mock_get_pulse)

    response = client.get("/api/pulse/99999", headers=auth_headers)

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"]


def test_get_pulse_detail_missing_auth(client: TestClient, mock_queue: PulseQueue):
    """Test that requesting pulse detail without auth returns 401."""
    response = client.get("/api/pulse/123")

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "Not authenticated" in data["detail"]


def test_get_pulse_detail_with_execution_data(
    client: TestClient, auth_headers: dict, mock_queue: PulseQueue
):
    """Test pulse detail includes execution data for completed pulses."""
    test_pulse = Pulse(
        id=456,
        scheduled_at=datetime(2026, 1, 20, 9, 0, tzinfo=timezone.utc),
        prompt="Completed pulse with execution data",
        priority=PulsePriority.NORMAL,
        status=PulseStatus.COMPLETED,
        created_by="system",
        retry_count=0,
        max_retries=3,
        created_at=datetime(2026, 1, 19, 12, 0, tzinfo=timezone.utc),
        executed_at=datetime(2026, 1, 20, 9, 1, 30, tzinfo=timezone.utc),
        execution_duration_ms=90000,
    )

    async def mock_get_pulse(pulse_id):
        if pulse_id == 456:
            return test_pulse
        return None

    mock_queue.get_pulse = AsyncMock(side_effect=mock_get_pulse)

    response = client.get("/api/pulse/456", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["executed_at"] == "2026-01-20T09:01:30+00:00"
    assert data["execution_duration_ms"] == 90000


# ========================================================================
# GET /api/pulse/list - Pulse List Tests
# ========================================================================


def test_list_pulses_pending(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test listing pending pulses."""
    pending_pulses = [
        Pulse(
            id=1,
            scheduled_at=datetime(2026, 1, 20, 9, 0, tzinfo=timezone.utc),
            prompt="First pending pulse",
            priority=PulsePriority.HIGH,
            status=PulseStatus.PENDING,
            created_by="system",
        ),
        Pulse(
            id=2,
            scheduled_at=datetime(2026, 1, 20, 10, 0, tzinfo=timezone.utc),
            prompt="Second pending pulse",
            priority=PulsePriority.NORMAL,
            status=PulseStatus.PENDING,
            created_by="telegram",
        ),
    ]

    async def mock_get_pulses_by_status(status, limit):
        if status == "pending":
            return pending_pulses
        return []

    mock_queue.get_pulses_by_status = AsyncMock(side_effect=mock_get_pulses_by_status)

    response = client.get("/api/pulse/list?status=pending", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["pulses"]) == 2
    assert data["pulses"][0]["id"] == 1
    assert data["pulses"][0]["status"] == "pending"
    assert data["pulses"][1]["id"] == 2

    mock_queue.get_pulses_by_status.assert_called_once_with(status="pending", limit=20)


def test_list_pulses_failed(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test listing failed pulses."""
    failed_pulses = [
        Pulse(
            id=10,
            scheduled_at=datetime(2026, 1, 19, 8, 0, tzinfo=timezone.utc),
            prompt="Failed pulse with error",
            priority=PulsePriority.HIGH,
            status=PulseStatus.FAILED,
            created_by="system",
            executed_at=datetime(2026, 1, 19, 8, 1, 0, tzinfo=timezone.utc),
            error_message="Connection timeout",
        ),
    ]

    async def mock_get_pulses_by_status(status, limit):
        if status == "failed":
            return failed_pulses
        return []

    mock_queue.get_pulses_by_status = AsyncMock(side_effect=mock_get_pulses_by_status)

    response = client.get("/api/pulse/list?status=failed", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["pulses"][0]["id"] == 10
    assert data["pulses"][0]["status"] == "failed"
    assert data["pulses"][0]["error_message"] == "Connection timeout"
    assert data["pulses"][0]["executed_at"] == "2026-01-19T08:01:00+00:00"


def test_list_pulses_completed(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test listing completed pulses."""
    completed_pulses = [
        Pulse(
            id=20,
            scheduled_at=datetime(2026, 1, 18, 9, 0, tzinfo=timezone.utc),
            prompt="Successfully completed pulse",
            priority=PulsePriority.NORMAL,
            status=PulseStatus.COMPLETED,
            created_by="system",
            executed_at=datetime(2026, 1, 18, 9, 2, 0, tzinfo=timezone.utc),
        ),
    ]

    async def mock_get_pulses_by_status(status, limit):
        if status == "completed":
            return completed_pulses
        return []

    mock_queue.get_pulses_by_status = AsyncMock(side_effect=mock_get_pulses_by_status)

    response = client.get("/api/pulse/list?status=completed", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["pulses"][0]["id"] == 20
    assert data["pulses"][0]["status"] == "completed"


def test_list_pulses_overdue(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test listing overdue pulses (pending pulses scheduled in the past)."""
    overdue_pulses = [
        Pulse(
            id=30,
            scheduled_at=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),  # In the past
            prompt="Overdue pulse that was scheduled earlier",
            priority=PulsePriority.HIGH,
            status=PulseStatus.PENDING,  # Still pending but past scheduled time
            created_by="system",
        ),
    ]

    async def mock_get_pulses_by_status(status, limit):
        if status == "overdue":
            return overdue_pulses
        return []

    mock_queue.get_pulses_by_status = AsyncMock(side_effect=mock_get_pulses_by_status)

    response = client.get("/api/pulse/list?status=overdue", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["pulses"][0]["id"] == 30
    # Note: status is still "pending" in the pulse object
    assert data["pulses"][0]["status"] == "pending"

    mock_queue.get_pulses_by_status.assert_called_once_with(status="overdue", limit=20)


def test_list_pulses_all(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test listing all pulses regardless of status."""
    all_pulses = [
        Pulse(
            id=1,
            scheduled_at=datetime(2026, 1, 20, 9, 0, tzinfo=timezone.utc),
            prompt="Pending pulse",
            priority=PulsePriority.HIGH,
            status=PulseStatus.PENDING,
            created_by="system",
        ),
        Pulse(
            id=2,
            scheduled_at=datetime(2026, 1, 19, 8, 0, tzinfo=timezone.utc),
            prompt="Completed pulse",
            priority=PulsePriority.NORMAL,
            status=PulseStatus.COMPLETED,
            created_by="system",
        ),
        Pulse(
            id=3,
            scheduled_at=datetime(2026, 1, 18, 7, 0, tzinfo=timezone.utc),
            prompt="Failed pulse",
            priority=PulsePriority.LOW,
            status=PulseStatus.FAILED,
            created_by="telegram",
        ),
    ]

    async def mock_get_pulses_by_status(status, limit):
        if status == "all":
            return all_pulses
        return []

    mock_queue.get_pulses_by_status = AsyncMock(side_effect=mock_get_pulses_by_status)

    response = client.get("/api/pulse/list?status=all", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    assert data["pulses"][0]["status"] == "pending"
    assert data["pulses"][1]["status"] == "completed"
    assert data["pulses"][2]["status"] == "failed"


def test_list_pulses_limit(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test that limit parameter restricts the number of returned pulses."""
    # Create 10 pulses
    many_pulses = [
        Pulse(
            id=i,
            scheduled_at=datetime(2026, 1, 20, 9, i, tzinfo=timezone.utc),
            prompt=f"Pulse number {i}",
            priority=PulsePriority.NORMAL,
            status=PulseStatus.PENDING,
            created_by="system",
        )
        for i in range(1, 11)
    ]

    async def mock_get_pulses_by_status(status, limit):
        # Return only up to the limit
        return many_pulses[:limit]

    mock_queue.get_pulses_by_status = AsyncMock(side_effect=mock_get_pulses_by_status)

    response = client.get("/api/pulse/list?status=pending&limit=5", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 5
    assert len(data["pulses"]) == 5

    mock_queue.get_pulses_by_status.assert_called_once_with(status="pending", limit=5)


def test_list_pulses_invalid_status(client: TestClient, auth_headers: dict):
    """Test that invalid status values are rejected."""
    response = client.get("/api/pulse/list?status=invalid_status", headers=auth_headers)

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Invalid status" in data["detail"]


def test_list_pulses_invalid_limit(client: TestClient, auth_headers: dict):
    """Test that invalid limit values are rejected."""
    # Limit too high
    response = client.get("/api/pulse/list?status=pending&limit=500", headers=auth_headers)
    assert response.status_code == 400
    assert "Limit must be between 1 and 100" in response.json()["detail"]

    # Limit too low
    response = client.get("/api/pulse/list?status=pending&limit=0", headers=auth_headers)
    assert response.status_code == 400
    assert "Limit must be between 1 and 100" in response.json()["detail"]


def test_list_pulses_missing_auth(client: TestClient):
    """Test that listing pulses requires authentication."""
    response = client.get("/api/pulse/list?status=pending")

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "Not authenticated" in data["detail"]


def test_list_pulses_truncates_long_prompts(
    client: TestClient, auth_headers: dict, mock_queue: PulseQueue
):
    """Test that long prompts are truncated in the list response."""
    pulses_with_long_prompt = [
        Pulse(
            id=1,
            scheduled_at=datetime(2026, 1, 20, 9, 0, tzinfo=timezone.utc),
            prompt="x" * 150,  # 150 character prompt
            priority=PulsePriority.NORMAL,
            status=PulseStatus.PENDING,
            created_by="system",
        ),
    ]

    async def mock_get_pulses_by_status(status, limit):
        return pulses_with_long_prompt

    mock_queue.get_pulses_by_status = AsyncMock(side_effect=mock_get_pulses_by_status)

    response = client.get("/api/pulse/list?status=pending", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    # Prompt should be truncated to 100 chars + "..."
    assert len(data["pulses"][0]["prompt"]) == 103
    assert data["pulses"][0]["prompt"].endswith("...")


# ========================================================================
# GET /api/pulse/stats - Queue Statistics Tests
# ========================================================================


def test_get_pulse_stats_empty(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test queue stats with an empty database returns zeros."""
    async def mock_get_pulse_stats():
        return {
            "pending": 0,
            "overdue": 0,
            "failed": 0,
            "completed_today": 0,
            "processing": 0,
        }

    mock_queue.get_pulse_stats = AsyncMock(side_effect=mock_get_pulse_stats)

    response = client.get("/api/pulse/stats", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["pending"] == 0
    assert data["overdue"] == 0
    assert data["failed"] == 0
    assert data["completed_today"] == 0
    assert data["processing"] == 0


def test_get_pulse_stats_with_data(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test queue stats returns correct counts."""
    async def mock_get_pulse_stats():
        return {
            "pending": 5,
            "overdue": 2,
            "failed": 3,
            "completed_today": 10,
            "processing": 1,
        }

    mock_queue.get_pulse_stats = AsyncMock(side_effect=mock_get_pulse_stats)

    response = client.get("/api/pulse/stats", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["pending"] == 5
    assert data["overdue"] == 2
    assert data["failed"] == 3
    assert data["completed_today"] == 10
    assert data["processing"] == 1


def test_get_pulse_stats_missing_auth(client: TestClient):
    """Test that queue stats requires authentication."""
    response = client.get("/api/pulse/stats")

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "Not authenticated" in data["detail"]


def test_get_pulse_stats_queue_error(
    client: TestClient, auth_headers: dict, mock_queue: PulseQueue
):
    """Test that queue errors on stats are handled gracefully."""
    async def mock_get_pulse_stats_error():
        raise RuntimeError("Database query failed")

    mock_queue.get_pulse_stats = AsyncMock(side_effect=mock_get_pulse_stats_error)

    response = client.get("/api/pulse/stats", headers=auth_headers)

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Failed to retrieve stats" in data["detail"]


# ========================================================================
# GET /api/stats - Execution Statistics Tests
# ========================================================================


def test_get_execution_stats_empty(client: TestClient, auth_headers: dict, mock_queue: PulseQueue):
    """Test execution stats with no data returns zeros."""
    async def mock_get_execution_stats():
        return {
            "total_completed": 0,
            "total_failed": 0,
            "success_rate": 0.0,
            "avg_duration_ms": 0.0,
            "recent_failures": [],
        }

    mock_queue.get_execution_stats = AsyncMock(side_effect=mock_get_execution_stats)

    response = client.get("/api/stats", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total_completed"] == 0
    assert data["total_failed"] == 0
    assert data["success_rate"] == 0.0
    assert data["avg_duration_ms"] == 0.0
    assert data["recent_failures"] == []


def test_get_execution_stats_with_data(
    client: TestClient, auth_headers: dict, mock_queue: PulseQueue
):
    """Test execution stats returns correct metrics."""
    async def mock_get_execution_stats():
        return {
            "total_completed": 80,
            "total_failed": 20,
            "success_rate": 80.0,
            "avg_duration_ms": 45000.5,
            "recent_failures": [
                {
                    "id": 100,
                    "prompt": "Failed pulse 1",
                    "error_message": "Connection timeout",
                },
                {
                    "id": 101,
                    "prompt": "Failed pulse 2",
                    "error_message": "API error",
                },
            ],
        }

    mock_queue.get_execution_stats = AsyncMock(side_effect=mock_get_execution_stats)

    response = client.get("/api/stats", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total_completed"] == 80
    assert data["total_failed"] == 20
    assert data["success_rate"] == 80.0
    assert data["avg_duration_ms"] == 45000.5
    assert len(data["recent_failures"]) == 2
    assert data["recent_failures"][0]["id"] == 100
    assert data["recent_failures"][0]["error_message"] == "Connection timeout"


def test_get_execution_stats_missing_auth(client: TestClient):
    """Test that execution stats requires authentication."""
    response = client.get("/api/stats")

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "Not authenticated" in data["detail"]


def test_get_execution_stats_queue_error(
    client: TestClient, auth_headers: dict, mock_queue: PulseQueue
):
    """Test that queue errors on execution stats are handled gracefully."""
    async def mock_get_execution_stats_error():
        raise RuntimeError("Database query failed")

    mock_queue.get_execution_stats = AsyncMock(side_effect=mock_get_execution_stats_error)

    response = client.get("/api/stats", headers=auth_headers)

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Failed to retrieve execution stats" in data["detail"]
