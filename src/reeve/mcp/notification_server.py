"""
MCP Server for Telegram Notifications

This server exposes tools that allow Reeve to send push notifications to the
user via Telegram. This is Reeve's "voice" - how it communicates proactively.

Environment Variables:
    TELEGRAM_BOT_TOKEN: Telegram bot token (required)
    TELEGRAM_CHAT_ID: User's Telegram chat ID (required)
    HAPI_BASE_URL: Base URL for Hapi sessions (optional, defaults to https://hapi.run)

Usage:
    Configure in ~/.config/claude-code/mcp_config.json:
    {
      "mcpServers": {
        "telegram-notifier": {
          "command": "uv",
          "args": ["run", "--directory", "/path/to/reeve-bot", "python", "-m", "reeve.mcp.notification_server"],
          "env": {
            "TELEGRAM_BOT_TOKEN": "your_bot_token",
            "TELEGRAM_CHAT_ID": "your_chat_id",
            "HAPI_BASE_URL": "https://hapi.run"
          }
        }
      }
    }
"""

import os
from typing import Annotated, Literal, Optional

import httpx
from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

# Initialize the MCP server
mcp = FastMCP("telegram-notifier")

# Telegram Bot Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # The user's chat ID
HAPI_BASE_URL = os.getenv("HAPI_BASE_URL", "https://hapi.run")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables are required")


# ============================================================================
# Tool Definitions
# ============================================================================


@mcp.tool()
async def send_notification(
    ctx: Context,
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
    priority: Annotated[
        Literal["silent", "normal", "critical"],
        Field(
            description=(
                "Notification priority level:\n"
                "- 'silent' (🔕): No alert, just logs to chat (no sound/vibration)\n"
                "- 'normal' (🔔): Standard push notification with sound (default)\n"
                "- 'critical' (🚨): High-priority alert with sound\n\n"
                "This controls both notification behavior and routing."
            ),
        ),
    ] = "normal",
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
) -> str:
    """
    Send a push notification to the user via Telegram.

    This is Reeve's primary communication channel with the user. Use this to:
    - Alert about important events (flight delays, weather alerts, etc.)
    - Provide task completion updates
    - Request user input or decisions
    - Share summaries and insights

    The tool automatically includes a "View in Claude Code" button linking to the current
    session, so the user can quickly jump back to the conversation context.

    Priority levels control notification behavior:
    - silent: No sound/vibration (for background updates)
    - normal: Standard notification with sound (default)
    - critical: High-priority alert with sound

    When to use:
    - Proactive alerts: "Something happened you should know about"
    - Task updates: "I finished X, here's the result"
    - Requests: "I need your input on Y"

    When NOT to use:
    - Responding to user messages (they're already in the chat)
    - Logging/debugging (use internal logs instead)
    - High-frequency updates (batch them into summaries)

    Examples:
        # Simple alert with auto-generated Claude Code link
        send_notification(
            message="✓ Daily briefing complete. 3 meetings today."
        )

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
        # Determine notification sound based on priority
        disable_notification = priority == "silent"

        # Auto-generate Hapi URL from session ID
        session_link_url = None
        try:
            session_id = ctx.session_id
            session_link_url = f"{HAPI_BASE_URL}/sessions/{session_id}"
        except (RuntimeError, AttributeError):
            # Session ID not available - no link button
            pass

        # Send via Telegram Bot API
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "disable_notification": disable_notification,
        }

        if parse_mode:
            payload["parse_mode"] = parse_mode

        # Add session link button if available
        if session_link_url:
            reply_markup = {
                "inline_keyboard": [[{"text": "View in Claude Code", "url": session_link_url}]]
            }
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
            response.raise_for_status()

        link_info = " with link" if session_link_url else ""
        return f"✓ Notification{link_info} sent successfully ({priority})"

    except httpx.HTTPError as e:
        return f"✗ Failed to send notification: {str(e)}"


# ============================================================================
# Server Entry Point
# ============================================================================


if __name__ == "__main__":
    mcp.run()
