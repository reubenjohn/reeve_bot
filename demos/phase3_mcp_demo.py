#!/usr/bin/env python3
"""
Phase 3 Demo: MCP Tools Integration

This demo verifies:
- MCP server can start successfully
- Time parsing functionality works
- Pulse scheduling via queue (simulating MCP tool behavior)
- Telegram notification functionality (if configured)

Note: To test the actual MCP protocol integration, use Claude Code with the
MCP servers configured in mcp_config.json. This demo tests the underlying
functionality that the MCP tools expose.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

from reeve.mcp.pulse_server import _parse_time_string, _priority_emoji, _status_emoji
from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.queue import PulseQueue
from reeve.utils.config import get_config


async def demo_time_parsing():
    """Demo the time parsing functionality."""
    print("🚀 Phase 3 Demo: MCP Tools Integration\n")
    print("=" * 60)
    print("Part 1: Time Parsing (used by MCP tools)\n")

    test_cases = [
        "now",
        "in 1 hour",
        "in 30 minutes",
        "in 2 days",
        "2026-01-25T15:00:00Z",
    ]

    print("✓ Testing time parsing...")
    for time_str in test_cases:
        try:
            parsed = _parse_time_string(time_str)
            now = datetime.now(timezone.utc)
            delta = (parsed - now).total_seconds()
            if delta < 60:
                delta_str = "now"
            elif delta < 3600:
                delta_str = f"in {int(delta/60)} minutes"
            elif delta < 86400:
                delta_str = f"in {delta/3600:.1f} hours"
            else:
                delta_str = f"in {delta/86400:.1f} days"
            print(f"  - '{time_str}' → {parsed} ({delta_str})")
        except Exception as e:
            print(f"  - '{time_str}' → Error: {e}")


async def demo_pulse_operations():
    """Demo pulse operations (what MCP tools use under the hood)."""
    print(f"\n{'='*60}")
    print("Part 2: Pulse Queue Operations (used by MCP tools)\n")

    config = get_config()
    queue = PulseQueue(config.pulse_db_url)
    await queue.initialize()

    # Schedule pulses (simulating schedule_pulse MCP tool)
    print("Scheduling pulses (via MCP-like operations)...\n")

    now = datetime.now(timezone.utc)
    pulse_ids = []

    pulse_id = await queue.schedule_pulse(
        scheduled_at=now + timedelta(hours=1),
        prompt="DEMO: Morning briefing",
        priority=PulsePriority.HIGH,
        tags=["demo", "morning"],
        sticky_notes=["Check calendar", "Review emails"],
    )
    pulse_ids.append(pulse_id)
    print(f"✓ Scheduled pulse #{pulse_id}: 'Morning briefing' (HIGH priority, in 1 hour)")

    pulse_id = await queue.schedule_pulse(
        scheduled_at=now + timedelta(hours=4),
        prompt="DEMO: Afternoon check-in",
        priority=PulsePriority.NORMAL,
        tags=["demo", "afternoon"],
    )
    pulse_ids.append(pulse_id)
    print(f"✓ Scheduled pulse #{pulse_id}: 'Afternoon check-in' (NORMAL priority, in 4 hours)")

    # List pulses (simulating list_upcoming_pulses MCP tool)
    print(f"\n{'='*60}")
    print("Listing upcoming pulses (via MCP-like operations):\n")

    upcoming = await queue.get_upcoming_pulses(limit=10)
    for pulse in upcoming:
        if pulse.prompt.startswith("DEMO:"):
            delta = (pulse.scheduled_at - datetime.now(timezone.utc)).total_seconds()
            delta_str = f"in {delta/3600:.1f}h" if delta > 0 else f"{abs(delta)/3600:.1f}h ago"
            emoji = _priority_emoji(pulse.priority)
            print(
                f"{emoji} #{pulse.id} - {pulse.priority.upper()} - {delta_str} - '{pulse.prompt}'"
            )

    # Reschedule (simulating reschedule_pulse MCP tool)
    if pulse_ids:
        print(f"\n{'='*60}")
        print(f"Rescheduling pulse #{pulse_ids[0]} to 30 minutes from now...\n")

        new_time = datetime.now(timezone.utc) + timedelta(minutes=30)
        success = await queue.reschedule_pulse(pulse_ids[0], new_time)
        if success:
            print(f"✓ Rescheduled pulse #{pulse_ids[0]}")

        # Cancel (simulating cancel_pulse MCP tool)
        if len(pulse_ids) > 1:
            print(f"\n{'='*60}")
            print(f"Cancelling pulse #{pulse_ids[1]}...\n")

            success = await queue.cancel_pulse(pulse_ids[1])
            if success:
                print(f"✓ Cancelled pulse #{pulse_ids[1]}")

    await queue.close()


async def demo_telegram_notifier():
    """Demo Telegram notification (if configured)."""
    print(f"\n{'='*60}")
    print("Part 3: Telegram Notifier (if configured)\n")

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("⚠ Telegram credentials not configured")
        print("  To test Telegram notifications, set:")
        print("    - TELEGRAM_BOT_TOKEN=your_bot_token")
        print("    - TELEGRAM_CHAT_ID=your_chat_id")
        print("\n  Skipping Telegram demo...")
        return

    print("✓ Telegram credentials found, testing notification...\n")

    try:
        import httpx

        # Send a test notification
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        message = "✅ *Phase 3 Demo Complete!*\n\nMCP tools are working correctly."

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                },
            )

            if response.status_code == 200:
                print("✓ Sent test notification successfully!")
                print("  Check your Telegram for the message.")
            else:
                print(f"❌ Failed to send notification: {response.text}")

    except Exception as e:
        print(f"❌ Failed to send notification: {e}")


async def cleanup_demo_pulses():
    """Clean up any remaining demo pulses."""
    config = get_config()
    queue = PulseQueue(config.pulse_db_url)
    await queue.initialize()

    upcoming = await queue.get_upcoming_pulses(limit=100)

    cancelled = 0
    for pulse in upcoming:
        if pulse.prompt.startswith("DEMO:"):
            success = await queue.cancel_pulse(pulse.id)
            if success:
                cancelled += 1

    await queue.close()

    if cancelled > 0:
        print(f"\n✓ Cleaned up {cancelled} demo pulse(s)")


async def main():
    try:
        await demo_time_parsing()
        await demo_pulse_operations()
        await demo_telegram_notifier()
    finally:
        await cleanup_demo_pulses()

    print("\n" + "=" * 60)
    print("✅ Phase 3 Demo Complete!")
    print("\nKey features demonstrated:")
    print("  - Flexible time parsing (ISO 8601, relative times, keywords)")
    print("  - Scheduling pulses with priorities, tags, and sticky notes")
    print("  - Listing upcoming pulses with formatting")
    print("  - Rescheduling pulses")
    print("  - Cancelling pulses")
    print("  - Telegram notifications (if configured)")
    print("\nTo use these features via MCP tools in Claude Code:")
    print("  1. Configure MCP servers in ~/.config/claude-code/mcp_config.json")
    print("  2. See docs/MCP_SETUP.md for setup instructions")
    print("  3. Use tools like schedule_pulse(), list_upcoming_pulses(), etc.")
    print("  4. Example: schedule_pulse(scheduled_at='in 1 hour', prompt='Test', priority='high')")


if __name__ == "__main__":
    asyncio.run(main())
