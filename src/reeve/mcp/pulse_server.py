"""
MCP Server for Pulse Queue Management

This server exposes tools that allow Reeve (Claude Code) to proactively manage
its own scheduling. Reeve can set alarms, check its upcoming schedule, and
cancel or reschedule tasks.

Usage:
    Configure in ~/.config/claude-code/mcp_config.json:
    {
      "mcpServers": {
        "pulse-queue": {
          "command": "uv",
          "args": ["run", "--directory", "/path/to/reeve_bot", "python", "-m", "reeve.mcp.pulse_server"]
        }
      }
    }
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.queue import PulseQueue

# Initialize the MCP server
mcp = FastMCP("pulse-queue")

# Initialize the pulse queue (database connection)
DB_PATH = os.getenv("PULSE_DB_PATH", "~/.reeve/pulse_queue.db")
queue = PulseQueue(f"sqlite+aiosqlite:///{os.path.expanduser(DB_PATH)}")


# ============================================================================
# Tool Definitions
# ============================================================================


@mcp.tool()
async def schedule_pulse(
    scheduled_at: Annotated[
        str,
        Field(
            description=(
                "When to execute this pulse. Accepts multiple formats:\n"
                "- ISO 8601 timestamp: '2026-01-20T09:00:00Z'\n"
                "- Relative time: 'in 2 hours', 'in 30 minutes', 'tomorrow at 9am'\n"
                "- Special keywords: 'now' (immediate), 'tonight' (today at 10pm), 'tomorrow morning' (tomorrow at 8am)\n\n"
                "IMPORTANT: All times are interpreted in the user's local timezone unless a UTC 'Z' suffix is provided."
            ),
            examples=["2026-01-20T09:00:00Z", "in 2 hours", "tomorrow at 9am", "now"],
        ),
    ],
    prompt: Annotated[
        str,
        Field(
            description=(
                "The instruction or context for Reeve when this pulse fires. "
                "This becomes the initial message in the spawned Hapi session.\n\n"
                "Be specific and action-oriented. Good examples:\n"
                "- 'Check flight status for UA123 and notify user if delayed'\n"
                "- 'Daily morning briefing: review calendar, check email, summarize priorities'\n"
                "- 'Follow up: Did user reply to the snowboarding trip proposal?'\n\n"
                "Avoid vague prompts like 'check things' or 'do stuff'."
            ),
            min_length=10,
            max_length=2000,
        ),
    ],
    priority: Annotated[
        Literal["critical", "high", "normal", "low", "deferred"],
        Field(
            description=(
                "Urgency level for this pulse. Determines execution order when multiple pulses are due:\n\n"
                "- 'critical' (🚨): Emergencies, user messages, system failures. Interrupts deep work.\n"
                "- 'high' (🔔): Important external events, user-facing tasks, scheduled alarms.\n"
                "- 'normal' (⏰): Regular maintenance, periodic checks, calendar reminders. (DEFAULT)\n"
                "- 'low' (📋): Background tasks, cleanup, non-urgent maintenance.\n"
                "- 'deferred' (🕐): Intentionally postponed tasks, snoozed items.\n\n"
                "Default: 'normal'"
            ),
        ),
    ] = "normal",
    session_link: Annotated[
        Optional[str],
        Field(
            description=(
                "Optional Hapi session ID or URL to resume existing context. "
                "If provided, the pulse will continue an existing conversation rather than starting fresh.\n\n"
                "Example: 'hapi://session/abc123' or just 'abc123'\n\n"
                "Leave empty to create a new session (most common)."
            ),
        ),
    ] = None,
    sticky_notes: Annotated[
        Optional[list[str]],
        Field(
            description=(
                "Optional list of reminder strings to inject into the prompt when the pulse fires. "
                "Use this to carry forward context between pulses.\n\n"
                "Examples:\n"
                "- ['User asked about snowboarding trip on Monday', 'Check if anyone replied in group chat']\n"
                "- ['Flight departs at 6:45 AM', 'TSA PreCheck lane available']\n\n"
                "These will be prepended to the main prompt with clear formatting."
            ),
        ),
    ] = None,
    tags: Annotated[
        Optional[list[str]],
        Field(
            description=(
                "Optional categorization tags for filtering and organization. "
                "Useful for querying related pulses or understanding patterns.\n\n"
                "Examples: ['daily', 'morning_routine'], ['trip_planning', 'japan'], ['follow_up', 'github']"
            ),
        ),
    ] = None,
) -> str:
    """
    Schedule a new pulse (wake-up event) for Reeve.

    This is Reeve's primary tool for proactive behavior. Use this to schedule
    future tasks, set reminders, or create follow-up checks.

    When to use:
    - Set alarms: "Remind me to check ticket prices tomorrow at 8am"
    - Schedule follow-ups: "Check if user replied in 2 hours"
    - Create recurring checks: "Every morning at 9am, review calendar"
    - Defer tasks: "I can't handle this now, wake me up tonight to finish"

    When NOT to use:
    - Immediate actions (just do them now)
    - One-time informational tasks (use memory/notes instead)

    Examples:
        # Set a morning briefing
        schedule_pulse(
            scheduled_at="tomorrow at 9am",
            prompt="Daily morning briefing: review calendar, check email, summarize priorities",
            priority="normal",
            tags=["daily", "morning_routine"]
        )

        # Follow up on a pending task
        schedule_pulse(
            scheduled_at="in 2 hours",
            prompt="Check if user replied to the snowboarding trip proposal in group chat",
            priority="high",
            sticky_notes=["Sent message at 2:30 PM", "Waiting for Alex and Jamie to confirm"],
            tags=["follow_up", "social"]
        )

        # Critical pre-departure check
        schedule_pulse(
            scheduled_at="2026-01-20T06:00:00Z",
            prompt="Check flight status for UA123 and notify user immediately if delayed",
            priority="critical",
            tags=["travel", "urgent"]
        )

    Returns:
        Confirmation message with the pulse ID and scheduled time
    """
    try:
        # Parse scheduled_at (handle relative times, keywords, etc.)
        parsed_time = _parse_time_string(scheduled_at)

        # Create the pulse
        pulse_id = await queue.schedule_pulse(
            scheduled_at=parsed_time,
            prompt=prompt,
            priority=PulsePriority(priority),
            session_link=session_link,
            sticky_notes=sticky_notes,
            tags=tags,
            created_by="reeve",
        )

        # Format response
        time_str = parsed_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        return (
            f"✓ Pulse scheduled successfully\n\n"
            f"Pulse ID: {pulse_id}\n"
            f"Scheduled: {time_str}\n"
            f"Priority: {priority} {_priority_emoji(priority)}\n"
            f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}"
        )
    except Exception as e:
        return f"✗ Failed to schedule pulse: {str(e)}"


@mcp.tool()
async def list_upcoming_pulses(
    limit: Annotated[
        int,
        Field(
            description="Maximum number of pulses to return (default: 20, max: 100)",
            ge=1,
            le=100,
        ),
    ] = 20,
    include_completed: Annotated[
        bool,
        Field(
            description="Whether to include recently completed pulses (default: False, only show pending)"
        ),
    ] = False,
) -> str:
    """
    List upcoming scheduled pulses.

    Use this to check Reeve's schedule and understand what tasks are coming up.
    Useful for:
    - Seeing what's on the agenda
    - Verifying a pulse was scheduled correctly
    - Detecting scheduling conflicts
    - Understanding workload distribution

    Examples:
        # Check what's coming up
        list_upcoming_pulses(limit=10)

        # Review recent history
        list_upcoming_pulses(limit=20, include_completed=True)

    Returns:
        Formatted list of pulses with time, priority, and prompt preview
    """
    try:
        statuses = [PulseStatus.PENDING]
        if include_completed:
            statuses.extend([PulseStatus.COMPLETED, PulseStatus.PROCESSING])

        pulses = await queue.get_upcoming_pulses(limit=limit, include_statuses=statuses)

        if not pulses:
            return "No upcoming pulses scheduled. The schedule is clear."

        # Format as a table
        lines = ["Upcoming Pulses:\n"]
        now = datetime.now(timezone.utc)

        for pulse in pulses:
            # Calculate time until pulse
            time_delta = pulse.scheduled_at - now
            if time_delta.total_seconds() < 0:
                time_str = "OVERDUE"
            elif time_delta.total_seconds() < 3600:
                time_str = f"in {int(time_delta.total_seconds() / 60)}m"
            elif time_delta.total_seconds() < 86400:
                time_str = f"in {int(time_delta.total_seconds() / 3600)}h"
            else:
                time_str = pulse.scheduled_at.strftime("%b %d %H:%M")

            emoji = _priority_emoji(pulse.priority.value)
            status_emoji = _status_emoji(pulse.status.value)
            prompt_preview = pulse.prompt[:60] + "..." if len(pulse.prompt) > 60 else pulse.prompt

            lines.append(
                f"{status_emoji} [{pulse.id:04d}] {emoji} {time_str:12s} | {prompt_preview}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"✗ Failed to list pulses: {str(e)}"


@mcp.tool()
async def cancel_pulse(
    pulse_id: Annotated[
        int,
        Field(description="The ID of the pulse to cancel (from list_upcoming_pulses)", gt=0),
    ],
) -> str:
    """
    Cancel a scheduled pulse.

    Use this when a task is no longer needed or circumstances have changed.

    Examples:
        # User already handled the task manually
        cancel_pulse(pulse_id=42)

        # Event was cancelled
        cancel_pulse(pulse_id=123)

    Returns:
        Confirmation message or error if pulse couldn't be cancelled
    """
    try:
        success = await queue.cancel_pulse(pulse_id)

        if success:
            return f"✓ Pulse {pulse_id} cancelled successfully"
        else:
            return f"✗ Could not cancel pulse {pulse_id} (may be already completed or not found)"
    except Exception as e:
        return f"✗ Failed to cancel pulse: {str(e)}"


@mcp.tool()
async def reschedule_pulse(
    pulse_id: Annotated[
        int,
        Field(description="The ID of the pulse to reschedule (from list_upcoming_pulses)", gt=0),
    ],
    new_scheduled_at: Annotated[
        str,
        Field(
            description=(
                "New execution time. Accepts same formats as schedule_pulse:\n"
                "- ISO 8601: '2026-01-20T09:00:00Z'\n"
                "- Relative: 'in 2 hours', 'tomorrow at 9am'\n"
                "- Keywords: 'tonight', 'tomorrow morning'"
            ),
            examples=["in 2 hours", "tomorrow at 9am", "2026-01-20T15:00:00Z"],
        ),
    ],
) -> str:
    """
    Reschedule a pulse to a different time.

    Use this when timing needs to change but the task itself remains relevant.

    Examples:
        # Postpone to tomorrow
        reschedule_pulse(pulse_id=42, new_scheduled_at="tomorrow at 9am")

        # Move earlier
        reschedule_pulse(pulse_id=123, new_scheduled_at="in 30 minutes")

    Returns:
        Confirmation message with old and new times
    """
    try:
        parsed_time = _parse_time_string(new_scheduled_at)
        success = await queue.reschedule_pulse(pulse_id, parsed_time)

        if success:
            time_str = parsed_time.strftime("%Y-%m-%d %H:%M:%S %Z")
            return f"✓ Pulse {pulse_id} rescheduled to {time_str}"
        else:
            return (
                f"✗ Could not reschedule pulse {pulse_id} (may be already completed or not found)"
            )
    except Exception as e:
        return f"✗ Failed to reschedule pulse: {str(e)}"


# ============================================================================
# Helper Functions
# ============================================================================


def _parse_time_string(time_str: str) -> datetime:
    """
    Parse a flexible time string into a UTC datetime.

    Supports:
    - ISO 8601: "2026-01-20T09:00:00Z"
    - Relative: "in 2 hours", "in 30 minutes"
    - Keywords: "now", "tonight", "tomorrow morning"

    TODO: Integrate with a proper NLP library (dateparser, parsedatetime)
    For now, implement basic cases.
    """
    time_str = time_str.strip()

    # ISO 8601 (check before lowercasing to preserve 'T')
    if "T" in time_str or time_str.endswith("Z") or time_str.endswith("+00:00"):
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))

    # Convert to lowercase for keyword/relative matching
    time_str_lower = time_str.lower()

    # Keyword: "now"
    if time_str_lower == "now":
        return datetime.now(timezone.utc)

    # Relative: "in X hours/minutes"
    if time_str_lower.startswith("in "):
        parts = time_str_lower[3:].split()
        if len(parts) == 2:
            amount = int(parts[0])
            unit = parts[1].rstrip("s")  # "hours" -> "hour"

            if unit == "minute":
                return datetime.now(timezone.utc) + timedelta(minutes=amount)
            elif unit == "hour":
                return datetime.now(timezone.utc) + timedelta(hours=amount)
            elif unit == "day":
                return datetime.now(timezone.utc) + timedelta(days=amount)

    # Fallback: raise error for unimplemented formats
    raise ValueError(
        f"Could not parse time string: '{time_str}'. "
        f"Supported formats: ISO 8601, 'now', 'in X hours/minutes/days'"
    )


def _priority_emoji(priority: str) -> str:
    """Map priority to emoji for visual scanning."""
    return {
        "critical": "🚨",
        "high": "🔔",
        "normal": "⏰",
        "low": "📋",
        "deferred": "🕐",
    }.get(priority, "")


def _status_emoji(status: str) -> str:
    """Map status to emoji for visual scanning."""
    return {
        "pending": "⏳",
        "processing": "⚙️",
        "completed": "✅",
        "failed": "❌",
        "cancelled": "🚫",
    }.get(status, "")


# ============================================================================
# Server Entry Point
# ============================================================================


if __name__ == "__main__":
    mcp.run()
