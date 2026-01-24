#!/usr/bin/env python3
"""
Phase 1 Demo: Database Schema and Models

This demo verifies:
- Database initialization
- Pulse model creation
- Database schema correctness
- Enum integration
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.models import Pulse
from reeve.pulse.queue import PulseQueue
from reeve.utils.config import get_config


async def main():
    print("🚀 Phase 1 Demo: Database Schema and Models\n")
    print("=" * 60)

    # Get configuration
    config = get_config()
    # Extract database path from URL
    db_path = config.pulse_db_url.replace("sqlite+aiosqlite:///", "")
    print(f"✓ Database location: {db_path}")

    # Initialize queue (creates database if needed)
    queue = PulseQueue(config.pulse_db_url)
    await queue.initialize()
    print(f"✓ Database initialized\n")

    # Create a test pulse
    print("Creating test pulse...")
    now = datetime.now(timezone.utc)
    scheduled_time = now + timedelta(hours=1)

    pulse_id = await queue.schedule_pulse(
        scheduled_at=scheduled_time,
        prompt="DEMO: Test pulse from Phase 1 demo",
        priority=PulsePriority.NORMAL,
    )
    print(f"✓ Created pulse with ID: {pulse_id}")

    # Retrieve and verify the pulse
    pulse = await queue.get_pulse(pulse_id)
    if pulse:
        print(f"\n✓ Verified pulse in database:")
        print(f"  - ID: {pulse.id}")
        print(f"  - Scheduled at: {pulse.scheduled_at}")
        print(f"  - Priority: {pulse.priority}")
        print(f"  - Status: {pulse.status}")
        print(f"  - Prompt: {pulse.prompt}")
        print(f"  - Created at: {pulse.created_at}")
    else:
        print("❌ Failed to retrieve pulse")
        await queue.close()
        return

    # Test enum values
    print(f"\n✓ Testing enum values:")
    print(
        f"  - Priority enum: {PulsePriority.NORMAL} (type: {type(PulsePriority.NORMAL).__name__})"
    )
    print(f"  - Status enum: {PulseStatus.PENDING} (type: {type(PulseStatus.PENDING).__name__})")
    print(f"  - Enums are strings: {isinstance(PulsePriority.NORMAL, str)}")

    # Cleanup: cancel the demo pulse
    print(f"\n✓ Cleaning up demo pulse...")
    cancelled = await queue.cancel_pulse(pulse_id)
    if cancelled:
        print(f"✓ Demo pulse cancelled")
    else:
        print("⚠ Note: Demo pulse may have already been processed")

    await queue.close()

    print("\n" + "=" * 60)
    print("✅ Phase 1 Demo Complete!")
    print(f"\nDatabase file: {db_path}")
    print(f"You can inspect it with: sqlite3 {db_path}")


if __name__ == "__main__":
    asyncio.run(main())
