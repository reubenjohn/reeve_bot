# MCP Integration Design

## Overview

This document specifies the MCP (Model Context Protocol) servers that Reeve uses to interact with the Pulse Queue system and send notifications. These servers expose tools that Reeve can call directly from within Hapi/Claude Code sessions.

## MCP Server 1: Pulse Queue Server

**Module**: `src/reeve/mcp/pulse_server.py`

**Purpose**: Allow Reeve to manage its own schedule by creating, viewing, and modifying pulses.

**Connection Type**: stdio (spawned on-demand by Reeve)

### Implementation

```python
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

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent
from pydantic import Field
from typing import Annotated, Literal, Optional
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
import os

from reeve.pulse.queue import PulseQueue
from reeve.pulse.enums import PulsePriority, PulseStatus

# Initialize the MCP server
app = Server("pulse-queue")

# Initialize the pulse queue (database connection)
DB_PATH = os.getenv("PULSE_DB_PATH", "~/.reeve/pulse_queue.db")
queue = PulseQueue(f"sqlite+aiosqlite:///{os.path.expanduser(DB_PATH)}")


# ============================================================================
# Tool Definitions
# ============================================================================

@app.tool()
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
            examples=["2026-01-20T09:00:00Z", "in 2 hours", "tomorrow at 9am", "now"]
        )
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
            max_length=2000
        )
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
        )
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
        )
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
        )
    ] = None,
    tags: Annotated[
        Optional[list[str]],
        Field(
            description=(
                "Optional categorization tags for filtering and organization. "
                "Useful for querying related pulses or understanding patterns.\n\n"
                "Examples: ['daily', 'morning_routine'], ['trip_planning', 'japan'], ['follow_up', 'github']"
            ),
        )
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


@app.tool()
async def list_upcoming_pulses(
    limit: Annotated[
        int,
        Field(
            description="Maximum number of pulses to return (default: 20, max: 100)",
            ge=1,
            le=100
        )
    ] = 20,
    include_completed: Annotated[
        bool,
        Field(
            description="Whether to include recently completed pulses (default: False, only show pending)"
        )
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


@app.tool()
async def cancel_pulse(
    pulse_id: Annotated[
        int,
        Field(
            description="The ID of the pulse to cancel (from list_upcoming_pulses)",
            gt=0
        )
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
    success = await queue.cancel_pulse(pulse_id)

    if success:
        return f"✓ Pulse {pulse_id} cancelled successfully"
    else:
        return f"✗ Could not cancel pulse {pulse_id} (may be already completed or not found)"


@app.tool()
async def reschedule_pulse(
    pulse_id: Annotated[
        int,
        Field(
            description="The ID of the pulse to reschedule (from list_upcoming_pulses)",
            gt=0
        )
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
            examples=["in 2 hours", "tomorrow at 9am", "2026-01-20T15:00:00Z"]
        )
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
    parsed_time = _parse_time_string(new_scheduled_at)
    success = await queue.reschedule_pulse(pulse_id, parsed_time)

    if success:
        time_str = parsed_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        return f"✓ Pulse {pulse_id} rescheduled to {time_str}"
    else:
        return f"✗ Could not reschedule pulse {pulse_id} (may be already completed or not found)"


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
    time_str = time_str.strip().lower()

    # Keyword: "now"
    if time_str == "now":
        return datetime.now(timezone.utc)

    # ISO 8601
    if "T" in time_str or time_str.endswith("Z"):
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))

    # Relative: "in X hours/minutes"
    if time_str.startswith("in "):
        parts = time_str[3:].split()
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

async def main():
    """Run the MCP server on stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## MCP Server 2: Telegram Notification Server

**Module**: `src/reeve/mcp/notification_server.py`

**Purpose**: Allow Reeve to send push notifications to the user via Telegram.

**Connection Type**: stdio (spawned on-demand by Reeve)

### Implementation

```python
"""
MCP Server for Telegram Notifications

This server exposes tools that allow Reeve to send push notifications to the
user via Telegram. This is Reeve's "voice" - how it communicates proactively.

Usage:
    Configure in ~/.config/claude-code/mcp_config.json:
    {
      "mcpServers": {
        "telegram-notifier": {
          "command": "uv",
          "args": ["run", "--directory", "/path/to/reeve_bot", "python", "-m", "reeve.mcp.notification_server"]
        }
      }
    }
"""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent
from pydantic import Field
from typing import Annotated, Literal, Optional
import os
import requests

# Initialize the MCP server
app = Server("telegram-notifier")

# Telegram Bot Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # The user's chat ID

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError(
        "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables are required"
    )


# ============================================================================
# Tool Definitions
# ============================================================================

@app.tool()
async def send_notification(
    message: Annotated[
        str,
        Field(
            description=(
                "The notification message to send (up to 4096 characters). "
                "Keep it concise and actionable - this is a push notification.\n\n"
                "Good examples:\n"
                "- '🔔 Powder Alert: 18 inches forecast for Mammoth this weekend'\n"
                "- '✓ Daily briefing complete. 3 meetings today, 2 high-priority emails.'\n"
                "- '🚨 Flight UA123 delayed 2 hours. New departure: 10:30 AM'\n\n"
                "If parse_mode is set, you can use formatting:\n"
                "- MarkdownV2: *bold*, _italic_, `code`, [link](url)\n"
                "- HTML: <b>bold</b>, <i>italic</i>, <code>code</code>, <a href='url'>link</a>"
            ),
            min_length=1,
            max_length=4096
        )
    ],
    parse_mode: Annotated[
        Literal["MarkdownV2", "HTML", "Markdown"] | None,
        Field(
            description=(
                "Optional message formatting mode:\n"
                "- 'MarkdownV2': Markdown formatting (recommended) - *bold*, _italic_, `code`\n"
                "- 'HTML': HTML formatting - <b>bold</b>, <i>italic</i>, <code>code</code>\n"
                "- 'Markdown': Legacy Markdown (deprecated, use MarkdownV2)\n"
                "- None: Plain text (default)\n\n"
                "Use MarkdownV2 for rich notifications, None for simple alerts."
            ),
        )
    ] = None,
    disable_notification: Annotated[
        bool,
        Field(
            description=(
                "If True, sends the message silently (no sound/vibration). "
                "Use for low-priority updates that don't require immediate attention.\n\n"
                "Examples: background task completions, non-urgent status updates."
            ),
        )
    ] = False,
    priority: Annotated[
        Literal["silent", "normal", "critical"],
        Field(
            description=(
                "Notification priority level:\n"
                "- 'silent' (🔕): No alert, just logs to chat (disable_notification=True)\n"
                "- 'normal' (🔔): Standard push notification (default)\n"
                "- 'critical' (🚨): High-priority alert (future: may override DND)\n\n"
                "This is a semantic hint for future notification routing."
            ),
        )
    ] = "normal",
) -> str:
    """
    Send a push notification to the user via Telegram.

    This is Reeve's primary communication channel with the user. Use this to:
    - Alert about important events (flight delays, weather alerts, etc.)
    - Provide task completion updates
    - Request user input or decisions
    - Share summaries and insights

    When to use:
    - Proactive alerts: "Something happened you should know about"
    - Task updates: "I finished X, here's the result"
    - Requests: "I need your input on Y"

    When NOT to use:
    - Responding to user messages (they're already in the chat)
    - Logging/debugging (use internal logs instead)
    - High-frequency updates (batch them into summaries)

    Examples:
        # Simple alert
        send_notification("✓ Daily briefing complete. 3 meetings today.")

        # Formatted urgent alert
        send_notification(
            message="*URGENT*: Flight UA123 delayed 2 hours\\nNew departure: 10:30 AM",
            parse_mode="MarkdownV2",
            priority="critical"
        )

        # Silent background update
        send_notification(
            message="📋 Archived 47 old notes to Diary/2026-01/",
            priority="silent"
        )

    Returns:
        Confirmation message or error details
    """
    # Handle priority -> disable_notification mapping
    if priority == "silent":
        disable_notification = True

    # Send via Telegram Bot API
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_notification": disable_notification,
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        return f"✓ Notification sent successfully ({priority})"

    except requests.exceptions.RequestException as e:
        return f"✗ Failed to send notification: {str(e)}"


@app.tool()
async def send_message_with_link(
    message: Annotated[
        str,
        Field(
            description="The notification message (see send_notification for formatting)",
            min_length=1,
            max_length=4096
        )
    ],
    link_url: Annotated[
        str,
        Field(
            description=(
                "URL to include as a clickable button or inline link.\n"
                "Examples: Hapi session URL, calendar event, Google Doc, GitHub PR"
            ),
            examples=[
                "https://hapi.example.com/session/abc123",
                "https://calendar.google.com/event?eid=xyz",
                "https://github.com/user/repo/pull/42"
            ]
        )
    ],
    link_text: Annotated[
        str,
        Field(
            description="Button text or link label (e.g., 'Open Session', 'View Event', 'Review PR')",
            max_length=50
        )
    ] = "Open",
    parse_mode: Annotated[
        Literal["MarkdownV2", "HTML", "Markdown"] | None,
        Field(description="Message formatting mode (see send_notification)")
    ] = None,
) -> str:
    """
    Send a notification with a clickable link button.

    Use this when the notification naturally leads to an action (opening a URL).
    This provides a better UX than embedding URLs in message text.

    Examples:
        # Link to a Hapi session
        send_message_with_link(
            message="🔔 I've started research on the Japan trip. Take a look when you have time.",
            link_url="https://hapi.example.com/session/abc123",
            link_text="Open Session"
        )

        # Link to a calendar event
        send_message_with_link(
            message="📅 Reminder: Team standup in 15 minutes",
            link_url="https://calendar.google.com/event?eid=xyz",
            link_text="View Event"
        )

    Returns:
        Confirmation message or error details
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    # Create inline keyboard button
    reply_markup = {
        "inline_keyboard": [[
            {"text": link_text, "url": link_url}
        ]]
    }

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "reply_markup": reply_markup,
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        return f"✓ Notification with link sent successfully"

    except requests.exceptions.RequestException as e:
        return f"✗ Failed to send notification: {str(e)}"


# ============================================================================
# Server Entry Point
# ============================================================================

async def main():
    """Run the MCP server on stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## Configuration

### MCP Client Configuration

Add to `~/.config/claude-code/mcp_config.json`:

```json
{
  "mcpServers": {
    "pulse-queue": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/home/reuben/workspace/reeve_bot",
        "python",
        "-m",
        "reeve.mcp.pulse_server"
      ],
      "env": {
        "PULSE_DB_PATH": "/home/reuben/.reeve/pulse_queue.db"
      }
    },
    "telegram-notifier": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/home/reuben/workspace/reeve_bot",
        "python",
        "-m",
        "reeve.mcp.notification_server"
      ],
      "env": {
        "TELEGRAM_BOT_TOKEN": "your_bot_token_here",
        "TELEGRAM_CHAT_ID": "your_chat_id_here"
      }
    }
  }
}
```

**Security Note**: The bot token is sensitive. Consider using a secrets manager or environment variable injection instead of hardcoding in the config.

### Environment Variables

**Required**:
- `TELEGRAM_BOT_TOKEN`: Bot API token from @BotFather
- `TELEGRAM_CHAT_ID`: User's chat ID (get from /start message)

**Optional**:
- `PULSE_DB_PATH`: Path to SQLite database (default: `~/.reeve/pulse_queue.db`)

## Design Principles

### 1. Type Safety with Pydantic

All tool parameters use `Annotated[Type, Field(...)]` to provide:
- Runtime validation (Pydantic)
- IDE autocomplete
- Auto-generated MCP documentation
- Clear error messages

### 2. Comprehensive Documentation

Each tool has:
- **Docstring**: High-level purpose and usage
- **Field descriptions**: Detailed parameter explanations
- **Examples**: Concrete use cases
- **When to use / When NOT to use**: Decision guidance

This helps Reeve (Claude) make intelligent decisions about when to call tools.

### 3. User-Friendly Formatting

- **Emojis**: Visual priority/status indicators
- **Relative times**: "in 2 hours" vs. ISO timestamps
- **Concise output**: Essential info only, no clutter

### 4. Error Handling

- **Graceful failures**: Return error strings, don't raise exceptions
- **Actionable messages**: "Could not cancel pulse (not found)" vs. "Error 404"
- **Success confirmation**: Always confirm what happened

## Testing MCP Tools

### Manual Testing

```bash
# Terminal 1: Start MCP server
uv run python -m reeve.mcp.pulse_server

# Terminal 2: Send test input (MCP JSON-RPC protocol)
echo '{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "schedule_pulse",
    "arguments": {
      "scheduled_at": "in 5 minutes",
      "prompt": "Test pulse",
      "priority": "normal"
    }
  }
}' | uv run python -m reeve.mcp.pulse_server
```

### Integration Testing

Use the Hapi/Claude Code test environment to call tools and verify behavior.

## Next Steps

See **[03_DEPLOYMENT.md](03_DEPLOYMENT.md)** for production deployment, systemd configuration, and monitoring setup.
