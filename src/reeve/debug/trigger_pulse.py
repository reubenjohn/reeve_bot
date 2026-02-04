"""
Manual pulse trigger for testing.

This CLI tool allows you to manually schedule and execute test pulses
without going through the normal daemon scheduler. Useful for:
- Testing pulse execution
- Debugging Hapi/Claude Code integration
- Verifying queue operations

Usage:
    uv run python -m reeve.debug.trigger_pulse "Test prompt"
    uv run python -m reeve.debug.trigger_pulse --priority high "Urgent"
    uv run python -m reeve.debug.trigger_pulse --dry-run "Test"
    uv run python -m reeve.debug.trigger_pulse --schedule-only "Later task"
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

from reeve.pulse.enums import PulsePriority
from reeve.pulse.executor import PulseExecutor
from reeve.pulse.queue import PulseQueue
from reeve.utils.config import get_config

# Configure logging for CLI output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("reeve.debug.trigger_pulse")


def parse_priority(priority_str: str) -> PulsePriority:
    """Convert string priority to PulsePriority enum."""
    priority_map = {
        "critical": PulsePriority.CRITICAL,
        "high": PulsePriority.HIGH,
        "normal": PulsePriority.NORMAL,
        "low": PulsePriority.LOW,
        "deferred": PulsePriority.DEFERRED,
    }
    return priority_map[priority_str.lower()]


async def run_trigger(args: argparse.Namespace) -> int:
    """
    Execute the trigger pulse workflow.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    config = get_config()

    # Initialize queue
    queue = PulseQueue(config.pulse_db_url)
    await queue.initialize()

    try:
        priority = parse_priority(args.priority)

        # Schedule the pulse
        pulse_id = await queue.schedule_pulse(
            scheduled_at=datetime.now(timezone.utc),
            prompt=args.prompt,
            priority=priority,
            tags=["debug", "manual"],
            created_by="trigger_pulse_cli",
        )

        logger.info(f"Scheduled pulse #{pulse_id} with priority={priority.value}")

        if args.schedule_only:
            print(f"Pulse #{pulse_id} scheduled (schedule-only mode, not executing)")
            return 0

        # Retrieve the pulse for execution
        pulse = await queue.get_pulse(pulse_id)
        if not pulse:
            logger.error(f"Could not retrieve pulse #{pulse_id}")
            return 1

        # Mark as processing
        if not await queue.mark_processing(pulse_id):
            logger.error(f"Could not mark pulse #{pulse_id} as processing")
            return 1

        # Initialize executor
        executor = PulseExecutor(
            hapi_command=config.hapi_command,
            desk_path=config.reeve_desk_path,
        )

        # Build full prompt with any sticky notes
        full_prompt = executor.build_prompt(pulse.prompt, pulse.sticky_notes)

        if args.dry_run:
            logger.info("[DRY RUN] Would execute pulse with prompt:")
            print(f"\n--- Prompt ---\n{full_prompt}\n--- End Prompt ---\n")
            logger.info(f"[DRY RUN] Hapi command: {config.hapi_command}")
            logger.info(f"[DRY RUN] Working directory: {config.reeve_desk_path}")

            # Mark completed for dry run
            await queue.mark_completed(pulse_id, execution_duration_ms=0)
            print(f"Pulse #{pulse_id} dry-run completed successfully")
            return 0

        # Execute the pulse
        logger.info(f"Executing pulse #{pulse_id}...")
        start_time = datetime.now(timezone.utc)

        try:
            result = await executor.execute(
                prompt=full_prompt,
                session_id=pulse.session_id,
            )

            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Mark completed
            await queue.mark_completed(pulse_id, execution_duration_ms=duration_ms)

            print(f"\nPulse #{pulse_id} completed successfully")
            print(f"Duration: {duration_ms}ms")
            if result.session_id:
                print(f"Session ID: {result.session_id}")

            if args.verbose:
                print(f"\n--- STDOUT ---\n{result.stdout}")
                if result.stderr:
                    print(f"\n--- STDERR ---\n{result.stderr}")

            return 0

        except RuntimeError as e:
            # Execution failed
            error_msg = str(e)
            await queue.mark_failed(pulse_id, error_msg, should_retry=False)
            logger.error(f"Pulse #{pulse_id} failed: {error_msg}")
            return 1

    finally:
        await queue.close()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manually trigger a test pulse",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Simple test pulse
    uv run python -m reeve.debug.trigger_pulse "Hello, this is a test"

    # High priority pulse
    uv run python -m reeve.debug.trigger_pulse --priority high "Urgent test"

    # Dry run (doesn't execute Hapi)
    uv run python -m reeve.debug.trigger_pulse --dry-run "Check what would happen"

    # Schedule only (doesn't execute immediately)
    uv run python -m reeve.debug.trigger_pulse --schedule-only "Execute later"
        """,
    )
    parser.add_argument("prompt", help="The prompt for the pulse")
    parser.add_argument(
        "--priority",
        choices=["critical", "high", "normal", "low", "deferred"],
        default="normal",
        help="Pulse priority (default: normal)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Schedule and mark complete without calling Hapi",
    )
    parser.add_argument(
        "--schedule-only",
        action="store_true",
        help="Only schedule, don't execute (useful for testing queue)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show full stdout/stderr from execution",
    )

    args = parser.parse_args()

    # Run the async workflow
    exit_code = asyncio.run(run_trigger(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
