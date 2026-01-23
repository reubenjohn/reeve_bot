#!/usr/bin/env python3
"""
Phase 2 Demo: Queue Operations

This demo verifies:
- Scheduling pulses with different priorities
- Querying due pulses (priority ordering)
- Marking pulses as processing/completed/failed
- Retry logic with exponential backoff
- Cancelling pulses
"""

import asyncio
from datetime import datetime, timezone, timedelta

from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.queue import PulseQueue
from reeve.utils.config import get_config


def priority_emoji(priority: PulsePriority) -> str:
    """Get emoji for priority level."""
    return {
        PulsePriority.CRITICAL: "🚨",
        PulsePriority.HIGH: "🔔",
        PulsePriority.NORMAL: "⏰",
        PulsePriority.LOW: "📋",
        PulsePriority.DEFERRED: "🕐",
    }[priority]


def status_emoji(status: PulseStatus) -> str:
    """Get emoji for status."""
    return {
        PulseStatus.PENDING: "⏳",
        PulseStatus.PROCESSING: "⚙️",
        PulseStatus.COMPLETED: "✅",
        PulseStatus.FAILED: "❌",
        PulseStatus.CANCELLED: "🚫",
    }[status]


async def main():
    print("🚀 Phase 2 Demo: Queue Operations\n")
    print("=" * 60)

    # Initialize queue
    config = get_config()
    queue = PulseQueue(config.pulse_db_url)
    await queue.initialize()
    print("✓ Initialized PulseQueue\n")

    # Schedule pulses with different priorities
    now = datetime.now(timezone.utc)
    pulse_ids = []

    print("Scheduling test pulses...")
    pulse_ids.append(
        await queue.schedule_pulse(
            scheduled_at=now + timedelta(seconds=5),
            prompt="DEMO: High priority task",
            priority=PulsePriority.HIGH,
        )
    )
    print(f"✓ Scheduled pulse #{pulse_ids[-1]}: 'High priority task' (due in 5s, priority: HIGH)")

    pulse_ids.append(
        await queue.schedule_pulse(
            scheduled_at=now + timedelta(seconds=10),
            prompt="DEMO: Normal maintenance",
            priority=PulsePriority.NORMAL,
        )
    )
    print(f"✓ Scheduled pulse #{pulse_ids[-1]}: 'Normal maintenance' (due in 10s, priority: NORMAL)")

    pulse_ids.append(
        await queue.schedule_pulse(
            scheduled_at=now + timedelta(seconds=15),
            prompt="DEMO: Low priority cleanup",
            priority=PulsePriority.LOW,
        )
    )
    print(f"✓ Scheduled pulse #{pulse_ids[-1]}: 'Low priority cleanup' (due in 15s, priority: LOW)")

    # List upcoming pulses
    print(f"\n{'='*60}")
    print("Upcoming pulses:")
    upcoming = await queue.get_upcoming_pulses(limit=10)
    for pulse in upcoming:
        delta = (pulse.scheduled_at - now).total_seconds()
        print(
            f"{priority_emoji(pulse.priority)} #{pulse.id} - {pulse.priority} - "
            f"in {int(delta)}s - '{pulse.prompt}'"
        )

    # Simulate marking a pulse as processing and completing it
    print(f"\n{'='*60}")
    print(f"Simulating execution of pulse #{pulse_ids[0]}...")
    success = await queue.mark_processing(pulse_ids[0])
    if success:
        print(f"✓ Marked pulse #{pulse_ids[0]} as PROCESSING")

    await asyncio.sleep(0.5)  # Simulate some work (500ms)

    await queue.mark_completed(pulse_ids[0], execution_duration_ms=500)
    print(f"✓ Marked pulse #{pulse_ids[0]} as COMPLETED")

    # Simulate a failure with retry
    print(f"\n{'='*60}")
    print(f"Simulating failure for pulse #{pulse_ids[1]}...")
    success = await queue.mark_processing(pulse_ids[1])
    if success:
        print(f"✓ Marked pulse #{pulse_ids[1]} as PROCESSING")

    await asyncio.sleep(0.5)  # Simulate some work

    retry_id = await queue.mark_failed(pulse_ids[1], error_message="DEMO: Simulated failure")
    if retry_id:
        retry_pulse = await queue.get_pulse(retry_id)
        if retry_pulse:
            retry_delay = (retry_pulse.scheduled_at - datetime.now(timezone.utc)).total_seconds()
            print(
                f"✓ Marked pulse #{pulse_ids[1]} as FAILED "
                f"(retry_count=1, will retry in ~{int(retry_delay/60)} minutes)"
            )
            # Clean up the retry pulse
            await queue.cancel_pulse(retry_id)
    else:
        print(f"✓ Marked pulse #{pulse_ids[1]} as FAILED (max retries reached)")

    # Cancel remaining pulse
    print(f"\n{'='*60}")
    print(f"Cancelling pulse #{pulse_ids[2]}...")
    success = await queue.cancel_pulse(pulse_ids[2])
    if success:
        print(f"✓ Cancelled pulse #{pulse_ids[2]}")

    # Show final status
    print(f"\n{'='*60}")
    print("Final status:")
    for i, pulse_id in enumerate(pulse_ids):
        pulse = await queue.get_pulse(pulse_id)
        if pulse:
            print(f"  - Pulse #{pulse_id}: {pulse.status} {status_emoji(pulse.status)}")

    await queue.close()

    print("\n" + "=" * 60)
    print("✅ Phase 2 Demo Complete!")
    print("\nKey features demonstrated:")
    print("  - Scheduling pulses with different priorities")
    print("  - Priority-based ordering (HIGH → NORMAL → LOW)")
    print("  - State transitions (PENDING → PROCESSING → COMPLETED)")
    print("  - Retry logic with exponential backoff (2^retry_count minutes)")
    print("  - Cancelling pulses")


if __name__ == "__main__":
    asyncio.run(main())
