"""
Phase 2 Validation Test

Tests the full integration from the roadmap validation example.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from reeve.pulse.enums import PulsePriority
from reeve.pulse.queue import PulseQueue


@pytest.mark.asyncio
async def test_phase2_integration():
    """
    Integration test from the roadmap.

    This validates that the core PulseQueue functionality works as expected
    in a realistic scenario.
    """
    queue = PulseQueue("sqlite+aiosqlite:///:memory:")
    await queue.initialize()

    try:
        # Schedule pulse
        pulse_id = await queue.schedule_pulse(
            scheduled_at=datetime.now(timezone.utc),
            prompt="Test pulse from Phase 2 validation",
            priority=PulsePriority.HIGH,
        )
        print(f"Created pulse {pulse_id}")
        assert pulse_id > 0

        # Get due pulses
        pulses = await queue.get_due_pulses()
        print(f"Due pulses: {len(pulses)}")
        assert len(pulses) == 1
        assert pulses[0].id == pulse_id
        assert pulses[0].prompt == "Test pulse from Phase 2 validation"
        assert pulses[0].priority == PulsePriority.HIGH

        # Mark as processing
        success = await queue.mark_processing(pulse_id)
        assert success is True

        # Verify it's no longer in due pulses
        pulses = await queue.get_due_pulses()
        assert len(pulses) == 0

        # Mark as completed
        await queue.mark_completed(pulse_id, execution_duration_ms=500)

        # Verify completion
        pulse = await queue.get_pulse(pulse_id)
        assert pulse.execution_duration_ms == 500
        assert pulse.executed_at is not None

        print("✓ Phase 2 validation successful!")

    finally:
        await queue.close()
