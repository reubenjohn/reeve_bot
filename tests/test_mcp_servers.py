"""
Tests for MCP Servers

Tests the Pulse Queue and Telegram Notifier MCP servers.
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
import requests

from reeve.pulse.enums import PulsePriority, PulseStatus


class TestTimeParsingHelper:
    """Test the _parse_time_string helper function."""

    def test_parse_now(self):
        """Test 'now' keyword."""
        from reeve.mcp.pulse_server import _parse_time_string

        result = _parse_time_string("now")
        assert result.tzinfo == timezone.utc
        # Should be within 1 second of current time
        assert abs((datetime.now(timezone.utc) - result).total_seconds()) < 1

    def test_parse_iso8601_with_z(self):
        """Test ISO 8601 format with Z suffix."""
        from reeve.mcp.pulse_server import _parse_time_string

        result = _parse_time_string("2026-01-20T09:00:00Z")
        expected = datetime(2026, 1, 20, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_iso8601_with_offset(self):
        """Test ISO 8601 format with timezone offset."""
        from reeve.mcp.pulse_server import _parse_time_string

        result = _parse_time_string("2026-01-20T09:00:00+00:00")
        expected = datetime(2026, 1, 20, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_relative_minutes(self):
        """Test relative time: 'in X minutes'."""
        from reeve.mcp.pulse_server import _parse_time_string

        before = datetime.now(timezone.utc)
        result = _parse_time_string("in 30 minutes")
        after = datetime.now(timezone.utc)

        # Should be 30 minutes from now
        expected_min = before + timedelta(minutes=30)
        expected_max = after + timedelta(minutes=30)

        assert expected_min <= result <= expected_max

    def test_parse_relative_hours(self):
        """Test relative time: 'in X hours'."""
        from reeve.mcp.pulse_server import _parse_time_string

        before = datetime.now(timezone.utc)
        result = _parse_time_string("in 2 hours")
        after = datetime.now(timezone.utc)

        # Should be 2 hours from now
        expected_min = before + timedelta(hours=2)
        expected_max = after + timedelta(hours=2)

        assert expected_min <= result <= expected_max

    def test_parse_relative_days(self):
        """Test relative time: 'in X days'."""
        from reeve.mcp.pulse_server import _parse_time_string

        before = datetime.now(timezone.utc)
        result = _parse_time_string("in 3 days")
        after = datetime.now(timezone.utc)

        # Should be 3 days from now
        expected_min = before + timedelta(days=3)
        expected_max = after + timedelta(days=3)

        assert expected_min <= result <= expected_max

    def test_parse_relative_plural(self):
        """Test relative time with plural units."""
        from reeve.mcp.pulse_server import _parse_time_string

        # "hours" should work the same as "hour"
        result1 = _parse_time_string("in 5 hours")
        result2 = _parse_time_string("in 5 hour")

        # Both should be approximately the same time
        assert abs((result1 - result2).total_seconds()) < 1

    def test_parse_invalid_format(self):
        """Test that invalid formats raise ValueError."""
        from reeve.mcp.pulse_server import _parse_time_string

        with pytest.raises(ValueError, match="Could not parse time string"):
            _parse_time_string("tomorrow at 9am")  # Not implemented yet

        with pytest.raises(ValueError):
            _parse_time_string("invalid_time_string")

    def test_parse_case_insensitive(self):
        """Test that parsing is case-insensitive."""
        from reeve.mcp.pulse_server import _parse_time_string

        result1 = _parse_time_string("NOW")
        result2 = _parse_time_string("now")
        result3 = _parse_time_string("NoW")

        # All should be within 1 second of each other
        assert abs((result1 - result2).total_seconds()) < 1
        assert abs((result2 - result3).total_seconds()) < 1


class TestEmojiHelpers:
    """Test the emoji helper functions."""

    def test_priority_emoji(self):
        """Test priority emoji mapping."""
        from reeve.mcp.pulse_server import _priority_emoji

        assert _priority_emoji("critical") == "🚨"
        assert _priority_emoji("high") == "🔔"
        assert _priority_emoji("normal") == "⏰"
        assert _priority_emoji("low") == "📋"
        assert _priority_emoji("deferred") == "🕐"
        assert _priority_emoji("unknown") == ""  # Unknown priority

    def test_status_emoji(self):
        """Test status emoji mapping."""
        from reeve.mcp.pulse_server import _status_emoji

        assert _status_emoji("pending") == "⏳"
        assert _status_emoji("processing") == "⚙️"
        assert _status_emoji("completed") == "✅"
        assert _status_emoji("failed") == "❌"
        assert _status_emoji("cancelled") == "🚫"
        assert _status_emoji("unknown") == ""  # Unknown status


class TestPulseQueueMCPTools:
    """Test the Pulse Queue MCP tools with real functions."""

    @pytest.mark.asyncio
    async def test_schedule_pulse_with_mock_queue(self):
        """Test scheduling a pulse with a mocked queue."""
        # Import the functions directly
        import reeve.mcp.pulse_server as pulse_server_module
        from reeve.mcp.pulse_server import schedule_pulse

        # Mock the queue
        mock_queue = AsyncMock()
        mock_queue.schedule_pulse.return_value = 42
        original_queue = pulse_server_module.queue
        pulse_server_module.queue = mock_queue

        try:
            result = await schedule_pulse(
                scheduled_at="in 2 hours",
                prompt="Test pulse",
                priority="normal",
            )

            # Verify the pulse was scheduled
            mock_queue.schedule_pulse.assert_called_once()
            call_args = mock_queue.schedule_pulse.call_args

            assert call_args.kwargs["prompt"] == "Test pulse"
            assert call_args.kwargs["priority"] == PulsePriority.NORMAL
            assert call_args.kwargs["created_by"] == "reeve"

            # Verify the response
            assert "✓ Pulse scheduled successfully" in result
            assert "Pulse ID: 42" in result
        finally:
            pulse_server_module.queue = original_queue

    @pytest.mark.asyncio
    async def test_schedule_pulse_invalid_time(self):
        """Test scheduling a pulse with invalid time format."""
        import reeve.mcp.pulse_server as pulse_server_module
        from reeve.mcp.pulse_server import schedule_pulse

        mock_queue = AsyncMock()
        original_queue = pulse_server_module.queue
        pulse_server_module.queue = mock_queue

        try:
            result = await schedule_pulse(
                scheduled_at="invalid_time",
                prompt="Test pulse",
                priority="normal",
            )

            # Should return error message
            assert "✗ Failed to schedule pulse" in result
            assert "Could not parse time string" in result

            # Queue should not be called
            mock_queue.schedule_pulse.assert_not_called()
        finally:
            pulse_server_module.queue = original_queue


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
            assert reply_markup["inline_keyboard"][0][0]["url"] == "https://hapi.run/sessions/test-session-123"
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


class TestPulseQueueMCPIntegration:
    """Integration tests with real PulseQueue."""

    @pytest.mark.asyncio
    async def test_full_pulse_lifecycle(self):
        """Test scheduling, listing, and cancelling a pulse."""
        import reeve.mcp.pulse_server as pulse_server_module
        from reeve.mcp.pulse_server import cancel_pulse, list_upcoming_pulses, schedule_pulse
        from reeve.pulse.queue import PulseQueue

        # Create in-memory database
        queue = PulseQueue("sqlite+aiosqlite:///:memory:")
        await queue.initialize()
        original_queue = pulse_server_module.queue
        pulse_server_module.queue = queue

        try:
            # Schedule a pulse
            result = await schedule_pulse(
                scheduled_at="in 1 hour",
                prompt="Integration test pulse",
                priority="normal",
            )

            assert "✓ Pulse scheduled successfully" in result
            assert "Pulse ID: 1" in result

            # List pulses
            result = await list_upcoming_pulses()
            assert "Integration test pulse" in result
            assert "[0001]" in result

            # Cancel the pulse
            result = await cancel_pulse(pulse_id=1)
            assert "✓ Pulse 1 cancelled successfully" in result

            # List should now be empty (cancelled pulses excluded by default)
            result = await list_upcoming_pulses()
            assert "No upcoming pulses scheduled" in result

            await queue.close()
        finally:
            pulse_server_module.queue = original_queue
