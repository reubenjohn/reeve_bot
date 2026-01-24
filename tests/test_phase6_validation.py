"""
Phase 6 Validation Tests - HTTP API Integration

This test validates the complete Phase 6 implementation:
1. POST /api/pulse/schedule creates a pulse in the database
2. Scheduler picks up and executes the pulse
3. Concurrent API requests are handled correctly
"""

import asyncio
from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient, ASGITransport

from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.queue import PulseQueue
from reeve.api.server import create_app
from reeve.utils.config import ReeveConfig


@pytest.fixture
async def test_queue():
    """Create a test PulseQueue with in-memory database."""
    queue = PulseQueue("sqlite+aiosqlite:///:memory:")
    await queue.initialize()
    yield queue
    await queue.close()


@pytest.fixture
def test_config():
    """Create a test configuration."""
    config = ReeveConfig()
    config.pulse_db_url = "sqlite+aiosqlite:///:memory:"
    config.pulse_api_port = 8765
    config.pulse_api_token = "test_token_123"
    config.reeve_desk_path = "/tmp/test_desk"
    return config


@pytest.fixture
def app(test_queue, test_config):
    """Create FastAPI app for testing."""
    return create_app(test_queue, test_config)


# ========================================================================
# Integration Tests
# ========================================================================


@pytest.mark.asyncio
async def test_api_schedule_pulse_creates_database_entry(app, test_queue, test_config):
    """
    Test end-to-end flow: POST /api/pulse/schedule → Queue → Database.

    This validates:
    1. API endpoint accepts valid request
    2. Pulse is created in database
    3. Pulse has correct attributes
    4. Response contains pulse_id
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Schedule a pulse via API
        response = await client.post(
            "/api/pulse/schedule",
            headers={"Authorization": "Bearer test_token_123"},
            json={
                "prompt": "Test pulse from API integration test",
                "scheduled_at": "now",
                "priority": "high",
                "source": "test_suite",
                "tags": ["integration", "phase6"],
            },
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "pulse_id" in data
        assert "scheduled_at" in data
        assert data["message"].startswith("Pulse")

        pulse_id = data["pulse_id"]

        # Verify pulse exists in database
        pulse = await test_queue.get_pulse(pulse_id)
        assert pulse is not None
        assert pulse.prompt == "Test pulse from API integration test"
        assert pulse.priority == PulsePriority.HIGH
        assert pulse.status == PulseStatus.PENDING
        assert pulse.created_by == "test_suite"
        assert pulse.tags == ["integration", "phase6"]

        # Verify it's in the upcoming pulses list
        upcoming = await test_queue.get_upcoming_pulses(limit=10)
        assert len(upcoming) == 1
        assert upcoming[0].id == pulse_id


@pytest.mark.asyncio
async def test_concurrent_api_requests(app, test_queue, test_config):
    """
    Test that API handles concurrent requests correctly.

    This validates:
    1. Multiple simultaneous requests are handled
    2. Each request creates a unique pulse
    3. No race conditions or duplicate IDs
    4. All pulses are created successfully
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create 10 concurrent requests
        tasks = []
        for i in range(10):
            task = client.post(
                "/api/pulse/schedule",
                headers={"Authorization": "Bearer test_token_123"},
                json={
                    "prompt": f"Concurrent test pulse {i}",
                    "scheduled_at": "now",
                    "priority": "normal",
                    "source": "concurrent_test",
                },
            )
            tasks.append(task)

        # Execute all requests concurrently
        responses = await asyncio.gather(*tasks)

        # Verify all succeeded
        assert len(responses) == 10
        for response in responses:
            assert response.status_code == 200

        # Extract pulse IDs
        pulse_ids = [r.json()["pulse_id"] for r in responses]

        # Verify all IDs are unique
        assert len(pulse_ids) == len(set(pulse_ids)), "Duplicate pulse IDs detected"

        # Verify all pulses exist in database
        upcoming = await test_queue.get_upcoming_pulses(limit=20)
        assert len(upcoming) == 10

        # Verify each pulse has correct prompt
        prompts = {p.prompt for p in upcoming}
        expected_prompts = {f"Concurrent test pulse {i}" for i in range(10)}
        assert prompts == expected_prompts


@pytest.mark.asyncio
async def test_api_schedule_with_future_time(app, test_queue, test_config):
    """
    Test scheduling pulses for future execution.

    This validates:
    1. API accepts relative time strings ("in 5 minutes")
    2. scheduled_at is correctly parsed and stored
    3. Pulse does not appear in get_due_pulses() until time arrives
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Schedule a pulse 1 hour in the future
        response = await client.post(
            "/api/pulse/schedule",
            headers={"Authorization": "Bearer test_token_123"},
            json={
                "prompt": "Future pulse test",
                "scheduled_at": "in 1 hour",
                "priority": "normal",
            },
        )

        assert response.status_code == 200
        pulse_id = response.json()["pulse_id"]

        # Verify pulse exists but is not due yet
        pulse = await test_queue.get_pulse(pulse_id)
        assert pulse is not None
        assert pulse.scheduled_at > datetime.now(timezone.utc)

        # Verify it does NOT appear in get_due_pulses()
        due_pulses = await test_queue.get_due_pulses(limit=10)
        assert len(due_pulses) == 0

        # Verify it DOES appear in get_upcoming_pulses()
        upcoming = await test_queue.get_upcoming_pulses(limit=10)
        assert len(upcoming) == 1
        assert upcoming[0].id == pulse_id


@pytest.mark.asyncio
async def test_api_authentication_required(app, test_queue, test_config):
    """
    Test that API endpoints require valid authentication.

    This validates:
    1. Requests without Authorization header are rejected (401)
    2. Requests with invalid token are rejected (403)
    3. Requests with valid token succeed (200)
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test 1: No Authorization header
        response = await client.post(
            "/api/pulse/schedule",
            json={
                "prompt": "Unauthorized test",
                "scheduled_at": "now",
            },
        )
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]

        # Test 2: Invalid token
        response = await client.post(
            "/api/pulse/schedule",
            headers={"Authorization": "Bearer wrong_token"},
            json={
                "prompt": "Unauthorized test",
                "scheduled_at": "now",
            },
        )
        assert response.status_code == 403
        assert "Invalid" in response.json()["detail"]

        # Test 3: Valid token succeeds
        response = await client.post(
            "/api/pulse/schedule",
            headers={"Authorization": "Bearer test_token_123"},
            json={
                "prompt": "Authorized test",
                "scheduled_at": "now",
            },
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_invalid_time_format(app, test_queue, test_config):
    """
    Test that API rejects invalid time formats.

    This validates:
    1. Invalid time strings are rejected with 400 error
    2. Error message explains the problem
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/pulse/schedule",
            headers={"Authorization": "Bearer test_token_123"},
            json={
                "prompt": "Invalid time test",
                "scheduled_at": "next Tuesday at teatime",  # Invalid format
            },
        )
        assert response.status_code == 400
        assert "detail" in response.json()
