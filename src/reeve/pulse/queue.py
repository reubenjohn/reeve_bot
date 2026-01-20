"""
Pulse Queue Management

Core business logic for scheduling and managing pulses.
Provides async API for creating, retrieving, and updating pulse execution state.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .enums import PulsePriority, PulseStatus
from .models import Base, Pulse


class PulseQueue:
    """
    Manages the pulse queue: scheduling, retrieval, and execution tracking.

    This is the core business logic layer for pulse management. It provides
    a clean API for the MCP server, HTTP API, and daemon scheduler to interact
    with the queue.

    All database operations are async to support high concurrency.
    """

    def __init__(self, db_url: str):
        """
        Initialize the pulse queue with a database connection.

        Args:
            db_url: SQLAlchemy database URL. Examples:
                - "sqlite+aiosqlite:///~/.reeve/pulse_queue.db" (async SQLite)
                - "sqlite+aiosqlite:///:memory:" (in-memory for testing)
                - "postgresql+asyncpg://user:pass@localhost/reeve" (async Postgres)
        """
        self.engine = create_async_engine(db_url, echo=False)
        self.SessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def initialize(self) -> None:
        """
        Initialize the database schema.

        Creates all tables if they don't exist. Useful for testing with
        in-memory databases.
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def schedule_pulse(
        self,
        scheduled_at: datetime,
        prompt: str,
        priority: PulsePriority = PulsePriority.NORMAL,
        session_link: Optional[str] = None,
        sticky_notes: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        created_by: str = "system",
        max_retries: int = 3,
    ) -> int:
        """
        Schedule a new pulse.

        Args:
            scheduled_at: When to execute (UTC timezone-aware datetime)
            prompt: The instruction/context for Reeve
            priority: Urgency level (default: NORMAL)
            session_link: Optional Hapi session to resume
            sticky_notes: Optional reminder strings to inject
            tags: Optional categorization tags
            created_by: Who created this pulse (for auditing)
            max_retries: Max retry attempts on failure

        Returns:
            The pulse ID (integer)

        Example:
            >>> pulse_id = await queue.schedule_pulse(
            ...     scheduled_at=datetime(2026, 1, 20, 9, 0, tzinfo=timezone.utc),
            ...     prompt="Daily morning briefing: Review calendar and tasks",
            ...     priority=PulsePriority.NORMAL,
            ...     tags=["daily", "morning_routine"]
            ... )
        """
        async with self.SessionLocal() as session:
            pulse = Pulse(
                scheduled_at=scheduled_at,
                prompt=prompt,
                priority=priority,
                session_link=session_link,
                sticky_notes=sticky_notes,
                tags=tags,
                created_by=created_by,
                max_retries=max_retries,
                status=PulseStatus.PENDING,
            )
            session.add(pulse)
            await session.commit()
            await session.refresh(pulse)
            return pulse.id

    async def get_due_pulses(self, limit: int = 10) -> List[Pulse]:
        """
        Get pulses that are due for execution.

        Returns pulses where:
        - scheduled_at <= now
        - status = PENDING
        - Ordered by: priority DESC, scheduled_at ASC

        This ensures high-priority pulses execute first, and among same-priority
        pulses, older ones execute first (FIFO).

        Args:
            limit: Maximum number of pulses to return

        Returns:
            List of Pulse objects ready for execution
        """
        from sqlalchemy import case

        async with self.SessionLocal() as session:
            now = datetime.now(timezone.utc)

            # Define priority ordering (lower number = higher priority)
            priority_order = case(
                (Pulse.priority == PulsePriority.CRITICAL, 1),
                (Pulse.priority == PulsePriority.HIGH, 2),
                (Pulse.priority == PulsePriority.NORMAL, 3),
                (Pulse.priority == PulsePriority.LOW, 4),
                (Pulse.priority == PulsePriority.DEFERRED, 5),
                else_=6,
            )

            stmt = (
                select(Pulse)
                .where(and_(Pulse.scheduled_at <= now, Pulse.status == PulseStatus.PENDING))
                .order_by(
                    # Sort by priority (CRITICAL first)
                    priority_order,
                    # Then by time (oldest first)
                    Pulse.scheduled_at,
                )
                .limit(limit)
            )

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_upcoming_pulses(
        self,
        limit: int = 20,
        include_statuses: Optional[List[PulseStatus]] = None,
    ) -> List[Pulse]:
        """
        Get upcoming scheduled pulses (for visibility/introspection).

        Args:
            limit: Maximum number of pulses to return
            include_statuses: Filter by status (default: [PENDING])

        Returns:
            List of Pulse objects ordered by scheduled_at
        """
        if include_statuses is None:
            include_statuses = [PulseStatus.PENDING]

        async with self.SessionLocal() as session:
            stmt = (
                select(Pulse)
                .where(Pulse.status.in_(include_statuses))
                .order_by(Pulse.scheduled_at)
                .limit(limit)
            )

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_pulse(self, pulse_id: int) -> Optional[Pulse]:
        """
        Get a pulse by ID.

        Args:
            pulse_id: The pulse ID to retrieve

        Returns:
            Pulse object if found, None otherwise
        """
        async with self.SessionLocal() as session:
            return await session.get(Pulse, pulse_id)

    async def mark_processing(self, pulse_id: int) -> bool:
        """
        Mark a pulse as currently processing (prevents duplicate execution).

        Args:
            pulse_id: The pulse to mark

        Returns:
            True if successfully marked, False if pulse was already processing/completed
        """
        async with self.SessionLocal() as session:
            pulse = await session.get(Pulse, pulse_id)

            if not pulse or pulse.status != PulseStatus.PENDING:
                return False

            pulse.status = PulseStatus.PROCESSING
            await session.commit()
            return True

    async def mark_completed(self, pulse_id: int, execution_duration_ms: int) -> None:
        """
        Mark a pulse as successfully completed.

        Args:
            pulse_id: The pulse to mark
            execution_duration_ms: How long execution took
        """
        async with self.SessionLocal() as session:
            pulse = await session.get(Pulse, pulse_id)

            if pulse:
                pulse.status = PulseStatus.COMPLETED
                pulse.executed_at = datetime.now(timezone.utc)
                pulse.execution_duration_ms = execution_duration_ms
                await session.commit()

    async def mark_failed(
        self, pulse_id: int, error_message: str, should_retry: bool = True
    ) -> Optional[int]:
        """
        Mark a pulse as failed.

        If retry is enabled and max_retries not exceeded, schedules a new
        retry pulse with exponential backoff.

        Args:
            pulse_id: The pulse to mark as failed
            error_message: Description of the failure
            should_retry: Whether to attempt retry

        Returns:
            New pulse ID if retried, None otherwise
        """
        async with self.SessionLocal() as session:
            pulse = await session.get(Pulse, pulse_id)

            if not pulse:
                return None

            pulse.status = PulseStatus.FAILED
            pulse.error_message = error_message
            pulse.executed_at = datetime.now(timezone.utc)

            # Retry logic with exponential backoff
            new_pulse_id = None
            if should_retry and pulse.retry_count < pulse.max_retries:
                # Schedule retry with exponential backoff: 2^retry_count minutes
                retry_delay_minutes = 2**pulse.retry_count
                retry_at = datetime.now(timezone.utc) + timedelta(minutes=retry_delay_minutes)

                retry_pulse = Pulse(
                    scheduled_at=retry_at,
                    prompt=pulse.prompt,
                    priority=pulse.priority,
                    session_link=pulse.session_link,
                    sticky_notes=pulse.sticky_notes,
                    tags=pulse.tags,
                    created_by=f"retry_{pulse.created_by}",
                    max_retries=pulse.max_retries,
                    retry_count=pulse.retry_count + 1,
                    status=PulseStatus.PENDING,
                )

                session.add(retry_pulse)
                await session.flush()
                new_pulse_id = retry_pulse.id

            await session.commit()
            return new_pulse_id

    async def cancel_pulse(self, pulse_id: int) -> bool:
        """
        Cancel a pending pulse.

        Args:
            pulse_id: The pulse to cancel

        Returns:
            True if cancelled, False if pulse was not in cancellable state
        """
        async with self.SessionLocal() as session:
            pulse = await session.get(Pulse, pulse_id)

            if not pulse or pulse.status != PulseStatus.PENDING:
                return False

            pulse.status = PulseStatus.CANCELLED
            await session.commit()
            return True

    async def reschedule_pulse(self, pulse_id: int, new_scheduled_at: datetime) -> bool:
        """
        Reschedule a pending pulse to a different time.

        Args:
            pulse_id: The pulse to reschedule
            new_scheduled_at: New execution time

        Returns:
            True if rescheduled, False if pulse was not pending
        """
        async with self.SessionLocal() as session:
            pulse = await session.get(Pulse, pulse_id)

            if not pulse or pulse.status != PulseStatus.PENDING:
                return False

            pulse.scheduled_at = new_scheduled_at
            await session.commit()
            return True

    async def close(self) -> None:
        """
        Close the database connection.

        Should be called when shutting down to clean up resources.
        """
        await self.engine.dispose()
