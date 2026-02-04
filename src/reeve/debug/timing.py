"""
Timing breakdown utility for performance analysis.

Provides a context manager for measuring execution time of code blocks
with named checkpoints. Useful for profiling and debugging performance
issues in the pulse execution pipeline.

Usage:
    from reeve.debug.timing import TimingBreakdown

    with TimingBreakdown("pulse_execution") as t:
        t.mark("init")
        # ... initialization code ...
        t.mark("execute")
        # ... execution code ...
        t.mark("cleanup")
        # ... cleanup code ...

    # Logs: "pulse_execution: init=12ms, execute=890ms, cleanup=5ms, total=907ms"

    # Or capture the result without logging:
    with TimingBreakdown("pulse_execution", auto_log=False) as t:
        t.mark("step1")
        # ... code ...

    breakdown = t.get_breakdown()
    # {'step1': 12.5, 'total': 12.5}  # times in ms
"""

import logging
import time
from typing import Literal, Optional

logger = logging.getLogger(__name__)


class TimingBreakdown:
    """
    Context manager for detailed timing breakdown of code execution.

    Allows marking named checkpoints during execution and automatically
    calculates durations between marks. On exit, logs a formatted summary.

    Attributes:
        name: Identifier for this timing session
        log_level: Logging level for the summary (default: INFO)
        auto_log: Whether to automatically log on exit (default: True)
    """

    def __init__(
        self,
        name: str,
        log_level: int = logging.INFO,
        auto_log: bool = True,
    ):
        """
        Initialize a timing breakdown session.

        Args:
            name: Identifier for this timing session (used in log output)
            log_level: Logging level for the summary (default: logging.INFO)
            auto_log: Whether to automatically log on context exit (default: True)
        """
        self.name = name
        self.log_level = log_level
        self.auto_log = auto_log
        self.marks: list[tuple[str, float]] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def __enter__(self) -> "TimingBreakdown":
        """Start the timing session."""
        self.start_time = time.perf_counter()
        self.marks = []
        self.end_time = None
        return self

    def mark(self, name: str) -> None:
        """
        Record a timing checkpoint.

        The duration between this mark and the previous one (or start)
        will be calculated in the final breakdown.

        Args:
            name: Label for this checkpoint
        """
        self.marks.append((name, time.perf_counter()))

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> Literal[False]:
        """
        End the timing session and optionally log the breakdown.

        Returns:
            False (does not suppress exceptions)
        """
        self.end_time = time.perf_counter()

        if self.auto_log:
            self._log_breakdown()

        return False  # Don't suppress exceptions

    def get_breakdown(self) -> dict[str, float]:
        """
        Get timing breakdown as a dictionary.

        Returns:
            Dictionary mapping mark names to durations in milliseconds,
            plus a 'total' key with the total elapsed time.

        Example:
            {'init': 12.5, 'execute': 890.2, 'cleanup': 5.1, 'total': 907.8}
        """
        if self.start_time is None:
            return {}

        end = self.end_time if self.end_time is not None else time.perf_counter()
        result: dict[str, float] = {}

        # Calculate durations between marks
        prev_time = self.start_time
        for mark_name, mark_time in self.marks:
            duration_ms = (mark_time - prev_time) * 1000
            result[mark_name] = round(duration_ms, 2)
            prev_time = mark_time

        # Add total
        total_ms = (end - self.start_time) * 1000
        result["total"] = round(total_ms, 2)

        return result

    def _log_breakdown(self) -> None:
        """Log the timing breakdown at the configured level."""
        breakdown = self.get_breakdown()

        if not breakdown:
            logger.log(self.log_level, f"{self.name}: no timing data")
            return

        # Format: "name: mark1=12ms, mark2=890ms, total=907ms"
        parts = []
        for key, value in breakdown.items():
            if key != "total":
                parts.append(f"{key}={value:.0f}ms")

        total = breakdown.get("total", 0)
        parts.append(f"total={total:.0f}ms")

        message = f"{self.name}: {', '.join(parts)}"
        logger.log(self.log_level, message)

    def format_breakdown(self) -> str:
        """
        Get a formatted string of the timing breakdown.

        Returns:
            Formatted string like "init=12ms, execute=890ms, total=907ms"
        """
        breakdown = self.get_breakdown()

        if not breakdown:
            return "no timing data"

        parts = []
        for key, value in breakdown.items():
            if key != "total":
                parts.append(f"{key}={value:.0f}ms")

        total = breakdown.get("total", 0)
        parts.append(f"total={total:.0f}ms")

        return ", ".join(parts)


def timed_section(name: str, log_level: int = logging.INFO) -> TimingBreakdown:
    """
    Convenience function for creating a TimingBreakdown context manager.

    Args:
        name: Identifier for this timing session
        log_level: Logging level for the summary

    Returns:
        TimingBreakdown instance ready to be used as a context manager

    Example:
        with timed_section("database_query") as t:
            t.mark("connect")
            conn = await connect()
            t.mark("execute")
            result = await conn.execute(query)
            t.mark("fetch")
            rows = await result.fetchall()
    """
    return TimingBreakdown(name, log_level=log_level)
