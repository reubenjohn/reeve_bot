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
