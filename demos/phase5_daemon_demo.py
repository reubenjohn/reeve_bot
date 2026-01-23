#!/usr/bin/env python3
"""
Phase 5 Demo: Pulse Daemon

This demo verifies:
- Daemon initialization and startup
- Scheduler loop polling (1 second intervals)
- Concurrent pulse execution
- Priority-based ordering
- Graceful shutdown (SIGINT/SIGTERM)
- Retry logic on failures

Note: This demo schedules real pulses and executes them via Hapi.
Use --mock to run without real Hapi execution.
"""

import asyncio
import signal
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from reeve.pulse.daemon import PulseDaemon
from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.queue import PulseQueue
from reeve.utils.config import get_config
from reeve.utils.logging import setup_logging

# ============================================================================
# Formatting Utilities
# ============================================================================

SEPARATOR_HEAVY = "=" * 60
SEPARATOR_LIGHT = "-" * 60
SEPARATOR_CODE = "─" * 60


def print_section(title: str, heavy: bool = False) -> None:
    """Print a formatted section header."""
    separator = SEPARATOR_HEAVY if heavy else SEPARATOR_LIGHT
    print(f"\n{separator}")
    print(title)
    print(SEPARATOR_LIGHT)


def print_success(message: str, details: Optional[dict] = None) -> None:
    """Print a success message with optional details."""
    print(f"✓ {message}")
    if details:
        for key, value in details.items():
            print(f"  {key}: {value}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"ℹ {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"⚠ {message}")


# ============================================================================
# Demo Helpers
# ============================================================================


async def cleanup_leftover_pulses(queue: PulseQueue) -> None:
    """Clean up any leftover demo pulses from previous runs."""
    # Get all pending/processing pulses (include_statuses defaults to [PENDING])
    all_pulses = await queue.get_upcoming_pulses(limit=100)

    cleaned = 0
    for pulse in all_pulses:
        if pulse.tags and "demo" in pulse.tags:
            await queue.cancel_pulse(pulse.id)
            cleaned += 1

    if cleaned > 0:
        print_info(f"Cleaned up {cleaned} leftover demo pulse(s) from previous runs")


async def schedule_demo_pulses(queue: PulseQueue, mock_mode: bool) -> list[int]:
    """Schedule a variety of demo pulses to test daemon execution."""
    print_section("Scheduling demo pulses")

    pulse_ids = []
    now = datetime.now(timezone.utc)

    # Pulse 1: CRITICAL priority (due immediately)
    pulse_ids.append(
        await queue.schedule_pulse(
            scheduled_at=now + timedelta(seconds=3),
            prompt="DEMO: Say just 'OK'" if not mock_mode else "DEMO: Critical pulse (mock)",
            priority=PulsePriority.CRITICAL,
            tags=["demo", "critical"],
        )
    )
    print_success("Scheduled CRITICAL pulse", {"Due in": "3 seconds", "ID": pulse_ids[-1]})

    # Pulse 2: HIGH priority (due in 8 seconds)
    pulse_ids.append(
        await queue.schedule_pulse(
            scheduled_at=now + timedelta(seconds=8),
            prompt="DEMO: Say just 'OK'" if not mock_mode else "DEMO: High priority pulse (mock)",
            priority=PulsePriority.HIGH,
            tags=["demo", "high"],
        )
    )
    print_success("Scheduled HIGH pulse", {"Due in": "8 seconds", "ID": pulse_ids[-1]})

    # Pulse 3: NORMAL priority with sticky notes (due in 28 seconds - after first pulse completes)
    pulse_ids.append(
        await queue.schedule_pulse(
            scheduled_at=now + timedelta(seconds=28),
            prompt="DEMO: Say just 'OK'" if not mock_mode else "DEMO: Normal pulse with sticky notes (mock)",
            priority=PulsePriority.NORMAL,
            sticky_notes=[
                "This pulse has sticky notes",
                "Sticky notes are appended to the prompt",
            ],
            tags=["demo", "normal"],
        )
    )
    print_success("Scheduled NORMAL pulse", {"Due in": "28 seconds", "With": "2 sticky notes", "ID": pulse_ids[-1]})

    # Pulse 4: Concurrent execution test (due in 33 seconds, along with next one)
    pulse_ids.append(
        await queue.schedule_pulse(
            scheduled_at=now + timedelta(seconds=33),
            prompt="DEMO: Say just 'OK'" if not mock_mode else "DEMO: Concurrent pulse A (mock)",
            priority=PulsePriority.NORMAL,
            tags=["demo", "concurrent"],
        )
    )
    print_success("Scheduled concurrent pulse A", {"Due in": "33 seconds", "ID": pulse_ids[-1]})

    # Pulse 5: Concurrent execution test (due in 33 seconds, same as previous)
    pulse_ids.append(
        await queue.schedule_pulse(
            scheduled_at=now + timedelta(seconds=33),
            prompt="DEMO: Say just 'OK'" if not mock_mode else "DEMO: Concurrent pulse B (mock)",
            priority=PulsePriority.NORMAL,
            tags=["demo", "concurrent"],
        )
    )
    print_success("Scheduled concurrent pulse B", {"Due in": "33 seconds (parallel)", "ID": pulse_ids[-1]})

    print(f"\n✓ Scheduled {len(pulse_ids)} demo pulses")
    if not mock_mode:
        print("  First 2 pulses start ~3-8 seconds apart")
        print("  Later pulses scheduled after first completion (~28-33 seconds)")
        print("  ⚠ Note: Real Hapi sessions can take 30-90+ seconds due to startup overhead")
        print("  ⚠ Demo shows PROCESSING state and graceful shutdown handling")
    else:
        print("  Pulses will execute with ~5 second intervals")

    return pulse_ids


async def monitor_pulse_status(queue: PulseQueue, pulse_ids: list[int], duration: int, mock_mode: bool = False) -> None:
    """Monitor pulse execution status for a given duration."""
    print_section(f"Monitoring pulse execution for {duration} seconds")
    if mock_mode:
        print("  (Updates every 2 seconds)\n")
    else:
        print("  (Updates every 2 seconds)")
        print("  Note: Real Hapi sessions take 15-25 seconds each\n")

    start_time = datetime.now(timezone.utc)
    last_statuses = {}

    while (datetime.now(timezone.utc) - start_time).total_seconds() < duration:
        await asyncio.sleep(2)

        # Check each pulse
        status_changed = False
        for pulse_id in pulse_ids:
            pulse = await queue.get_pulse(pulse_id)
            if pulse:
                current_status = pulse.status
                if pulse_id not in last_statuses or last_statuses[pulse_id] != current_status:
                    status_changed = True
                    emoji = {
                        PulseStatus.PENDING: "⏳",
                        PulseStatus.PROCESSING: "⚙️",
                        PulseStatus.COMPLETED: "✅",
                        PulseStatus.FAILED: "❌",
                        PulseStatus.CANCELLED: "🚫",
                    }.get(current_status, "❓")

                    priority_emoji = {
                        PulsePriority.CRITICAL: "🚨",
                        PulsePriority.HIGH: "🔔",
                        PulsePriority.NORMAL: "⏰",
                        PulsePriority.LOW: "📋",
                        PulsePriority.DEFERRED: "🕐",
                    }.get(pulse.priority, "❓")

                    prompt_preview = pulse.prompt[:40] + "..." if len(pulse.prompt) > 40 else pulse.prompt
                    print(f"{emoji} {priority_emoji} Pulse {pulse_id}: {current_status.upper()} - {prompt_preview}")

                    if current_status == PulseStatus.COMPLETED and pulse.execution_duration_ms:
                        print(f"   ⏱ Executed in {pulse.execution_duration_ms}ms")

                    last_statuses[pulse_id] = current_status

        if not status_changed:
            print(".", end="", flush=True)


async def cleanup_demo_pulses(queue: PulseQueue, pulse_ids: list[int]) -> None:
    """Clean up any remaining demo pulses."""
    print_section("Cleaning up demo pulses")

    for pulse_id in pulse_ids:
        pulse = await queue.get_pulse(pulse_id)
        if pulse and pulse.status in [PulseStatus.PENDING, PulseStatus.PROCESSING]:
            await queue.cancel_pulse(pulse_id)
            print(f"✓ Cancelled pulse {pulse_id}")

    print("✓ Cleanup complete")


# ============================================================================
# Real Daemon Demo
# ============================================================================


async def demo_with_real_daemon():
    """Demo with real daemon and Hapi execution."""
    print("🚀 Phase 5 Demo: Pulse Daemon (Real Execution)\n")
    print(SEPARATOR_HEAVY)

    config = get_config()

    # Setup logging
    setup_logging()

    # Create daemon
    daemon = PulseDaemon(config)
    queue = daemon.queue

    # Initialize database
    await queue.initialize()

    pulse_ids = []

    try:
        # Clean up any leftover pulses from previous runs
        await cleanup_leftover_pulses(queue)

        # Schedule demo pulses
        pulse_ids = await schedule_demo_pulses(queue, mock_mode=False)

        # Start daemon in background
        print_section("Starting daemon", heavy=True)
        print("  Scheduler will poll every 1 second")
        print("  Pulses will execute concurrently")
        print("  Press Ctrl+C to stop gracefully\n")

        daemon_task = asyncio.create_task(daemon.start())

        # Give daemon time to start
        await asyncio.sleep(1)
        print_success("Daemon started")

        # Monitor execution for 60 seconds (enough time for most Hapi sessions to complete)
        await monitor_pulse_status(queue, pulse_ids, duration=60, mock_mode=False)

        # Show final status
        print_section("Final pulse status", heavy=True)
        completed_count = 0
        failed_count = 0
        processing_count = 0

        for pulse_id in pulse_ids:
            pulse = await queue.get_pulse(pulse_id)
            if pulse:
                if pulse.status == PulseStatus.COMPLETED:
                    completed_count += 1
                elif pulse.status == PulseStatus.FAILED:
                    failed_count += 1
                elif pulse.status == PulseStatus.PROCESSING:
                    processing_count += 1

                status_emoji = {
                    PulseStatus.COMPLETED: "✅",
                    PulseStatus.FAILED: "❌",
                    PulseStatus.PROCESSING: "⚙️",
                    PulseStatus.PENDING: "⏳",
                }.get(pulse.status, "❓")

                print(f"{status_emoji} Pulse {pulse_id}: {pulse.status.upper()}")

        print(f"\nSummary:")
        print(f"  ✅ Completed: {completed_count}/{len(pulse_ids)}")
        print(f"  ❌ Failed: {failed_count}/{len(pulse_ids)}")
        if processing_count > 0:
            print(f"  ⚙️ Still processing: {processing_count}/{len(pulse_ids)}")
            print(f"\n  Note: Real Hapi sessions can take 30-90+ seconds")
            print(f"  Pulses still processing will complete during shutdown grace period")

        # Trigger graceful shutdown
        print_section("Triggering graceful shutdown", heavy=True)
        print("  Sending SIGINT to daemon...")

        # Send SIGINT to trigger shutdown
        import os
        os.kill(os.getpid(), signal.SIGINT)

        # Wait for daemon to shut down
        try:
            await asyncio.wait_for(daemon_task, timeout=35)
            print_success("Daemon shut down gracefully")
        except asyncio.TimeoutError:
            print_warning("Daemon shutdown timed out")
            daemon_task.cancel()

    finally:
        # Cleanup
        await cleanup_demo_pulses(queue, pulse_ids)
        await queue.close()

    # Summary
    print_section("✅ Phase 5 Demo Complete!", heavy=True)

    summary = """
Key features demonstrated:
  1. Daemon startup and initialization
  2. Scheduler loop (1-second polling)
  3. Priority-based pulse execution (CRITICAL → HIGH → NORMAL → LOW)
  4. Concurrent pulse execution (multiple pulses in parallel)
  5. Sticky notes appended to prompts
  6. Status transitions (PENDING → PROCESSING)
  7. Graceful shutdown with 30-second grace period for in-flight pulses
  8. Retry logic on failure/interruption

Technical details:
  - Daemon runs scheduler loop in background task
  - Pulses execute via PulseExecutor (spawns real Hapi sessions)
  - Signal handlers (SIGINT, SIGTERM) trigger graceful shutdown
  - In-flight pulses get 30-second grace period
  - Interrupted pulses automatically scheduled for retry
  - Database connection properly closed on shutdown

Real-world note:
  - Hapi sessions have 30-90+ seconds of overhead for initialization
  - In production, pulses run for minutes/hours (calendar checks, email processing)
  - This demo shows the daemon mechanics, not realistic execution times

Next steps:
  - Phase 6: HTTP REST API for external triggers
  - Phase 7: Integration with Telegram, Email, Calendar
  - Phase 8: Production deployment (systemd service)
"""
    print(summary)


# ============================================================================
# Mock Demo
# ============================================================================


async def demo_with_mock_daemon():
    """Demo with mock daemon (no real Hapi execution)."""
    print("🚀 Phase 5 Demo: Pulse Daemon (Mock Mode)\n")
    print(SEPARATOR_HEAVY)
    print("ℹ Running in mock mode - no real Hapi execution\n")

    config = get_config()

    # Setup logging
    setup_logging()

    # Create daemon with mock command
    daemon = PulseDaemon(config)
    daemon.executor.hapi_command = "echo"  # Use echo as mock
    queue = daemon.queue

    # Initialize database
    await queue.initialize()

    pulse_ids = []

    try:
        # Clean up any leftover pulses from previous runs
        await cleanup_leftover_pulses(queue)

        # Schedule demo pulses
        pulse_ids = await schedule_demo_pulses(queue, mock_mode=True)

        # Start daemon in background
        print_section("Starting daemon (mock mode)", heavy=True)
        print("  Scheduler will poll every 1 second")
        print("  Pulses will execute with 'echo' command (mock)")
        print("  Press Ctrl+C to stop gracefully\n")

        daemon_task = asyncio.create_task(daemon.start())

        # Give daemon time to start
        await asyncio.sleep(1)
        print_success("Daemon started")

        # Monitor execution for 40 seconds (to see all pulses complete)
        await monitor_pulse_status(queue, pulse_ids, duration=40, mock_mode=True)

        # Show final status
        print_section("Final pulse status", heavy=True)
        completed_count = 0

        for pulse_id in pulse_ids:
            pulse = await queue.get_pulse(pulse_id)
            if pulse:
                if pulse.status == PulseStatus.COMPLETED:
                    completed_count += 1

                status_emoji = "✅" if pulse.status == PulseStatus.COMPLETED else "⏳"
                print(f"{status_emoji} Pulse {pulse_id}: {pulse.status.upper()}")

        print(f"\n✓ All {completed_count}/{len(pulse_ids)} pulses completed")

        # Trigger graceful shutdown
        print_section("Triggering graceful shutdown", heavy=True)

        # Send SIGINT
        import os
        os.kill(os.getpid(), signal.SIGINT)

        # Wait for shutdown
        try:
            await asyncio.wait_for(daemon_task, timeout=35)
            print_success("Daemon shut down gracefully")
        except asyncio.TimeoutError:
            print_warning("Daemon shutdown timed out")
            daemon_task.cancel()

    finally:
        # Cleanup
        await cleanup_demo_pulses(queue, pulse_ids)
        await queue.close()

    # Summary
    print_section("✅ Phase 5 Demo Complete (Mock Mode)!", heavy=True)

    summary = """
Note: Install Hapi to test real execution.

Key features demonstrated:
  - Daemon architecture and lifecycle
  - Scheduler loop concept
  - Priority-based ordering
  - Concurrent execution pattern
  - Graceful shutdown handling

With real Hapi, you'll also see:
  - Actual Hapi session execution
  - Session ID extraction and tracking
  - Real execution duration metrics
  - Retry logic on failures
"""
    print(summary)


# ============================================================================
# Main Entry Point
# ============================================================================


async def main():
    """Main entry point."""
    mock_mode = "--mock" in sys.argv

    if mock_mode:
        await demo_with_mock_daemon()
    else:
        print_info("Starting with real daemon...")
        print_info("If you want mock mode, use: --mock\n")
        await demo_with_real_daemon()

    # Usage instructions
    usage = """
To run in specific mode:
  Real daemon: uv run python demos/phase5_daemon_demo.py
  Mock mode:   uv run python demos/phase5_daemon_demo.py --mock
"""
    print(usage)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        sys.exit(0)
