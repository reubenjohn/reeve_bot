# Reeve Bot - Implementation Context

## Project Overview

**Reeve Bot** is the Engine component of Project Reeve - a proactive AI "Chief of Staff" system. This repository contains the **Pulse Queue System**, which enables Reeve to schedule its own wake-ups and respond to external events.

### Key Concept: The Pulse Queue

A **Pulse** is a scheduled wake-up event for Reeve. When a pulse fires, it launches a Hapi/Claude Code session with a specific prompt and context. This allows Reeve to be proactive rather than purely reactive.

## Current Status

### ✅ Phase 1: Foundation - COMPLETED (Commit: ece5e41)

**What's been implemented:**

1. **Project Structure**
   - `src/reeve/pulse/` - Core pulse queue logic
   - `src/reeve/mcp/` - MCP servers (to be implemented)
   - `src/reeve/api/` - HTTP REST API (to be implemented)
   - `src/reeve/integrations/` - External event listeners (to be implemented)
   - `src/reeve/utils/` - Shared utilities (to be implemented)

2. **Database Schema**
   - SQLite database at `~/.reeve/pulse_queue.db`
   - `pulses` table with 15 columns
   - 5 indexes including composite indexes for query optimization
   - Alembic migration: `07ce7ae63b4a`

3. **Models & Enums**
   - `src/reeve/pulse/enums.py`: `PulsePriority` and `PulseStatus` enums
   - `src/reeve/pulse/models.py`: `Pulse` SQLAlchemy model
   - All fields properly typed with comments

4. **Alembic Setup**
   - Configured for auto-discovery of models
   - Environment variable support: `PULSE_DB_URL`
   - Default path: `~/.reeve/pulse_queue.db`

### 🔄 Next: Phase 2 - Queue Management

**Goal**: Implement the `PulseQueue` class with async business logic.

**Files to create:**
- `src/reeve/pulse/queue.py` - Core queue management class
- `src/reeve/utils/config.py` - Configuration loading
- `tests/test_pulse_queue.py` - Comprehensive unit tests

**Key requirements:**
- Async SQLAlchemy operations
- Methods: `schedule_pulse()`, `get_due_pulses()`, `mark_processing()`, `mark_completed()`, `mark_failed()`, `cancel_pulse()`, `reschedule_pulse()`
- Retry logic with exponential backoff (2^retry_count minutes)
- In-memory database for testing

## Architecture Decisions

### Database
- **SQLite** with async support (`aiosqlite`)
- Single-user system - no need for Postgres
- Alembic for migrations

### Async Design
- All queue operations are async
- Daemon will run asyncio event loop
- Concurrent MCP server + HTTP API + scheduler

### Priority System
```python
CRITICAL  # 🚨 User messages, emergencies
HIGH      # 🔔 External events, user-facing tasks
NORMAL    # ⏰ Regular maintenance, scheduled checks
LOW       # 📋 Background tasks
DEFERRED  # 🕐 Intentionally postponed
```

### Status Lifecycle
```
PENDING → PROCESSING → COMPLETED (success)
                     → FAILED (with retry)
                     → CANCELLED (manual)
```

## Key Design Patterns

### 1. Composite Indexes
The main query pattern is "get pending pulses due before now, ordered by priority":
```sql
WHERE status = 'pending' AND scheduled_at <= now()
ORDER BY priority, scheduled_at
```

Index: `idx_pulse_execution` on `(status, scheduled_at, priority)`

### 2. Retry Logic
On failure, create a new pulse with:
- `retry_count` incremented
- `scheduled_at` = now + 2^retry_count minutes
- Same prompt, priority, and context
- Stop after `max_retries` attempts

### 3. String Enums
All enums inherit from `str` for:
- JSON serialization (API responses, MCP tools)
- Human-readable database values
- Type safety in Python code

## Configuration

### Environment Variables (`.env`)
```bash
REEVE_DESK_PATH=~/my_reeve              # User's context repository
PULSE_DB_URL=sqlite+aiosqlite:///~/.reeve/pulse_queue.db
PULSE_API_PORT=8765
PULSE_API_TOKEN=your_secret_token
HAPI_COMMAND=hapi
```

### Database URLs
- **Alembic (sync)**: `sqlite:///~/.reeve/pulse_queue.db`
- **Runtime (async)**: `sqlite+aiosqlite:///~/.reeve/pulse_queue.db`

## Testing Strategy

### Unit Tests
- Use in-memory database: `sqlite+aiosqlite:///:memory:`
- Test all CRUD operations
- Test priority ordering
- Test retry logic
- Test edge cases

### Validation Tests
- `tests/test_phase1_validation.py` - Phase 1 foundation tests
- `tests/test_pulse_queue.py` - Phase 2 queue operations (to be created)

## Code Style

### Type Hints
All functions must have complete type hints:
```python
async def schedule_pulse(
    self,
    scheduled_at: datetime,
    prompt: str,
    priority: PulsePriority = PulsePriority.NORMAL,
) -> int:
```

### Docstrings
All public methods must have docstrings with:
- Description
- Args (with types and descriptions)
- Returns (with type and description)
- Example usage (when helpful)

### Formatting
- **Black**: line-length = 100
- **isort**: profile = "black"
- **mypy**: type checking enabled

## Important Implementation Notes

### For Phase 2 (Queue Management)

1. **Session Management**
   ```python
   self.engine = create_async_engine(db_url, echo=False)
   self.SessionLocal = async_sessionmaker(
       self.engine,
       class_=AsyncSession,
       expire_on_commit=False
   )
   ```

2. **Priority Ordering**
   SQLAlchemy will order enums by their definition order (CRITICAL first).
   The enum definition order matches desired priority (highest to lowest).

3. **Timezone Awareness**
   Always use `datetime.now(timezone.utc)` - never naive datetimes.

4. **Retry Backoff**
   ```python
   retry_delay_minutes = 2 ** pulse.retry_count
   # 0 retries = 1 min, 1 retry = 2 min, 2 retries = 4 min, 3 retries = 8 min
   ```

5. **Transaction Handling**
   Use `async with self.SessionLocal() as session:` for automatic cleanup.
   Call `await session.commit()` explicitly.

6. **Error Handling**
   Be defensive - check if pulse exists before updating.
   Return `False` or `None` on failure, log errors appropriately.

## File References

### Documentation
- `docs/00_PROJECT_STRUCTURE.md` - Directory layout
- `docs/01_PULSE_QUEUE_DESIGN.md` - Database schema, queue logic
- `docs/02_MCP_INTEGRATION.md` - MCP server specs (Phase 3)
- `docs/03_DAEMON_AND_API.md` - Daemon and API design (Phases 4-6)
- `docs/04_DEPLOYMENT.md` - Production deployment (Phase 8)
- `docs/IMPLEMENTATION_ROADMAP.md` - Full implementation plan

### Implemented Files
- `src/reeve/pulse/enums.py` - Priority and status enums
- `src/reeve/pulse/models.py` - Pulse SQLAlchemy model
- `alembic/versions/07ce7ae63b4a_create_pulses_table.py` - Initial migration
- `tests/test_phase1_validation.py` - Phase 1 validation

### To Be Implemented (Phase 2)
- `src/reeve/pulse/queue.py` - PulseQueue class
- `src/reeve/utils/config.py` - Configuration management
- `tests/test_pulse_queue.py` - Queue unit tests

## Quick Start Commands

```bash
# Install dependencies
uv sync

# Run Alembic migrations
uv run alembic upgrade head

# Run tests
uv run pytest tests/ -v

# Format code
uv run black src/
uv run isort src/

# Check types
uv run mypy src/
```

## Common Queries

### Check migration status
```bash
uv run alembic current
```

### Inspect database
```bash
sqlite3 ~/.reeve/pulse_queue.db
.schema pulses
SELECT * FROM pulses;
```

### Test model creation
```python
from reeve.pulse.models import Pulse
from reeve.pulse.enums import PulsePriority, PulseStatus
from datetime import datetime, timezone

pulse = Pulse(
    scheduled_at=datetime.now(timezone.utc),
    prompt="Test pulse",
    priority=PulsePriority.NORMAL,
    status=PulseStatus.PENDING
)
```

## Next Session Prompt

When starting Phase 2, use this prompt:

```
I'm ready to implement Phase 2 (Queue Management) for the Pulse Queue system.

Please implement:
1. PulseQueue class in src/reeve/pulse/queue.py with async SQLAlchemy
2. All queue methods (schedule, get_due_pulses, mark_*, cancel, reschedule)
3. Retry logic with exponential backoff
4. Configuration management in src/reeve/utils/config.py
5. Comprehensive unit tests in tests/test_pulse_queue.py

Refer to docs/01_PULSE_QUEUE_DESIGN.md for the complete PulseQueue implementation specification.
```

## Design Principles

1. **Keep it simple**: Don't over-engineer. SQLite is sufficient.
2. **Async by default**: All I/O operations are async.
3. **Type-safe**: Use type hints and enums everywhere.
4. **Testable**: Use dependency injection, in-memory databases for tests.
5. **Documented**: Code should be self-explanatory with good docstrings.
6. **Fail gracefully**: Check preconditions, return None/False on errors.
7. **Idempotent**: Operations should be safe to retry.

## Git Workflow

```bash
# Phase commits should be atomic
git add -A
git commit -m "Implement Phase N: [Title]

[Detailed description of what was implemented]

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

## Dependencies Version Lock

Current versions (from `uv.lock`):
- SQLAlchemy: 2.0.45
- aiosqlite: 0.22.1
- Alembic: 1.18.1
- FastAPI: 0.128.0
- Pydantic: 2.12.5
- MCP: 1.25.0

---

**Last Updated**: 2026-01-19 (after Phase 1 completion)
**Current Commit**: ece5e41
**Current Migration**: 07ce7ae63b4a
