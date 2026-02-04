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
        session_id: Optional[str] = None,
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
            session_id: Optional Hapi session ID to resume
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
                session_id=session_id,
                sticky_notes=sticky_notes,
                tags=tags,
                created_by=created_by,
                max_retries=max_retries,
                status=PulseStatus.PENDING,
            )
            session.add(pulse)
            await session.commit()
            await session.refresh(pulse)
            return pulse.id  # type: ignore[return-value]

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

            pulse.status = PulseStatus.PROCESSING  # type: ignore[assignment]
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
                pulse.status = PulseStatus.COMPLETED  # type: ignore[assignment]
                pulse.executed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                pulse.execution_duration_ms = execution_duration_ms  # type: ignore[assignment]
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

            pulse.status = PulseStatus.FAILED  # type: ignore[assignment]
            pulse.error_message = error_message  # type: ignore[assignment]
            pulse.executed_at = datetime.now(timezone.utc)  # type: ignore[assignment]

            # Retry logic with exponential backoff
            new_pulse_id = None
            if should_retry and pulse.retry_count < pulse.max_retries:
                # Schedule retry with exponential backoff: 2^retry_count minutes
                retry_delay_minutes = 2**pulse.retry_count  # type: ignore[operator]
                retry_at = datetime.now(timezone.utc) + timedelta(minutes=retry_delay_minutes)

                retry_pulse = Pulse(
                    scheduled_at=retry_at,
                    prompt=pulse.prompt,
                    priority=pulse.priority,
                    session_id=pulse.session_id,
                    sticky_notes=pulse.sticky_notes,
                    tags=pulse.tags,
                    created_by=f"retry_{pulse.created_by}",
                    max_retries=pulse.max_retries,
                    retry_count=pulse.retry_count + 1,
                    status=PulseStatus.PENDING,
                )

                session.add(retry_pulse)
                await session.flush()
                new_pulse_id = retry_pulse.id  # type: ignore[assignment]

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

            pulse.status = PulseStatus.CANCELLED  # type: ignore[assignment]
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

            pulse.scheduled_at = new_scheduled_at  # type: ignore[assignment]
            await session.commit()
            return True

    async def get_pulses_by_status(
        self, status: Optional[str] = None, limit: int = 20
    ) -> List[Pulse]:
        """
        Get pulses filtered by status.

        Args:
            status: Filter by status. Valid values:
                - "pending", "failed", "completed", "cancelled", "processing" - filter by that status
                - "overdue" - return pending pulses where scheduled_at < now
                - None or "all" - return all recent pulses
            limit: Maximum number of pulses to return

        Returns:
            List of Pulse objects ordered by scheduled_at DESC
        """
        async with self.SessionLocal() as session:
            now = datetime.now(timezone.utc)

            if status == "overdue":
                # Pending pulses that are past their scheduled time
                stmt = (
                    select(Pulse)
                    .where(and_(Pulse.status == PulseStatus.PENDING, Pulse.scheduled_at < now))
                    .order_by(Pulse.scheduled_at.desc())
                    .limit(limit)
                )
            elif status in ("pending", "failed", "completed", "cancelled", "processing"):
                # Filter by specific status
                pulse_status = PulseStatus(status)
                stmt = (
                    select(Pulse)
                    .where(Pulse.status == pulse_status)
                    .order_by(Pulse.scheduled_at.desc())
                    .limit(limit)
                )
            else:
                # Return all recent pulses (None or "all")
                stmt = select(Pulse).order_by(Pulse.scheduled_at.desc()).limit(limit)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_pulse_stats(self) -> dict:
        """
        Get queue statistics.

        Returns:
            Dictionary with:
                - pending: Count of pending pulses
                - overdue: Count of pending pulses where scheduled_at < now
                - failed: Count of failed pulses
                - completed_today: Count of pulses completed in last 24 hours
                - processing: Count of currently processing pulses
        """
        from sqlalchemy import func as sqlfunc

        async with self.SessionLocal() as session:
            now = datetime.now(timezone.utc)
            twenty_four_hours_ago = now - timedelta(hours=24)

            # Count pending pulses
            pending_stmt = (
                select(sqlfunc.count())
                .select_from(Pulse)
                .where(Pulse.status == PulseStatus.PENDING)
            )
            pending_result = await session.execute(pending_stmt)
            pending_count = pending_result.scalar() or 0

            # Count overdue pulses (pending and past scheduled time)
            overdue_stmt = (
                select(sqlfunc.count())
                .select_from(Pulse)
                .where(and_(Pulse.status == PulseStatus.PENDING, Pulse.scheduled_at < now))
            )
            overdue_result = await session.execute(overdue_stmt)
            overdue_count = overdue_result.scalar() or 0

            # Count failed pulses
            failed_stmt = (
                select(sqlfunc.count()).select_from(Pulse).where(Pulse.status == PulseStatus.FAILED)
            )
            failed_result = await session.execute(failed_stmt)
            failed_count = failed_result.scalar() or 0

            # Count completed in last 24 hours
            completed_stmt = (
                select(sqlfunc.count())
                .select_from(Pulse)
                .where(
                    and_(
                        Pulse.status == PulseStatus.COMPLETED,
                        Pulse.executed_at >= twenty_four_hours_ago,
                    )
                )
            )
            completed_result = await session.execute(completed_stmt)
            completed_today_count = completed_result.scalar() or 0

            # Count processing pulses
            processing_stmt = (
                select(sqlfunc.count())
                .select_from(Pulse)
                .where(Pulse.status == PulseStatus.PROCESSING)
            )
            processing_result = await session.execute(processing_stmt)
            processing_count = processing_result.scalar() or 0

            return {
                "pending": pending_count,
                "overdue": overdue_count,
                "failed": failed_count,
                "completed_today": completed_today_count,
                "processing": processing_count,
            }

    async def get_execution_stats(self) -> dict:
        """
        Get execution statistics for the last 7 days.

        Returns:
            Dictionary with:
                - total_completed: Total completed pulses in last 7 days
                - total_failed: Total failed pulses in last 7 days
                - success_rate: Percentage of successful executions (0.0-100.0)
                - avg_duration_ms: Average execution duration in milliseconds
                - recent_failures: Last 5 failed pulses with id, prompt (truncated), error_message
        """
        from sqlalchemy import func as sqlfunc

        async with self.SessionLocal() as session:
            now = datetime.now(timezone.utc)
            seven_days_ago = now - timedelta(days=7)

            # Count completed in last 7 days
            completed_stmt = (
                select(sqlfunc.count())
                .select_from(Pulse)
                .where(
                    and_(
                        Pulse.status == PulseStatus.COMPLETED,
                        Pulse.executed_at >= seven_days_ago,
                    )
                )
            )
            completed_result = await session.execute(completed_stmt)
            total_completed = completed_result.scalar() or 0

            # Count failed in last 7 days
            failed_stmt = (
                select(sqlfunc.count())
                .select_from(Pulse)
                .where(
                    and_(
                        Pulse.status == PulseStatus.FAILED,
                        Pulse.executed_at >= seven_days_ago,
                    )
                )
            )
            failed_result = await session.execute(failed_stmt)
            total_failed = failed_result.scalar() or 0

            # Calculate success rate
            total_executions = total_completed + total_failed
            success_rate = (
                (total_completed / total_executions * 100.0) if total_executions > 0 else 0.0
            )

            # Calculate average duration for completed pulses
            avg_duration_stmt = (
                select(sqlfunc.avg(Pulse.execution_duration_ms))
                .select_from(Pulse)
                .where(
                    and_(
                        Pulse.status == PulseStatus.COMPLETED,
                        Pulse.executed_at >= seven_days_ago,
                        Pulse.execution_duration_ms.isnot(None),
                    )
                )
            )
            avg_duration_result = await session.execute(avg_duration_stmt)
            avg_duration_ms = avg_duration_result.scalar() or 0.0

            # Get recent failures (last 5)
            recent_failures_stmt = (
                select(Pulse)
                .where(Pulse.status == PulseStatus.FAILED)
                .order_by(Pulse.executed_at.desc())
                .limit(5)
            )
            recent_failures_result = await session.execute(recent_failures_stmt)
            recent_failure_pulses = list(recent_failures_result.scalars().all())

            recent_failures = [
                {
                    "id": p.id,
                    "prompt": (
                        str(p.prompt)[:100] + "..." if len(str(p.prompt)) > 100 else str(p.prompt)
                    ),
                    "error_message": p.error_message,
                }
                for p in recent_failure_pulses
            ]

            return {
                "total_completed": total_completed,
                "total_failed": total_failed,
                "success_rate": round(success_rate, 2),
                "avg_duration_ms": round(float(avg_duration_ms), 2),
                "recent_failures": recent_failures,
            }

    async def close(self) -> None:
        """
        Close the database connection.

        Should be called when shutting down to clean up resources.
        """
        await self.engine.dispose()
