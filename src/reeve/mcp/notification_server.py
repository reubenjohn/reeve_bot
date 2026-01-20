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

import os
from typing import Annotated, Literal, Optional

import requests
from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Initialize the MCP server
mcp = FastMCP("telegram-notifier")

# Telegram Bot Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # The user's chat ID

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables are required")


# ============================================================================
# Tool Definitions
# ============================================================================


@mcp.tool()
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
            max_length=4096,
        ),
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
        ),
    ] = None,
    disable_notification: Annotated[
        bool,
        Field(
            description=(
                "If True, sends the message silently (no sound/vibration). "
                "Use for low-priority updates that don't require immediate attention.\n\n"
                "Examples: background task completions, non-urgent status updates."
            ),
        ),
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
        ),
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
    try:
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

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        return f"✓ Notification sent successfully ({priority})"

    except requests.exceptions.RequestException as e:
        return f"✗ Failed to send notification: {str(e)}"


@mcp.tool()
async def send_message_with_link(
    message: Annotated[
        str,
        Field(
            description="The notification message (see send_notification for formatting)",
            min_length=1,
            max_length=4096,
        ),
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
                "https://github.com/user/repo/pull/42",
            ],
        ),
    ],
    link_text: Annotated[
        str,
        Field(
            description="Button text or link label (e.g., 'Open Session', 'View Event', 'Review PR')",
            max_length=50,
        ),
    ] = "Open",
    parse_mode: Annotated[
        Literal["MarkdownV2", "HTML", "Markdown"] | None,
        Field(description="Message formatting mode (see send_notification)"),
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
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        # Create inline keyboard button
        reply_markup = {"inline_keyboard": [[{"text": link_text, "url": link_url}]]}

        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "reply_markup": reply_markup,
        }

        if parse_mode:
            payload["parse_mode"] = parse_mode

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        return f"✓ Notification with link sent successfully"

    except requests.exceptions.RequestException as e:
        return f"✗ Failed to send notification: {str(e)}"


# ============================================================================
# Server Entry Point
# ============================================================================


if __name__ == "__main__":
    mcp.run()
