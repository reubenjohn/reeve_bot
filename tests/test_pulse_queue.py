"""
Unit tests for PulseQueue

Tests all queue operations including CRUD, priority ordering, retry logic, and edge cases.
Uses in-memory SQLite database for fast, isolated testing.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.queue import PulseQueue


@pytest.fixture(scope="function")
async def queue():
    """Create a PulseQueue with in-memory database for testing."""
    q = PulseQueue("sqlite+aiosqlite:///:memory:")
    await q.initialize()
    yield q
    await q.close()


@pytest.mark.asyncio
async def test_schedule_pulse(queue):
    """Test basic pulse scheduling."""
    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=1)

    pulse_id = await queue.schedule_pulse(
        scheduled_at=future,
        prompt="Test pulse",
        priority=PulsePriority.NORMAL,
        tags=["test"],
    )

    assert isinstance(pulse_id, int)
    assert pulse_id > 0

    # Verify pulse was created
    pulse = await queue.get_pulse(pulse_id)
    assert pulse is not None
    assert pulse.prompt == "Test pulse"
    assert pulse.priority == PulsePriority.NORMAL
    assert pulse.status == PulseStatus.PENDING
    assert pulse.tags == ["test"]


@pytest.mark.asyncio
async def test_schedule_pulse_with_all_fields(queue):
    """Test pulse scheduling with all optional fields."""
    now = datetime.now(timezone.utc)

    pulse_id = await queue.schedule_pulse(
        scheduled_at=now,
        prompt="Comprehensive test",
        priority=PulsePriority.HIGH,
        session_link="https://hapi.example.com/session/123",
        sticky_notes=["Remember to check email", "Follow up on PR"],
        tags=["urgent", "email"],
        created_by="test_suite",
        max_retries=5,
    )

    pulse = await queue.get_pulse(pulse_id)
    assert pulse.session_link == "https://hapi.example.com/session/123"
    assert pulse.sticky_notes == ["Remember to check email", "Follow up on PR"]
    assert pulse.tags == ["urgent", "email"]
    assert pulse.created_by == "test_suite"
    assert pulse.max_retries == 5


@pytest.mark.asyncio
async def test_get_due_pulses_empty(queue):
    """Test getting due pulses when queue is empty."""
    pulses = await queue.get_due_pulses()
    assert pulses == []


@pytest.mark.asyncio
async def test_get_due_pulses(queue):
    """Test retrieving due pulses."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=5)

    # Schedule some pulses
    await queue.schedule_pulse(scheduled_at=past, prompt="Due pulse 1")
    await queue.schedule_pulse(scheduled_at=past, prompt="Due pulse 2")
    await queue.schedule_pulse(scheduled_at=now + timedelta(hours=1), prompt="Future pulse")

    # Get due pulses
    due = await queue.get_due_pulses()
    assert len(due) == 2
    assert all(p.scheduled_at <= now for p in due)


@pytest.mark.asyncio
async def test_priority_ordering(queue):
    """Test that pulses are returned in priority order."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=5)

    # Schedule pulses in random priority order
    low_id = await queue.schedule_pulse(
        scheduled_at=past, prompt="Low priority", priority=PulsePriority.LOW
    )
    critical_id = await queue.schedule_pulse(
        scheduled_at=past, prompt="Critical priority", priority=PulsePriority.CRITICAL
    )
    normal_id = await queue.schedule_pulse(
        scheduled_at=past, prompt="Normal priority", priority=PulsePriority.NORMAL
    )
    high_id = await queue.schedule_pulse(
        scheduled_at=past, prompt="High priority", priority=PulsePriority.HIGH
    )
    deferred_id = await queue.schedule_pulse(
        scheduled_at=past, prompt="Deferred priority", priority=PulsePriority.DEFERRED
    )

    # Get due pulses - should be ordered by priority
    due = await queue.get_due_pulses(limit=10)
    assert len(due) == 5

    # Verify order: CRITICAL, HIGH, NORMAL, LOW, DEFERRED
    assert due[0].id == critical_id
    assert due[0].priority == PulsePriority.CRITICAL
    assert due[1].id == high_id
    assert due[1].priority == PulsePriority.HIGH
    assert due[2].id == normal_id
    assert due[2].priority == PulsePriority.NORMAL
    assert due[3].id == low_id
    assert due[3].priority == PulsePriority.LOW
    assert due[4].id == deferred_id
    assert due[4].priority == PulsePriority.DEFERRED


@pytest.mark.asyncio
async def test_time_ordering_within_priority(queue):
    """Test that within same priority, older pulses execute first (FIFO)."""
    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=2)
    older = now - timedelta(hours=3)
    oldest = now - timedelta(hours=4)

    # Schedule pulses with same priority but different times
    id_old = await queue.schedule_pulse(
        scheduled_at=old, prompt="Old", priority=PulsePriority.NORMAL
    )
    id_oldest = await queue.schedule_pulse(
        scheduled_at=oldest, prompt="Oldest", priority=PulsePriority.NORMAL
    )
    id_older = await queue.schedule_pulse(
        scheduled_at=older, prompt="Older", priority=PulsePriority.NORMAL
    )

    due = await queue.get_due_pulses(limit=10)
    assert len(due) == 3

    # Should be ordered by time (oldest first)
    assert due[0].id == id_oldest
    assert due[1].id == id_older
    assert due[2].id == id_old


@pytest.mark.asyncio
async def test_get_due_pulses_limit(queue):
    """Test that limit parameter works correctly."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=5)

    # Schedule 10 pulses
    for i in range(10):
        await queue.schedule_pulse(scheduled_at=past, prompt=f"Pulse {i}")

    # Get only 3
    due = await queue.get_due_pulses(limit=3)
    assert len(due) == 3


@pytest.mark.asyncio
async def test_get_upcoming_pulses(queue):
    """Test retrieving upcoming scheduled pulses."""
    now = datetime.now(timezone.utc)
    future1 = now + timedelta(hours=1)
    future2 = now + timedelta(hours=2)

    await queue.schedule_pulse(scheduled_at=future1, prompt="Future 1")
    await queue.schedule_pulse(scheduled_at=future2, prompt="Future 2")

    upcoming = await queue.get_upcoming_pulses(limit=10)
    assert len(upcoming) == 2
    assert upcoming[0].prompt == "Future 1"  # Ordered by time
    assert upcoming[1].prompt == "Future 2"


@pytest.mark.asyncio
async def test_get_upcoming_pulses_filters_by_status(queue):
    """Test that get_upcoming_pulses filters by status."""
    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=1)

    pending_id = await queue.schedule_pulse(scheduled_at=future, prompt="Pending")
    completed_id = await queue.schedule_pulse(scheduled_at=future, prompt="Completed")

    # Mark one as completed
    await queue.mark_processing(completed_id)
    await queue.mark_completed(completed_id, execution_duration_ms=1000)

    # Get upcoming (default: only PENDING)
    upcoming = await queue.get_upcoming_pulses()
    assert len(upcoming) == 1
    assert upcoming[0].id == pending_id

    # Get both PENDING and COMPLETED
    upcoming_all = await queue.get_upcoming_pulses(
        include_statuses=[PulseStatus.PENDING, PulseStatus.COMPLETED]
    )
    assert len(upcoming_all) == 2


@pytest.mark.asyncio
async def test_mark_processing(queue):
    """Test marking pulse as processing."""
    now = datetime.now(timezone.utc)
    pulse_id = await queue.schedule_pulse(scheduled_at=now, prompt="Test")

    # Mark as processing
    success = await queue.mark_processing(pulse_id)
    assert success is True

    pulse = await queue.get_pulse(pulse_id)
    assert pulse.status == PulseStatus.PROCESSING


@pytest.mark.asyncio
async def test_mark_processing_already_processing(queue):
    """Test that marking already processing pulse fails."""
    now = datetime.now(timezone.utc)
    pulse_id = await queue.schedule_pulse(scheduled_at=now, prompt="Test")

    # Mark as processing
    await queue.mark_processing(pulse_id)

    # Try to mark again - should fail
    success = await queue.mark_processing(pulse_id)
    assert success is False


@pytest.mark.asyncio
async def test_mark_processing_nonexistent_pulse(queue):
    """Test that marking nonexistent pulse fails."""
    success = await queue.mark_processing(99999)
    assert success is False


@pytest.mark.asyncio
async def test_mark_completed(queue):
    """Test marking pulse as completed."""
    now = datetime.now(timezone.utc)
    pulse_id = await queue.schedule_pulse(scheduled_at=now, prompt="Test")

    await queue.mark_processing(pulse_id)
    await queue.mark_completed(pulse_id, execution_duration_ms=5000)

    pulse = await queue.get_pulse(pulse_id)
    assert pulse.status == PulseStatus.COMPLETED
    assert pulse.executed_at is not None
    assert pulse.execution_duration_ms == 5000


@pytest.mark.asyncio
async def test_mark_failed_without_retry(queue):
    """Test marking pulse as failed without retry."""
    now = datetime.now(timezone.utc)
    pulse_id = await queue.schedule_pulse(scheduled_at=now, prompt="Test")

    await queue.mark_processing(pulse_id)
    retry_id = await queue.mark_failed(
        pulse_id, error_message="Something went wrong", should_retry=False
    )

    # No retry should be scheduled
    assert retry_id is None

    pulse = await queue.get_pulse(pulse_id)
    assert pulse.status == PulseStatus.FAILED
    assert pulse.error_message == "Something went wrong"
    assert pulse.executed_at is not None


@pytest.mark.asyncio
async def test_mark_failed_with_retry(queue):
    """Test retry logic with exponential backoff."""
    now = datetime.now(timezone.utc)
    pulse_id = await queue.schedule_pulse(scheduled_at=now, prompt="Test", max_retries=3)

    await queue.mark_processing(pulse_id)

    # First failure - should create retry
    retry_id = await queue.mark_failed(pulse_id, error_message="First failure", should_retry=True)

    assert retry_id is not None
    assert retry_id != pulse_id

    # Check original pulse
    original = await queue.get_pulse(pulse_id)
    assert original.status == PulseStatus.FAILED
    assert original.retry_count == 0

    # Check retry pulse
    retry = await queue.get_pulse(retry_id)
    assert retry.status == PulseStatus.PENDING
    assert retry.retry_count == 1
    assert retry.prompt == "Test"
    assert retry.created_by == "retry_system"

    # Verify exponential backoff: 2^0 = 1 minute
    time_diff = (retry.scheduled_at - now).total_seconds()
    assert 50 < time_diff < 70  # Should be ~60 seconds (1 minute)


@pytest.mark.asyncio
async def test_retry_exponential_backoff(queue):
    """Test that retry delays follow 2^retry_count pattern."""
    now = datetime.now(timezone.utc)

    # Create pulse with retry_count already set
    pulse_id = await queue.schedule_pulse(scheduled_at=now, prompt="Test", max_retries=5)

    # Manually update retry_count to test different backoff values
    pulse = await queue.get_pulse(pulse_id)
    expected_delays = {
        0: 1,  # 2^0 = 1 minute
        1: 2,  # 2^1 = 2 minutes
        2: 4,  # 2^2 = 4 minutes
        3: 8,  # 2^3 = 8 minutes
    }

    for retry_count, expected_minutes in expected_delays.items():
        await queue.mark_processing(pulse_id)

        # Update retry_count in database
        async with queue.SessionLocal() as session:
            p = await session.get(type(pulse), pulse_id)
            p.retry_count = retry_count
            await session.commit()

        # Mark failed and get retry
        retry_id = await queue.mark_failed(pulse_id, error_message="Test")

        if retry_id:
            retry = await queue.get_pulse(retry_id)
            time_diff = (retry.scheduled_at - datetime.now(timezone.utc)).total_seconds()
            expected_seconds = expected_minutes * 60

            # Allow 10 second tolerance
            assert (
                expected_seconds - 10 < time_diff < expected_seconds + 10
            ), f"Retry {retry_count}: expected ~{expected_minutes}min, got {time_diff/60:.1f}min"

            pulse_id = retry_id  # Use retry for next iteration


@pytest.mark.asyncio
async def test_retry_stops_after_max_retries(queue):
    """Test that retries stop after max_retries is reached."""
    now = datetime.now(timezone.utc)
    pulse_id = await queue.schedule_pulse(scheduled_at=now, prompt="Test", max_retries=2)

    # First failure (retry_count=0) - should retry
    await queue.mark_processing(pulse_id)
    retry1_id = await queue.mark_failed(pulse_id, error_message="Failure 1")
    assert retry1_id is not None

    # Second failure (retry_count=1) - should retry
    await queue.mark_processing(retry1_id)
    retry2_id = await queue.mark_failed(retry1_id, error_message="Failure 2")
    assert retry2_id is not None

    # Third failure (retry_count=2, equals max_retries) - should NOT retry
    await queue.mark_processing(retry2_id)
    retry3_id = await queue.mark_failed(retry2_id, error_message="Failure 3")
    assert retry3_id is None


@pytest.mark.asyncio
async def test_cancel_pulse(queue):
    """Test cancelling a pending pulse."""
    now = datetime.now(timezone.utc)
    pulse_id = await queue.schedule_pulse(scheduled_at=now, prompt="Test")

    success = await queue.cancel_pulse(pulse_id)
    assert success is True

    pulse = await queue.get_pulse(pulse_id)
    assert pulse.status == PulseStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_pulse_already_processing(queue):
    """Test that cancelling a processing pulse fails."""
    now = datetime.now(timezone.utc)
    pulse_id = await queue.schedule_pulse(scheduled_at=now, prompt="Test")

    await queue.mark_processing(pulse_id)

    # Try to cancel - should fail
    success = await queue.cancel_pulse(pulse_id)
    assert success is False

    pulse = await queue.get_pulse(pulse_id)
    assert pulse.status == PulseStatus.PROCESSING  # Still processing


@pytest.mark.asyncio
async def test_cancel_nonexistent_pulse(queue):
    """Test cancelling nonexistent pulse."""
    success = await queue.cancel_pulse(99999)
    assert success is False


@pytest.mark.asyncio
async def test_reschedule_pulse(queue):
    """Test rescheduling a pending pulse."""
    now = datetime.now(timezone.utc)
    original_time = now + timedelta(hours=1)
    new_time = now + timedelta(hours=2)

    pulse_id = await queue.schedule_pulse(scheduled_at=original_time, prompt="Test")

    success = await queue.reschedule_pulse(pulse_id, new_time)
    assert success is True

    pulse = await queue.get_pulse(pulse_id)
    assert pulse.scheduled_at == new_time


@pytest.mark.asyncio
async def test_reschedule_pulse_already_processing(queue):
    """Test that rescheduling a processing pulse fails."""
    now = datetime.now(timezone.utc)
    pulse_id = await queue.schedule_pulse(scheduled_at=now, prompt="Test")

    await queue.mark_processing(pulse_id)

    # Try to reschedule - should fail
    new_time = now + timedelta(hours=1)
    success = await queue.reschedule_pulse(pulse_id, new_time)
    assert success is False


@pytest.mark.asyncio
async def test_reschedule_nonexistent_pulse(queue):
    """Test rescheduling nonexistent pulse."""
    now = datetime.now(timezone.utc)
    success = await queue.reschedule_pulse(99999, now)
    assert success is False


@pytest.mark.asyncio
async def test_get_due_pulses_excludes_non_pending(queue):
    """Test that get_due_pulses only returns PENDING pulses."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=5)

    # Create pulses with different statuses
    pending_id = await queue.schedule_pulse(scheduled_at=past, prompt="Pending")
    processing_id = await queue.schedule_pulse(scheduled_at=past, prompt="Processing")
    completed_id = await queue.schedule_pulse(scheduled_at=past, prompt="Completed")
    cancelled_id = await queue.schedule_pulse(scheduled_at=past, prompt="Cancelled")

    # Update statuses
    await queue.mark_processing(processing_id)
    await queue.mark_processing(completed_id)
    await queue.mark_completed(completed_id, execution_duration_ms=1000)
    await queue.cancel_pulse(cancelled_id)

    # Get due pulses - should only get pending
    due = await queue.get_due_pulses()
    assert len(due) == 1
    assert due[0].id == pending_id


@pytest.mark.asyncio
async def test_concurrent_operations(queue):
    """Test that concurrent operations don't interfere with each other."""
    now = datetime.now(timezone.utc)

    # Schedule multiple pulses concurrently
    tasks = [queue.schedule_pulse(scheduled_at=now, prompt=f"Pulse {i}") for i in range(10)]
    pulse_ids = await asyncio.gather(*tasks)

    assert len(pulse_ids) == 10
    assert len(set(pulse_ids)) == 10  # All unique IDs

    # Get all due pulses
    due = await queue.get_due_pulses(limit=20)
    assert len(due) == 10


@pytest.mark.asyncio
async def test_timezone_awareness(queue):
    """Test that all datetime operations use timezone-aware datetimes."""
    # Schedule with UTC timezone
    utc_time = datetime.now(timezone.utc)
    pulse_id = await queue.schedule_pulse(scheduled_at=utc_time, prompt="Test")

    pulse = await queue.get_pulse(pulse_id)

    # Verify all timestamps are timezone-aware
    assert pulse.scheduled_at.tzinfo is not None
    assert pulse.created_at.tzinfo is not None


@pytest.mark.asyncio
async def test_get_pulse_nonexistent(queue):
    """Test getting a pulse that doesn't exist."""
    pulse = await queue.get_pulse(99999)
    assert pulse is None


@pytest.mark.asyncio
async def test_empty_sticky_notes_and_tags(queue):
    """Test that empty lists for sticky_notes and tags work correctly."""
    now = datetime.now(timezone.utc)
    pulse_id = await queue.schedule_pulse(scheduled_at=now, prompt="Test", sticky_notes=[], tags=[])

    pulse = await queue.get_pulse(pulse_id)
    assert pulse.sticky_notes == []
    assert pulse.tags == []


@pytest.mark.asyncio
async def test_pulse_queue_close(queue):
    """Test that close() properly disposes the engine."""
    # Queue is created by fixture, just test close doesn't crash
    await queue.close()
    # Can't easily verify disposal, but at least it shouldn't error
