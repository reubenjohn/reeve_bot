# Pulse Queue Design

## Overview

The Pulse Queue is the core scheduling mechanism that enables Reeve's proactive behavior. It manages when and why Reeve should "wake up" to perform tasks, check for updates, or process information.

## Core Concepts

### 1. Pulse

A **Pulse** represents a single scheduled wake-up event for Reeve. Each pulse contains:

- **When** to wake up (`scheduled_at`)
- **Why** to wake up (`prompt` - the context/task)
- **How urgent** it is (`priority`)
- **What context** to resume (`session_id`, `sticky_notes`)
- **Current state** (`status`)

### 2. Priority System

Pulses have different priority levels to manage Reeve's attention:

```python
class PulsePriority(str, Enum):
    """
    Priority levels for pulses, determining execution order when multiple
    pulses are due at the same time.

    Higher priority pulses are processed first. Priority also affects
    interrupt behavior and user notification urgency.
    """

    CRITICAL = "critical"    # 🚨 Emergency: User messages, system failures
                             # - Interrupts deep work
                             # - Bypasses DND settings
                             # - Example: "Wife texted: Emergency"

    HIGH = "high"           # 🔔 Important: External events, user-facing tasks
                             # - Scheduled alarms the user set
                             # - External triggers (Telegram, Email)
                             # - Example: "Check flight status before departure"

    NORMAL = "normal"       # ⏰ Standard: Regular maintenance, scheduled checks
                             # - Periodic pulses (hourly check)
                             # - Calendar event reminders
                             # - Example: "Daily 9 AM: Review calendar"

    LOW = "low"             # 📋 Background: Non-urgent maintenance
                             # - Cleanup tasks
                             # - Background research
                             # - Example: "Weekly: Archive old notes"

    DEFERRED = "deferred"   # 🕐 Postponed: Intentionally delayed
                             # - User explicitly snoozed a task
                             # - Rescheduled due to conflicts
                             # - Example: "Moved from Monday to Friday"
```

**Design Rationale**:
- **String Enum**: JSON-serializable, human-readable in DB
- **Explicit semantics**: Each level has clear use cases
- **Emoji convention**: Visual scanning in logs/UI
- **5 levels**: Enough granularity without decision paralysis

### 3. Pulse Status Lifecycle

```python
class PulseStatus(str, Enum):
    """
    Status of a pulse in its lifecycle.

    State transitions:
    PENDING -> PROCESSING -> COMPLETED (success)
                          -> FAILED (error, will retry)
                          -> CANCELLED (user/system cancelled)
    """

    PENDING = "pending"         # Waiting to be executed
    PROCESSING = "processing"   # Currently executing
    COMPLETED = "completed"     # Successfully executed
    FAILED = "failed"           # Execution failed (see error_message)
    CANCELLED = "cancelled"     # Manually cancelled by user/system
```

**Design Rationale**:
- **Simple states**: Easy to reason about, no complex state machine
- **Processing state**: Prevents duplicate execution (idempotency)
- **Failed vs Cancelled**: Failed = retry possible, Cancelled = intentional stop

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'lineColor': '#888'}}}%%
flowchart TD
    create(["schedule_pulse()"]) --> pending["PENDING"]
    pending --> |"Daemon detects due pulse"| processing
    processing["PROCESSING"]
    processing --> |"Executor runs"| result{Result?}

    result --> |Success| completed["COMPLETED"]
    result --> |Failure| failed["FAILED"]

    failed --> retry{"retry_count < max?"}
    retry --> |Yes| new_pending["New PENDING<br/>(exponential backoff)"]
    retry --> |No| remains["Remains FAILED"]

    cancel(["cancel_pulse()"]) -.-> |"At any time"| cancelled["CANCELLED"]
    pending -.-> cancelled

    %% Styles
    classDef status fill:#4a90a4,stroke:#2e6b7a,color:#fff
    classDef success fill:#6b9b76,stroke:#4a7a54,color:#fff
    classDef failure fill:#c4955a,stroke:#a67940,color:#fff
    classDef action fill:#888,stroke:#666,color:#fff

    class pending,processing status
    class completed,new_pending success
    class failed,remains,cancelled failure
    class create,cancel,result,retry action
```

## Database Schema

### Pulse Model

```python
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum as SQLEnum, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List

Base = declarative_base()

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
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When this pulse should execute (UTC timestamp)"
    )

    # Execution Context
    prompt = Column(
        Text,
        nullable=False,
        comment="The instruction/context for Reeve when this pulse fires. "
                "This becomes the initial message in the Hapi session."
    )

    priority = Column(
        SQLEnum(PulsePriority),
        nullable=False,
        default=PulsePriority.NORMAL,
        index=True,
        comment="Execution priority (determines order when multiple pulses are due)"
    )

    # Session Continuity (Optional)
    session_id = Column(
        String(500),
        nullable=True,
        comment="Optional Hapi session ID or URL to resume existing context. "
                "If None, a new session is created."
    )

    sticky_notes = Column(
        JSON,
        nullable=True,
        comment="Optional list of reminder strings to inject into the prompt. "
                "Example: ['Check if user replied to ski trip', 'Follow up on PR review']"
    )

    # Execution State
    status = Column(
        SQLEnum(PulseStatus),
        nullable=False,
        default=PulseStatus.PENDING,
        index=True,
        comment="Current execution status of this pulse"
    )

    # Execution Results (populated after execution)
    executed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this pulse actually executed (may differ from scheduled_at)"
    )

    execution_duration_ms = Column(
        Integer,
        nullable=True,
        comment="How long the Hapi session took to complete (milliseconds)"
    )

    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if status=FAILED. Used for debugging and retry logic."
    )

    # Retry Logic
    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times this pulse has been retried after failure"
    )

    max_retries = Column(
        Integer,
        nullable=False,
        default=3,
        comment="Maximum retry attempts before giving up"
    )

    # Metadata
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When this pulse was created (for auditing)"
    )

    created_by = Column(
        String(100),
        nullable=False,
        default="system",
        comment="Who/what created this pulse. Examples: 'reeve', 'telegram_listener', 'user_cli'"
    )

    tags = Column(
        JSON,
        nullable=True,
        comment="Optional tags for categorization/filtering. "
                "Example: ['hourly_check', 'calendar_sync', 'snowboarding']"
    )

    # Database Indexes (in addition to individual column indexes)
    # Composite index for the main query pattern
    __table_args__ = (
        # Most common query: "Get all pending/processing pulses due before now, ordered by priority"
        Index('idx_pulse_execution', 'status', 'scheduled_at', 'priority'),
        # For listing upcoming pulses: "What's on Reeve's schedule?"
        Index('idx_pulse_upcoming', 'scheduled_at', 'status'),
    )

    def __repr__(self):
        return (f"<Pulse(id={self.id}, scheduled_at={self.scheduled_at}, "
                f"priority={self.priority.value}, status={self.status.value})>")
```

### Alembic Migration Strategy

**Initial Migration** (`versions/001_create_pulses_table.py`):
```python
"""Create pulses table

Revision ID: 001
Revises:
Create Date: 2026-01-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'pulses',
        # ... (full schema as defined above)
    )

def downgrade():
    op.drop_table('pulses')
```

**Why Alembic?**
- Version-controlled schema changes
- Safe migrations in production
- Rollback capability
- Explicit upgrade path

## Queue Management Logic

### PulseQueue Class

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_, or_
from datetime import datetime, timezone
from typing import List, Optional
import asyncio

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
                - "postgresql+asyncpg://user:pass@localhost/reeve" (async Postgres)
        """
        self.engine = create_async_engine(db_url, echo=False)
        self.SessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def schedule_pulse(
        self,
        scheduled_at: datetime,
        prompt: str,
        priority: PulsePriority = PulsePriority.NORMAL,
        session_id: Optional[str] = None,
        sticky_notes: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        created_by: str = "system",
        max_retries: int = 3
    ) -> int:
        """
        Schedule a new pulse.

        Args:
            scheduled_at: When to execute (UTC timezone-aware datetime)
            prompt: The instruction/context for Reeve
            priority: Urgency level (default: NORMAL)
            session_id: Optional Hapi session to resume
            sticky_notes: Optional reminder strings to inject
            tags: Optional categorization tags
            created_by: Who created this pulse (for auditing)
            max_retries: Max retry attempts on failure

        Returns:
            The pulse ID (integer)

        Example:
            pulse_id = await queue.schedule_pulse(
                scheduled_at=datetime(2026, 1, 20, 9, 0, tzinfo=timezone.utc),
                prompt="Daily morning briefing: Review calendar and tasks",
                priority=PulsePriority.NORMAL,
                tags=["daily", "morning_routine"]
            )
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
                status=PulseStatus.PENDING
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
        async with self.SessionLocal() as session:
            now = datetime.now(timezone.utc)

            stmt = (
                select(Pulse)
                .where(
                    and_(
                        Pulse.scheduled_at <= now,
                        Pulse.status == PulseStatus.PENDING
                    )
                )
                .order_by(
                    # Sort by priority enum value order (CRITICAL first)
                    Pulse.priority,
                    # Then by time (oldest first)
                    Pulse.scheduled_at
                )
                .limit(limit)
            )

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_upcoming_pulses(
        self,
        limit: int = 20,
        include_statuses: Optional[List[PulseStatus]] = None
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

    async def mark_completed(
        self,
        pulse_id: int,
        execution_duration_ms: int
    ) -> None:
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
        self,
        pulse_id: int,
        error_message: str,
        should_retry: bool = True
    ) -> Optional[int]:
        """
        Mark a pulse as failed.

        If retry is enabled and max_retries not exceeded, schedules a new
        retry pulse.

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

            # Retry logic
            new_pulse_id = None
            if should_retry and pulse.retry_count < pulse.max_retries:
                # Schedule retry with exponential backoff: 2^retry_count minutes
                retry_delay_minutes = 2 ** pulse.retry_count
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
                    status=PulseStatus.PENDING
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

            if not pulse or pulse.status not in [PulseStatus.PENDING]:
                return False

            pulse.status = PulseStatus.CANCELLED
            await session.commit()
            return True

    async def reschedule_pulse(
        self,
        pulse_id: int,
        new_scheduled_at: datetime
    ) -> bool:
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
```

## Design Decisions & Rationale

### 1. Why Async SQLAlchemy?

**Decision**: Use `AsyncSession` and `async_sessionmaker`

**Rationale**:
- Daemon runs an asyncio event loop (concurrent MCP server + HTTP API + scheduler)
- Blocking DB calls would stall the entire event loop
- Async allows thousands of concurrent operations
- Future-proof for high-throughput scenarios

### 2. Why String Enums?

**Decision**: `class PulsePriority(str, Enum)`

**Rationale**:
- JSON-serializable (for API responses, MCP tool returns)
- Human-readable in database (SQLite browser shows "high" not 2)
- Type-safe in Python code
- Better error messages ("got 'urgent', expected 'high'")

### 3. Why Composite Indexes?

**Decision**: `Index('idx_pulse_execution', 'status', 'scheduled_at', 'priority')`

**Rationale**:
- The main query (`get_due_pulses`) filters by status + scheduled_at, sorts by priority
- Composite index covers entire query (no table scan)
- SQLite can use leftmost prefix for other queries
- Tradeoff: Slightly slower writes (index maintenance), but reads are 100x faster

### 4. Why Retry Logic in DB?

**Decision**: Store `retry_count` and `max_retries` in Pulse model

**Rationale**:
- Self-contained: Each pulse knows its own retry policy
- Exponential backoff: 1min → 2min → 4min → 8min
- Failure forensics: Can query "which pulses failed repeatedly?"
- Future: Could add per-priority retry policies

### 5. Why Separate `created_by` Field?

**Decision**: Track who/what created each pulse

**Rationale**:
- Debugging: "Why did this pulse fire?"
- Analytics: "How many pulses come from Telegram vs. Reeve itself?"
- Audit trail: Security/compliance
- Future: Rate limiting per source

## Execution Flow

### Daemon Main Loop

```
┌─────────────────────────────────────────┐
│  While True (every 1 second):           │
│                                         │
│  1. Get due pulses from queue           │
│  2. For each pulse (up to 10):          │
│     a. Mark as PROCESSING               │
│     b. Launch Hapi session (async)      │
│     c. Wait for completion              │
│     d. Mark as COMPLETED/FAILED         │
│  3. Sleep 1 second                      │
└─────────────────────────────────────────┘
```

**Why 1 second polling?**
- Sub-second precision (vs. cron's 1-minute minimum)
- Low CPU overhead (DB query is cheap with indexes)
- Can batch multiple due pulses in one iteration
- Future: Could use DB triggers + notify/listen for zero-latency

### Parallel Execution

**Option A: Sequential** (Initial Implementation)
- Process one pulse at a time
- Simple, predictable
- Good for debugging

**Option B: Parallel** (Future Optimization)
- Process up to N pulses concurrently
- Faster overall throughput
- Risk: Resource contention (CPU, Hapi sessions)

**Recommendation**: Start with Sequential, add Parallel after observing real-world load.

## Next Steps

See **[mcp-integration.md](mcp-integration.md)** for how Reeve interacts with this queue via MCP tools.
