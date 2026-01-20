"""
Pulse Queue Database Models

SQLAlchemy ORM models for the pulse queue system.
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Index, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

from .enums import PulsePriority, PulseStatus

Base = declarative_base()


class TZDateTime(TypeDecorator):
    """
    Custom DateTime type that ensures all datetime values are timezone-aware (UTC).

    SQLite doesn't natively support timezone-aware datetimes, so we need to
    manually add timezone info when loading from the database.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert timezone-aware datetime to naive UTC for storage."""
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("TZDateTime requires timezone-aware datetimes")
            # Convert to UTC and strip timezone for storage
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        """Add UTC timezone info when loading from database."""
        if value is not None:
            # Add UTC timezone to naive datetime
            return value.replace(tzinfo=timezone.utc)
        return value


class Pulse(Base):
    """
    Represents a scheduled wake-up event for Reeve.

    A pulse is the fundamental unit of Reeve's proactive behavior. It defines
    when Reeve should wake up, what it should think about, and with what urgency.

    Pulses can be:
    - Periodic (e.g., hourly heartbeat checks)
    - Aperiodic (e.g., "check ticket prices at 6:45 AM tomorrow")
    - Event-triggered (e.g., external Telegram message arrives)

    Once a pulse executes, it launches a Hapi session with the pulse's prompt
    as the initial context, allowing Reeve to take action.
    """

    __tablename__ = "pulses"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Scheduling Information
    scheduled_at = Column(
        TZDateTime,
        nullable=False,
        index=True,
        comment="When this pulse should execute (UTC timestamp)",
    )

    # Execution Context
    prompt = Column(
        Text,
        nullable=False,
        comment="The instruction/context for Reeve when this pulse fires. "
        "This becomes the initial message in the Hapi session.",
    )

    priority = Column(
        SQLEnum(PulsePriority),
        nullable=False,
        default=PulsePriority.NORMAL,
        index=True,
        comment="Execution priority (determines order when multiple pulses are due)",
    )

    # Session Continuity (Optional)
    session_link = Column(
        String(500),
        nullable=True,
        comment="Optional Hapi session ID or URL to resume existing context. "
        "If None, a new session is created.",
    )

    sticky_notes = Column(
        JSON,
        nullable=True,
        comment="Optional list of reminder strings to inject into the prompt. "
        "Example: ['Check if user replied to ski trip', 'Follow up on PR review']",
    )

    # Execution State
    status = Column(
        SQLEnum(PulseStatus),
        nullable=False,
        default=PulseStatus.PENDING,
        index=True,
        comment="Current execution status of this pulse",
    )

    # Execution Results (populated after execution)
    executed_at = Column(
        TZDateTime,
        nullable=True,
        comment="When this pulse actually executed (may differ from scheduled_at)",
    )

    execution_duration_ms = Column(
        Integer,
        nullable=True,
        comment="How long the Hapi session took to complete (milliseconds)",
    )

    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if status=FAILED. Used for debugging and retry logic.",
    )

    # Retry Logic
    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times this pulse has been retried after failure",
    )

    max_retries = Column(
        Integer,
        nullable=False,
        default=3,
        comment="Maximum retry attempts before giving up",
    )

    # Metadata
    created_at = Column(
        TZDateTime,
        nullable=False,
        server_default=func.now(),
        comment="When this pulse was created (for auditing)",
    )

    created_by = Column(
        String(100),
        nullable=False,
        default="system",
        comment="Who/what created this pulse. Examples: 'reeve', 'telegram_listener', 'user_cli'",
    )

    tags = Column(
        JSON,
        nullable=True,
        comment="Optional tags for categorization/filtering. "
        "Example: ['hourly_check', 'calendar_sync', 'snowboarding']",
    )

    # Database Indexes
    __table_args__ = (
        # Most common query: "Get all pending/processing pulses due before now, ordered by priority"
        Index("idx_pulse_execution", "status", "scheduled_at", "priority"),
        # For listing upcoming pulses: "What's on Reeve's schedule?"
        Index("idx_pulse_upcoming", "scheduled_at", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Pulse(id={self.id}, scheduled_at={self.scheduled_at}, "
            f"priority={self.priority.value}, status={self.status.value})>"
        )
