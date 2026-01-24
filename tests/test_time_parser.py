"""
Unit tests for time_parser utilities.

Tests the flexible time string parsing functionality, including:
- ISO 8601 timestamps
- Relative time expressions
- Keywords ("now")
- Case insensitivity
- Error handling for invalid formats
"""

from datetime import datetime, timedelta, timezone

import pytest

from reeve.utils.time_parser import parse_time_string


class TestParseTimeString:
    """Tests for parse_time_string() function."""

    def test_keyword_now(self):
        """Test parsing 'now' keyword."""
        result = parse_time_string("now")

        # Should be very close to current time (within 1 second)
        now = datetime.now(timezone.utc)
        assert abs((result - now).total_seconds()) < 1

        # Should be timezone-aware (UTC)
        assert result.tzinfo == timezone.utc

    def test_keyword_now_case_insensitive(self):
        """Test that 'now' keyword is case-insensitive."""
        for variant in ["now", "NOW", "Now", "NoW"]:
            result = parse_time_string(variant)
            now = datetime.now(timezone.utc)
            assert abs((result - now).total_seconds()) < 1

    def test_keyword_now_with_whitespace(self):
        """Test that 'now' keyword handles leading/trailing whitespace."""
        result = parse_time_string("  now  ")
        now = datetime.now(timezone.utc)
        assert abs((result - now).total_seconds()) < 1

    def test_relative_in_minutes(self):
        """Test parsing 'in X minutes' format."""
        result = parse_time_string("in 5 minutes")

        # Should be approximately 5 minutes from now
        expected = datetime.now(timezone.utc) + timedelta(minutes=5)
        assert abs((result - expected).total_seconds()) < 1

        # Should be timezone-aware (UTC)
        assert result.tzinfo == timezone.utc

    def test_relative_in_minute_singular(self):
        """Test parsing 'in 1 minute' (singular form)."""
        result = parse_time_string("in 1 minute")

        expected = datetime.now(timezone.utc) + timedelta(minutes=1)
        assert abs((result - expected).total_seconds()) < 1

    def test_relative_in_hours(self):
        """Test parsing 'in X hours' format."""
        result = parse_time_string("in 2 hours")

        # Should be approximately 2 hours from now
        expected = datetime.now(timezone.utc) + timedelta(hours=2)
        assert abs((result - expected).total_seconds()) < 1

        # Should be timezone-aware (UTC)
        assert result.tzinfo == timezone.utc

    def test_relative_in_hour_singular(self):
        """Test parsing 'in 1 hour' (singular form)."""
        result = parse_time_string("in 1 hour")

        expected = datetime.now(timezone.utc) + timedelta(hours=1)
        assert abs((result - expected).total_seconds()) < 1

    def test_relative_in_days(self):
        """Test parsing 'in X days' format."""
        result = parse_time_string("in 3 days")

        # Should be approximately 3 days from now
        expected = datetime.now(timezone.utc) + timedelta(days=3)
        assert abs((result - expected).total_seconds()) < 1

        # Should be timezone-aware (UTC)
        assert result.tzinfo == timezone.utc

    def test_relative_in_day_singular(self):
        """Test parsing 'in 1 day' (singular form)."""
        result = parse_time_string("in 1 day")

        expected = datetime.now(timezone.utc) + timedelta(days=1)
        assert abs((result - expected).total_seconds()) < 1

    def test_relative_case_insensitive(self):
        """Test that relative time expressions are case-insensitive."""
        for variant in ["in 2 hours", "IN 2 HOURS", "In 2 Hours", "iN 2 HoUrS"]:
            result = parse_time_string(variant)
            expected = datetime.now(timezone.utc) + timedelta(hours=2)
            assert abs((result - expected).total_seconds()) < 1

    def test_relative_with_whitespace(self):
        """Test that relative time expressions handle leading/trailing whitespace."""
        result = parse_time_string("  in 5 minutes  ")
        expected = datetime.now(timezone.utc) + timedelta(minutes=5)
        assert abs((result - expected).total_seconds()) < 1

    def test_iso8601_with_z(self):
        """Test parsing ISO 8601 timestamp with 'Z' suffix."""
        result = parse_time_string("2026-01-20T09:00:00Z")

        expected = datetime(2026, 1, 20, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected
        assert result.tzinfo == timezone.utc

    def test_iso8601_with_offset(self):
        """Test parsing ISO 8601 timestamp with timezone offset."""
        result = parse_time_string("2026-01-20T09:00:00+00:00")

        expected = datetime(2026, 1, 20, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected
        assert result.tzinfo == timezone.utc

    def test_iso8601_with_microseconds(self):
        """Test parsing ISO 8601 timestamp with microseconds."""
        result = parse_time_string("2026-01-20T09:00:00.123456Z")

        expected = datetime(2026, 1, 20, 9, 0, 0, 123456, tzinfo=timezone.utc)
        assert result == expected

    def test_iso8601_with_whitespace(self):
        """Test that ISO 8601 timestamps handle leading/trailing whitespace."""
        result = parse_time_string("  2026-01-20T09:00:00Z  ")
        expected = datetime(2026, 1, 20, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_invalid_format_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Could not parse time string"):
            parse_time_string("")

    def test_invalid_format_whitespace_only(self):
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="Could not parse time string"):
            parse_time_string("   ")

    def test_invalid_format_unknown_keyword(self):
        """Test that unknown keywords raise ValueError."""
        with pytest.raises(ValueError, match="Could not parse time string"):
            parse_time_string("tomorrow")

    def test_invalid_format_malformed_relative(self):
        """Test that malformed relative time expressions raise ValueError."""
        with pytest.raises(ValueError):
            parse_time_string("in 5")  # Missing unit

        with pytest.raises(ValueError):
            parse_time_string("in minutes")  # Missing amount

        with pytest.raises(ValueError):
            parse_time_string("in two hours")  # Non-numeric amount

    def test_invalid_format_unsupported_unit(self):
        """Test that unsupported time units raise ValueError."""
        with pytest.raises(ValueError, match="Could not parse time string"):
            parse_time_string("in 5 weeks")

        with pytest.raises(ValueError, match="Could not parse time string"):
            parse_time_string("in 5 months")

    def test_invalid_format_malformed_iso8601(self):
        """Test that malformed ISO 8601 timestamps raise ValueError."""
        with pytest.raises(ValueError):
            parse_time_string("2026-01-20")  # Missing time component

        with pytest.raises(ValueError):
            parse_time_string("2026-13-01T09:00:00Z")  # Invalid month

        with pytest.raises(ValueError):
            parse_time_string("not-a-date")

    def test_relative_with_zero_amount(self):
        """Test that relative time with zero amount works correctly."""
        result = parse_time_string("in 0 minutes")

        # Should be approximately now
        now = datetime.now(timezone.utc)
        assert abs((result - now).total_seconds()) < 1

    def test_relative_with_large_amount(self):
        """Test that relative time with large amounts works correctly."""
        result = parse_time_string("in 365 days")

        expected = datetime.now(timezone.utc) + timedelta(days=365)
        assert abs((result - expected).total_seconds()) < 1

    def test_relative_non_integer_amount(self):
        """Test that non-integer amounts raise ValueError."""
        with pytest.raises(ValueError, match="Invalid amount"):
            parse_time_string("in 2.5 hours")

        with pytest.raises(ValueError, match="Invalid amount"):
            parse_time_string("in five minutes")

    def test_error_message_includes_input(self):
        """Test that error messages include the invalid input string."""
        invalid_input = "invalid time string"
        with pytest.raises(ValueError, match=f"Could not parse time string: '{invalid_input}'"):
            parse_time_string(invalid_input)

    def test_error_message_includes_supported_formats(self):
        """Test that error messages mention supported formats."""
        with pytest.raises(ValueError, match="Supported formats"):
            parse_time_string("invalid")
