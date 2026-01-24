"""
Tests for Pulse Server Helper Functions

Tests the time parsing and emoji helper functions from the Pulse Queue MCP server.
"""

from datetime import datetime, timedelta, timezone

import pytest


class TestTimeParsingHelper:
    """Test the _parse_time_string helper function."""

    def test_parse_now(self):
        """Test 'now' keyword."""
        from reeve.utils.time_parser import parse_time_string as _parse_time_string

        result = _parse_time_string("now")
        assert result.tzinfo == timezone.utc
        # Should be within 1 second of current time
        assert abs((datetime.now(timezone.utc) - result).total_seconds()) < 1

    def test_parse_iso8601_with_z(self):
        """Test ISO 8601 format with Z suffix."""
        from reeve.utils.time_parser import parse_time_string as _parse_time_string

        result = _parse_time_string("2026-01-20T09:00:00Z")
        expected = datetime(2026, 1, 20, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_iso8601_with_offset(self):
        """Test ISO 8601 format with timezone offset."""
        from reeve.utils.time_parser import parse_time_string as _parse_time_string

        result = _parse_time_string("2026-01-20T09:00:00+00:00")
        expected = datetime(2026, 1, 20, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_relative_minutes(self):
        """Test relative time: 'in X minutes'."""
        from reeve.utils.time_parser import parse_time_string as _parse_time_string

        before = datetime.now(timezone.utc)
        result = _parse_time_string("in 30 minutes")
        after = datetime.now(timezone.utc)

        # Should be 30 minutes from now
        expected_min = before + timedelta(minutes=30)
        expected_max = after + timedelta(minutes=30)

        assert expected_min <= result <= expected_max

    def test_parse_relative_hours(self):
        """Test relative time: 'in X hours'."""
        from reeve.utils.time_parser import parse_time_string as _parse_time_string

        before = datetime.now(timezone.utc)
        result = _parse_time_string("in 2 hours")
        after = datetime.now(timezone.utc)

        # Should be 2 hours from now
        expected_min = before + timedelta(hours=2)
        expected_max = after + timedelta(hours=2)

        assert expected_min <= result <= expected_max

    def test_parse_relative_days(self):
        """Test relative time: 'in X days'."""
        from reeve.utils.time_parser import parse_time_string as _parse_time_string

        before = datetime.now(timezone.utc)
        result = _parse_time_string("in 3 days")
        after = datetime.now(timezone.utc)

        # Should be 3 days from now
        expected_min = before + timedelta(days=3)
        expected_max = after + timedelta(days=3)

        assert expected_min <= result <= expected_max

    def test_parse_relative_plural(self):
        """Test relative time with plural units."""
        from reeve.utils.time_parser import parse_time_string as _parse_time_string

        # "hours" should work the same as "hour"
        result1 = _parse_time_string("in 5 hours")
        result2 = _parse_time_string("in 5 hour")

        # Both should be approximately the same time
        assert abs((result1 - result2).total_seconds()) < 1

    def test_parse_invalid_format(self):
        """Test that invalid formats raise ValueError."""
        from reeve.utils.time_parser import parse_time_string as _parse_time_string

        with pytest.raises(ValueError, match="Could not parse time string"):
            _parse_time_string("tomorrow at 9am")  # Not implemented yet

        with pytest.raises(ValueError):
            _parse_time_string("invalid_time_string")

    def test_parse_case_insensitive(self):
        """Test that parsing is case-insensitive."""
        from reeve.utils.time_parser import parse_time_string as _parse_time_string

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
