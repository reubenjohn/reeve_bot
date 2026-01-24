"""
Time parsing utilities for flexible time string parsing.

This module provides utilities for parsing time strings into datetime objects,
supporting various formats including ISO 8601, relative times, and keywords.

Used by MCP servers and API endpoints to provide flexible time input.
"""

from datetime import datetime, timedelta, timezone


def parse_time_string(time_str: str) -> datetime:
    """
    Parse a flexible time string into a UTC datetime.

    Supports:
    - ISO 8601: "2026-01-20T09:00:00Z", "2026-01-20T09:00:00+00:00"
    - Relative: "in 2 hours", "in 30 minutes", "in 5 days"
    - Keywords: "now"

    Args:
        time_str: The time string to parse (case-insensitive for keywords/relative)

    Returns:
        A timezone-aware datetime in UTC

    Raises:
        ValueError: If the time string cannot be parsed or is in an unsupported format

    Examples:
        >>> parse_time_string("now")
        datetime.datetime(2026, 1, 23, 10, 30, 0, tzinfo=datetime.timezone.utc)

        >>> parse_time_string("in 2 hours")
        datetime.datetime(2026, 1, 23, 12, 30, 0, tzinfo=datetime.timezone.utc)

        >>> parse_time_string("2026-01-20T09:00:00Z")
        datetime.datetime(2026, 1, 20, 9, 0, 0, tzinfo=datetime.timezone.utc)
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

    # Relative: "in X hours/minutes/days"
    if time_str_lower.startswith("in "):
        parts = time_str_lower[3:].split()
        if len(parts) == 2:
            try:
                amount = int(parts[0])
            except ValueError:
                raise ValueError(
                    f"Invalid amount in time string: '{time_str}'. " f"Amount must be an integer."
                )

            unit = parts[1].rstrip("s")  # "hours" -> "hour", "minutes" -> "minute"

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
