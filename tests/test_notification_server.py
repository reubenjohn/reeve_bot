"""
Tests for Telegram Notifier MCP Server

Tests the MCP tools provided by the Telegram Notifier MCP server.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import requests


class TestTelegramNotifierMCPTools:
    """Test the Telegram Notifier MCP tools."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Set up environment variables for testing."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "test_chat_456")

    @pytest.mark.asyncio
    async def test_send_notification_success(self):
        """Test sending a notification successfully with auto-generated session link."""
        # Need to reload the module after setting env vars
        import importlib

        import reeve.mcp.notification_server as notification_module

        importlib.reload(notification_module)
        from reeve.mcp.notification_server import send_notification

        # Create mock Context with session_id
        mock_ctx = MagicMock()
        mock_ctx.session_id = "test-session-123"

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await send_notification(
                ctx=mock_ctx,
                message="Test notification",
                priority="normal",
            )

            # Verify the request was made
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            assert "sendMessage" in call_args[0][0]
            assert call_args.kwargs["json"]["text"] == "Test notification"
            assert call_args.kwargs["json"]["chat_id"] == "test_chat_456"
            assert call_args.kwargs["json"]["disable_notification"] is False

            # Verify auto-generated link button is present
            assert "reply_markup" in call_args.kwargs["json"]
            reply_markup = call_args.kwargs["json"]["reply_markup"]
            assert "inline_keyboard" in reply_markup
            link = "https://hapi.run/sessions/test-session-123"
            assert reply_markup["inline_keyboard"][0][0]["url"] == link
            assert reply_markup["inline_keyboard"][0][0]["text"] == "View in Claude Code"

            # Verify the response
            assert "✓ Notification with link sent successfully" in result

    @pytest.mark.asyncio
    async def test_send_notification_failure(self):
        """Test handling Telegram API failure."""
        import importlib

        import reeve.mcp.notification_server as notification_module

        importlib.reload(notification_module)
        from reeve.mcp.notification_server import send_notification

        # Create mock Context
        mock_ctx = MagicMock()
        mock_ctx.session_id = "test-session-123"

        with patch("reeve.mcp.notification_server.requests.post") as mock_post:
            # Use requests.exceptions.RequestException which is what the function catches
            mock_post.side_effect = requests.exceptions.RequestException("Network error")

            result = await send_notification(
                ctx=mock_ctx,
                message="Test notification",
            )

            # Should return error message
            assert "✗ Failed to send notification" in result
            assert "Network error" in result

    @pytest.mark.asyncio
    async def test_send_notification_silent_priority(self):
        """Test that silent priority disables notifications."""
        import importlib

        import reeve.mcp.notification_server as notification_module

        importlib.reload(notification_module)
        from reeve.mcp.notification_server import send_notification

        mock_ctx = MagicMock()
        mock_ctx.session_id = "test-session-123"

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await send_notification(
                ctx=mock_ctx,
                message="Silent notification",
                priority="silent",
            )

            # Verify disable_notification is True for silent priority
            call_args = mock_post.call_args
            assert call_args.kwargs["json"]["disable_notification"] is True
            assert "✓ Notification with link sent successfully (silent)" in result

    @pytest.mark.asyncio
    async def test_send_notification_no_session_id(self):
        """Test notification when session_id is not available."""
        import importlib

        import reeve.mcp.notification_server as notification_module

        importlib.reload(notification_module)
        from reeve.mcp.notification_server import send_notification

        # Create mock Context that raises RuntimeError when accessing session_id
        mock_ctx = MagicMock()
        type(mock_ctx).session_id = PropertyMock(side_effect=RuntimeError("No session"))

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await send_notification(
                ctx=mock_ctx,
                message="Test notification",
            )

            # Verify no link button is present
            call_args = mock_post.call_args
            assert "reply_markup" not in call_args.kwargs["json"]
            assert "✓ Notification sent successfully" in result
