# Reeve Bot - Implementation Context

## End Vision: The Proactive AI Chief of Staff

**Project Reeve** is building a proactive AI assistant that operates on a **"Push" paradigm** rather than waiting passively for prompts. Reeve functions as a high-fidelity proxy between the user and the world—filtering noise (email, group chats), coordinating logistics, and anticipating needs based on time and context. It acts as a **Gatekeeper** (protecting attention), **Proxy** (handling communication), and **Coach** (adapting to the user's energy and priorities).

The system uses a **Dual-Repo Architecture**: the **Engine** (`reeve_bot/`) contains immutable logic, while the **Desk** (`my_reeve/`) contains the user's personal context (Goals, Responsibilities, Preferences). Reeve "wakes up" on a **Pulse**—either periodically (hourly heartbeat) or aperiodically (self-scheduled alarms). When a pulse fires, it launches a Hapi/Claude Code session with access to the Desk, allowing it to reason about the user's life and take action. External events (Telegram messages, emails, calendar changes) can also trigger pulses via an HTTP API.

The **Pulse Queue** (what we're building now) is the foundational scheduling mechanism enabling this proactivity. It manages when and why Reeve should wake up, handles retries on failure, and provides priority-based execution. Once complete, the system will include MCP servers (for Reeve to manage its own schedule), a daemon (running the pulse loop), integrations (Telegram, Email, Calendar), and an HTTP API (for external triggers). See [README.md](README.md) for the full philosophy and use cases.

---

## Project Overview

**Reeve Bot** (`reeve_bot/`) is the Engine component of Project Reeve. This repository contains the **Pulse Queue System**, which enables Reeve to schedule its own wake-ups and respond to external events.

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
   - `src/reeve/utils/` - Shared utilities

2. **Database Schema**
   - SQLite database at `~/.reeve/pulse_queue.db`
   - `pulses` table with 15 columns
   - 5 indexes including composite indexes for query optimization
   - Alembic migration: `07ce7ae63b4a`

3. **Models & Enums**
   - `src/reeve/pulse/enums.py`: `PulsePriority` and `PulseStatus` enums
   - `src/reeve/pulse/models.py`: `Pulse` SQLAlchemy model with `TZDateTime` for timezone handling
   - All fields properly typed with comments

4. **Alembic Setup**
   - Configured for auto-discovery of models
   - Environment variable support: `PULSE_DB_URL`
   - Default path: `~/.reeve/pulse_queue.db`

### ✅ Phase 2: Queue Management - COMPLETED (Commit: 52eac4c)

**What's been implemented:**

1. **PulseQueue Class** (`src/reeve/pulse/queue.py`)
   - Async SQLAlchemy session management
   - `schedule_pulse()` - Create new pulses
   - `get_due_pulses()` - Query pending pulses with priority ordering (using CASE statement)
   - `get_upcoming_pulses()` - List future pulses
   - `get_pulse()` - Retrieve pulse by ID
   - `mark_processing()` - Transition to processing state
   - `mark_completed()` - Mark successful completion
   - `mark_failed()` - Handle failures with exponential backoff retry (2^retry_count minutes)
   - `cancel_pulse()` - Cancel pending pulses
   - `reschedule_pulse()` - Change scheduled time
   - `initialize()` - Initialize database schema
   - `close()` - Clean up resources

2. **Configuration Management** (`src/reeve/utils/config.py`)
   - `ReeveConfig` class with environment variable support
   - Path expansion for `~` and `$VAR` in paths
   - Database URL handling (async and sync modes)
   - Singleton pattern with `get_config()` and `reload_config()`

3. **Enhanced Database Models** (`src/reeve/pulse/models.py`)
   - `TZDateTime` custom type for proper timezone handling with SQLite
   - Updated to SQLAlchemy 2.0 style (`orm.declarative_base`)
   - All datetime fields preserve timezone information

4. **Comprehensive Test Suite** (`tests/test_pulse_queue.py`)
   - 29 unit tests covering all queue operations
   - Priority ordering tests with custom CASE ordering
   - Retry logic with exponential backoff tests
   - Concurrent operations tests
   - Edge case coverage
   - In-memory SQLite for fast, isolated testing

5. **Validation Tests** (`tests/test_phase2_validation.py`)
   - Integration test from roadmap
   - End-to-end workflow validation

**Test Results**: 33/33 tests PASSED
- 3 Phase 1 validation tests
- 1 Phase 2 integration test
- 29 Phase 2 unit tests

### ✅ Phase 3: MCP Integration - COMPLETED (Commit: b4ff8ed)

**What's been implemented:**

1. **Pulse Queue MCP Server** (`src/reeve/mcp/pulse_server.py`)
   - Built with FastMCP (mcp.server.fastmcp)
   - Four MCP tools:
     - `schedule_pulse()` - Schedule new pulses with flexible time parsing
     - `list_upcoming_pulses()` - View scheduled pulses with visual formatting
     - `cancel_pulse()` - Cancel pending pulses
     - `reschedule_pulse()` - Change pulse timing
   - Helper functions:
     - `_parse_time_string()` - Parse ISO 8601, relative times ("in 2 hours"), keywords ("now")
     - `_priority_emoji()` - Visual priority indicators (🚨🔔⏰📋🕐)
     - `_status_emoji()` - Visual status indicators (⏳⚙️✅❌🚫)
   - Comprehensive parameter validation with Pydantic
   - User-friendly error messages
   - Clean output formatting with emojis and relative times

2. **Telegram Notifier MCP Server** (`src/reeve/mcp/notification_server.py`)
   - Built with FastMCP with Context integration
   - Single MCP tool:
     - `send_notification()` - Send push notifications via Telegram
   - Auto-detects session ID and generates "View in Claude Code" button
   - Supports MarkdownV2, HTML, and plain text formatting
   - Priority levels: silent (no sound), normal (with sound), critical (with sound)
   - Configurable Hapi base URL via `HAPI_BASE_URL` environment variable
   - Error handling for Telegram API failures

3. **MCP Configuration**
   - Example config: `mcp_config.json.example`
   - Setup guide: `docs/MCP_SETUP.md`
   - Instructions for obtaining Telegram bot token and chat ID
   - Troubleshooting guide for common issues

4. **Time Parsing**
   - ISO 8601 format: "2026-01-20T09:00:00Z"
   - Relative time: "in 2 hours", "in 30 minutes", "in 5 days"
   - Keywords: "now" (immediate)
   - Case-insensitive parsing
   - UTC timezone-aware datetime handling

5. **Test Suite** (split into 3 files for better organization)
   - `tests/test_pulse_server_helpers.py` - 11 tests for time parsing and emoji helpers
   - `tests/test_pulse_server_tools.py` - 3 tests for pulse queue MCP tools and integration
   - `tests/test_notification_server.py` - 4 tests for Telegram notifier MCP tools
   - All tests use async patterns
   - Mock-based testing for external dependencies

**Test Results**: 51/51 tests PASSED
- 33 Phase 1-2 tests (unchanged)
- 18 Phase 3 MCP tests (reorganized into 3 files)

### ✅ Phase 4: Pulse Executor - COMPLETED (Commit: 5d7b2ab)

**Goal**: Execute pulses by launching Hapi sessions.

**What's been implemented:**

1. **PulseExecutor Class** (`src/reeve/pulse/executor.py`)
   - Async subprocess execution for Hapi sessions
   - Key features:
     - `execute()` - Launch Hapi with prompt, session link, and working directory
     - `build_prompt()` - Build full prompt with sticky notes appended (not prepended)
     - Timeout handling with configurable defaults (1 hour default)
     - Working directory validation and path expansion
     - UTF-8 error handling for subprocess output
     - Graceful timeout with process cleanup
   - Configuration:
     - `hapi_command` - Path to Hapi executable
     - `desk_path` - Default working directory (user's Desk)
     - `timeout_seconds` - Maximum execution time
   - Return format:
     - `stdout` - Standard output from Hapi
     - `stderr` - Standard error from Hapi
     - `return_code` - Process exit code
     - `timed_out` - Whether execution timed out
   - Error handling:
     - RuntimeError on non-zero exit codes
     - RuntimeError on timeout
     - RuntimeError on command not found
     - RuntimeError on invalid working directory

2. **Prompt Building with Sticky Notes**
   - Sticky notes are appended to the base prompt (not prepended)
   - Clear formatting with 📌 emoji header
   - Each note on separate line with bullet point
   - Blank line separator between base prompt and sticky notes
   - Example format:
     ```
     Daily morning briefing

     📌 Reminders:
       - Check if user replied to ski trip
       - Follow up on PR review
     ```

3. **Comprehensive Test Suite** (`tests/test_pulse_executor.py`)
   - 18 unit tests covering:
     - Prompt building (4 tests: no notes, with notes, empty list, single note)
     - Successful execution (4 tests: basic, with session link, with stderr, default desk path)
     - Error handling (5 tests: non-zero exit, command not found, missing working dir, timeout, UTF-8 errors)
     - Configuration (2 tests: path expansion, custom timeout)
     - Integration scenarios (3 tests: full flow, timeout override, working dir override)
   - All tests use async patterns with mocked subprocess
   - Tests verify command construction and parameter passing

**Test Results**: 69/69 tests PASSED
- 51 Phase 1-3 tests (unchanged)
- 18 Phase 4 executor tests (new)

### 🔄 Next: Phase 5 - Daemon

**Goal**: Build the main daemon process that orchestrates pulse execution.

**Files to create:**
- `src/reeve/pulse/daemon.py` - PulseDaemon class
- `src/reeve/utils/logging.py` - Logging configuration

**Key requirements:**
- Scheduler loop (polls every 1 second)
- Concurrent execution of pulses
- Integration with PulseExecutor
- Graceful shutdown handling

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

### For Phase 3 (MCP Integration)

1. **MCP Tool Structure**
   - Use `Annotated[Type, Field(...)]` for all parameters
   - Provide comprehensive docstrings (visible to Claude)
   - Return structured data (not raw model objects)

2. **Time Parsing**
   - Implement flexible time parsing ("in 5 minutes", "tomorrow at 9am", "2026-01-20 15:00")
   - Always convert to UTC timezone-aware datetime
   - Handle relative and absolute time expressions

3. **Error Handling**
   - Catch exceptions and return user-friendly error messages
   - Log errors for debugging
   - Never expose internal stack traces to MCP calls

## File References

### Documentation
- `docs/00_PROJECT_STRUCTURE.md` - Directory layout
- `docs/01_PULSE_QUEUE_DESIGN.md` - Database schema, queue logic
- `docs/02_MCP_INTEGRATION.md` - MCP server specs (Phase 3)
- `docs/03_DAEMON_AND_API.md` - Daemon and API design (Phases 4-6)
- `docs/04_DEPLOYMENT.md` - Production deployment (Phase 8)
- `docs/IMPLEMENTATION_ROADMAP.md` - Full implementation plan

### Implemented Files (Phases 1-4)
- `src/reeve/pulse/enums.py` - Priority and status enums
- `src/reeve/pulse/models.py` - Pulse SQLAlchemy model with TZDateTime
- `src/reeve/pulse/queue.py` - PulseQueue class with async operations
- `src/reeve/pulse/executor.py` - PulseExecutor class for Hapi execution
- `src/reeve/utils/config.py` - Configuration management
- `src/reeve/mcp/pulse_server.py` - Pulse Queue MCP server (FastMCP)
- `src/reeve/mcp/notification_server.py` - Telegram Notifier MCP server (FastMCP)
- `alembic/versions/07ce7ae63b4a_create_pulses_table.py` - Initial migration
- `tests/test_phase1_validation.py` - Phase 1 validation (3 tests)
- `tests/test_phase2_validation.py` - Phase 2 integration test
- `tests/test_pulse_queue.py` - Comprehensive queue unit tests (29 tests)
- `tests/test_pulse_server_helpers.py` - Pulse server helper tests (11 tests)
- `tests/test_pulse_server_tools.py` - Pulse server MCP tool tests (3 tests)
- `tests/test_notification_server.py` - Telegram notifier tests (4 tests)
- `tests/test_pulse_executor.py` - Pulse executor tests (18 tests)
- `mcp_config.json.example` - Example MCP configuration for Claude Code
- `docs/MCP_SETUP.md` - MCP server setup and troubleshooting guide
- `pytest.ini` - Pytest configuration for async tests

### To Be Implemented (Phase 5+)
- `src/reeve/pulse/daemon.py` - Main daemon process
- `src/reeve/utils/logging.py` - Logging configuration
- `src/reeve/api/server.py` - FastAPI HTTP server
- `src/reeve/integrations/telegram.py` - Telegram listener

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

When starting Phase 5, use this prompt:

```
I'm ready to implement Phase 5 (Pulse Daemon) for the Pulse Queue system.

Please implement:
1. PulseDaemon class (src/reeve/pulse/daemon.py) that:
   - Runs a scheduler loop that polls every 1 second
   - Executes due pulses using PulseExecutor
   - Handles concurrent pulse execution
   - Implements graceful shutdown (SIGTERM/SIGINT)
   - Integrates prompt building with sticky notes
2. Logging configuration (src/reeve/utils/logging.py)
3. Unit tests for the daemon
4. Integration tests for end-to-end pulse execution

Refer to docs/03_DAEMON_AND_API.md for the complete daemon specifications.
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

**Last Updated**: 2026-01-19 (after Phase 4 completion)
**Current Commit**: 5d7b2ab
**Current Migration**: 07ce7ae63b4a
**Test Status**: 69/69 tests PASSED
