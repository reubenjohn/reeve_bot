# Reeve Bot - Implementation Context

## End Vision: The Proactive AI Chief of Staff

**Project Reeve** is building a proactive AI assistant that operates on a **"Push" paradigm** rather than waiting passively for prompts. Reeve functions as a high-fidelity proxy between the user and the world—filtering noise (email, group chats), coordinating logistics, and anticipating needs based on time and context. It acts as a **Gatekeeper** (protecting attention), **Proxy** (handling communication), and **Coach** (adapting to the user's energy and priorities).

The system uses a **Dual-Repo Architecture**: the **Engine** (`reeve-bot/`) contains immutable logic, while the **Desk** (`my_reeve/`) contains the user's personal context (Goals, Responsibilities, Preferences). Reeve "wakes up" on a **Pulse**—either periodically (hourly heartbeat) or aperiodically (self-scheduled alarms). When a pulse fires, it launches a Hapi/Claude Code session with access to the Desk, allowing it to reason about the user's life and take action. External events (Telegram messages, emails, calendar changes) can also trigger pulses via an HTTP API.

The **Pulse Queue** (what we're building now) is the foundational scheduling mechanism enabling this proactivity. It manages when and why Reeve should wake up, handles retries on failure, and provides priority-based execution. Once complete, the system will include MCP servers (for Reeve to manage its own schedule), a daemon (running the pulse loop), integrations (Telegram, Email, Calendar), and an HTTP API (for external triggers). See [README.md](README.md) for the full philosophy and use cases.

---

## Project Overview

**Reeve Bot** (`reeve-bot/`) is the Engine component of Project Reeve. This repository contains the **Pulse Queue System**, which enables Reeve to schedule its own wake-ups and respond to external events.

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

### ✅ Phase 5: Pulse Daemon - COMPLETED (Commit: b9b9714)

**Goal**: Build the main daemon process that orchestrates pulse execution.

**What's been implemented:**

1. **PulseDaemon Class** (`src/reeve/pulse/daemon.py` - 273 lines)
   - Scheduler loop polling every 1 second
   - Concurrent pulse execution (up to 10 per iteration)
   - Signal handling (SIGTERM, SIGINT) for graceful shutdown
   - 30-second grace period for in-flight pulses
   - Automatic retry on failures with exponential backoff
   - Error recovery with 5-second backoff on database errors
   - Key methods:
     - `_execute_pulse()` - Execute single pulse, track duration, handle errors
     - `_scheduler_loop()` - Poll for due pulses, spawn concurrent tasks
     - `_handle_shutdown()` - Graceful shutdown with timeout
     - `start()` - Main entry point (blocks until shutdown)
   - State tracking:
     - `self.running` - Controls scheduler loop
     - `self.executing_pulses: set[asyncio.Task]` - In-flight tasks
     - `self.shutdown_event: asyncio.Event()` - Shutdown signal

2. **Logging Configuration** (`src/reeve/utils/logging.py` - 72 lines)
   - `setup_logging()` function with rotating file handler
   - RotatingFileHandler (10MB max, 5 backups)
   - Structured formatting: `"%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"`
   - Console + file output (configurable)
   - Auto-creates log directory if missing

3. **Entry Point** (`src/reeve/pulse/__main__.py` - 59 lines)
   - Run as module: `python -m reeve.pulse`
   - Configuration loading via `get_config()`
   - Logging initialization
   - Startup info logging (database, desk, hapi paths)
   - Graceful KeyboardInterrupt handling

4. **Test Suite** (23 comprehensive tests)
   - `tests/test_pulse_daemon.py` - 21 unit tests covering:
     - Pulse Execution (6 tests): success, sticky notes, session ID, failures, retries, duration
     - Scheduler Loop (8 tests): polling, task spawning, priority, concurrency, error handling
     - Signal Handling (4 tests): shutdown, in-flight wait, timeout, resource cleanup
     - Integration (3 tests): full lifecycle, concurrent execution, error recovery
   - `tests/test_phase5_validation.py` - 2 integration tests:
     - End-to-end daemon lifecycle validation
     - Pulse execution flow verification

**Test Results**: 94/94 tests PASSED
- 71 Phase 1-4 tests (unchanged)
- 21 Phase 5 daemon unit tests (new)
- 2 Phase 5 validation tests (new)

### ✅ Phase 6: HTTP API - COMPLETED (Commit: 70b9bec)

**Goal**: Add FastAPI server to allow external systems to trigger pulses.

**What's been implemented:**

1. **FastAPI Server** (`src/reeve/api/server.py` - 295 lines)
   - Four REST endpoints:
     - `POST /api/pulse/schedule` - Create new pulse (with Bearer auth)
     - `GET /api/pulse/upcoming` - List upcoming pulses (with Bearer auth)
     - `GET /api/health` - Health check (no auth required)
     - `GET /api/status` - Daemon status and config (with Bearer auth)
   - Bearer token authentication with `Authorization: Bearer <token>` header
   - Flexible time parsing via `parse_time_string()` utility
   - Comprehensive Pydantic models for request/response validation
   - Error handling with proper HTTP status codes

2. **Integration with Daemon** (`src/reeve/pulse/__main__.py` updates)
   - API server runs concurrently with scheduler loop
   - Shared PulseQueue instance for database access
   - Graceful shutdown handling for both scheduler and API server
   - Configurable API port via `PULSE_API_PORT` environment variable

3. **Time Parsing Utility** (`src/reeve/utils/time_parser.py` - 79 lines)
   - Shared time parsing logic extracted from MCP server
   - Supports ISO 8601, relative times ("in X hours/minutes/days"), and "now" keyword
   - Used by both MCP server and API server
   - Comprehensive error messages for invalid time formats

4. **Demo Script** (`demos/phase6_api_demo.py` - 418 lines)
   - 8 comprehensive demo functions:
     1. Health check endpoint (no auth)
     2. Bearer token authentication test
     3. Schedule immediate pulse ("now")
     4. Schedule relative pulse ("in 5 minutes")
     5. Schedule ISO 8601 pulse with sticky notes
     6. List upcoming pulses
     7. Daemon status
     8. Cleanup demo pulses
   - Uses httpx for async HTTP requests
   - Clean output formatting following phase4_executor_demo.py pattern
   - Interactive flow with daemon running check

5. **Test Suite** (`tests/test_api_server.py` - 88 lines)
   - 8 comprehensive tests covering:
     - Authentication (3 tests): missing auth, invalid token, valid token
     - Schedule pulse (2 tests): success, invalid time format
     - List upcoming (1 test): success
     - Health check (1 test): no auth required
     - Status endpoint (1 test): success

6. **Configuration Updates**
   - Added `httpx>=0.27.0` to dependencies in `pyproject.toml`
   - Refactored pulse_server.py to use shared `parse_time_string()` utility
   - Removed duplicate time parsing code from MCP server

**Test Results**: 154/154 tests PASSED
- 94 Phase 1-5 tests (unchanged)
- 8 Phase 6 API server tests (new)
- 52 Phase 6 validation tests (time parser, integration, etc.)

### ✅ Phase 7: Telegram Integration - COMPLETED (Commit: TBD)

**Goal**: Build Telegram listener to convert incoming messages to pulses.

**What's been implemented:**

1. **TelegramListener Class** (`src/reeve/integrations/telegram/listener.py` - 595 lines)
   - Async polling-based integration with Telegram Bot API
   - Key features:
     - Long polling (100s timeout) for efficient resource usage
     - Offset persistence to prevent duplicate message processing
     - Chat ID filtering (only processes authorized user)
     - Exponential backoff error handling (up to 5 minutes)
     - Graceful shutdown with SIGTERM/SIGINT handlers
   - Configuration via environment variables:
     - `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather
     - `TELEGRAM_CHAT_ID` - Authorized user's chat ID
     - `PULSE_API_URL` - API server URL (default: http://127.0.0.1:8765)
     - `PULSE_API_TOKEN` - Bearer token for API authentication
   - Message flow:
     - Polls getUpdates endpoint with long polling
     - Filters messages by chat ID
     - Builds prompt: "Telegram message from {user}: {text}"
     - Triggers pulse via HTTP API with priority=critical
     - Tags: ["telegram", "user_message"]
     - Saves offset after successful batch processing
   - Error recovery:
     - Exponential backoff: 2^error_count seconds (max 300s)
     - Fatal error detection (invalid token, max retries)
     - Automatic shutdown on fatal errors

2. **Entry Point** (`src/reeve/integrations/telegram/__main__.py`)
   - Run as module: `python -m reeve.integrations.telegram`
   - Configuration loading and validation
   - Logging initialization
   - Graceful KeyboardInterrupt handling

3. **Demo Script** (`demos/phase7_telegram_demo.py` - 475 lines)
   - 7 comprehensive demo functions:
     1. Start mock Telegram API server (getMe, getUpdates)
     2. Start mock Pulse API server (schedule endpoint)
     3. Configure listener with mock endpoints
     4. Simulate incoming message from Alice
     5. Show listener polling flow
     6. Verify pulse triggered with correct metadata
     7. Verify offset persistence to disk
   - Mock servers using aiohttp.web
   - Clean output formatting with status indicators
   - Full integration flow demonstration

4. **Test Suite** (`tests/test_telegram_listener.py` - 35 tests)
   - Comprehensive unit tests covering:
     - Offset Management (6 tests): load, save, persistence, errors
     - Telegram Polling (7 tests): API interactions, long polling, errors
     - Message Processing (7 tests): filtering, formatting, chat ID
     - API Integration (5 tests): pulse triggering, authentication
     - Error Handling (5 tests): exponential backoff, fatal errors
     - Signal Handling (3 tests): graceful shutdown, cleanup
     - Integration (2 tests): end-to-end workflows
   - All tests use async patterns with mocked HTTP clients
   - Mock-based testing for Telegram and Pulse APIs

5. **Validation Tests** (`tests/test_phase7_validation.py` - 2 tests)
   - End-to-end integration test with real components
   - Validates full message flow: Telegram → Listener → API → Queue
   - Verifies pulse created with correct metadata
   - Tests offset persistence

**Test Results**: 191/191 tests PASSED
- 154 Phase 1-6 tests (unchanged)
- 35 Phase 7 Telegram listener unit tests (new)
- 2 Phase 7 validation tests (new)

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

### Implemented Files (Phases 1-7)
- `src/reeve/pulse/enums.py` - Priority and status enums
- `src/reeve/pulse/models.py` - Pulse SQLAlchemy model with TZDateTime
- `src/reeve/pulse/queue.py` - PulseQueue class with async operations
- `src/reeve/pulse/executor.py` - PulseExecutor class for Hapi execution
- `src/reeve/pulse/daemon.py` - PulseDaemon class with scheduler loop (273 lines)
- `src/reeve/pulse/__main__.py` - Entry point for daemon module (updated for API)
- `src/reeve/api/server.py` - FastAPI HTTP server for external triggers (295 lines)
- `src/reeve/integrations/telegram/listener.py` - TelegramListener class (595 lines)
- `src/reeve/integrations/telegram/__main__.py` - Entry point for Telegram listener
- `src/reeve/utils/config.py` - Configuration management
- `src/reeve/utils/logging.py` - Logging configuration with rotation (72 lines)
- `src/reeve/utils/time_parser.py` - Shared time parsing utility (79 lines)
- `src/reeve/mcp/pulse_server.py` - Pulse Queue MCP server (FastMCP, refactored)
- `src/reeve/mcp/notification_server.py` - Telegram Notifier MCP server (FastMCP)
- `alembic/versions/07ce7ae63b4a_create_pulses_table.py` - Initial migration
- `tests/test_phase1_validation.py` - Phase 1 validation (3 tests)
- `tests/test_phase2_validation.py` - Phase 2 integration test
- `tests/test_pulse_queue.py` - Comprehensive queue unit tests (29 tests)
- `tests/test_pulse_server_helpers.py` - Pulse server helper tests (11 tests)
- `tests/test_pulse_server_tools.py` - Pulse server MCP tool tests (3 tests)
- `tests/test_notification_server.py` - Telegram notifier tests (4 tests)
- `tests/test_pulse_executor.py` - Pulse executor tests (18 tests)
- `tests/test_pulse_daemon.py` - Pulse daemon unit tests (21 tests)
- `tests/test_phase5_validation.py` - Phase 5 validation tests (2 tests)
- `tests/test_api_server.py` - API server unit tests (8 tests)
- `tests/test_telegram_listener.py` - Telegram listener unit tests (35 tests)
- `tests/test_phase7_validation.py` - Phase 7 validation tests (2 tests)
- `mcp_config.json.example` - Example MCP configuration for Claude Code
- `docs/MCP_SETUP.md` - MCP server setup and troubleshooting guide
- `pytest.ini` - Pytest configuration for async tests
- `demos/phase1_database_demo.py` - Phase 1 demo: Database schema
- `demos/phase2_queue_demo.py` - Phase 2 demo: Queue operations
- `demos/phase3_mcp_demo.py` - Phase 3 demo: MCP integration
- `demos/phase4_executor_demo.py` - Phase 4 demo: Pulse executor
- `demos/phase5_daemon_demo.py` - Phase 5 demo: Daemon orchestration
- `demos/phase6_api_demo.py` - Phase 6 demo: HTTP API server (442 lines)
- `demos/phase7_telegram_demo.py` - Phase 7 demo: Telegram integration (475 lines)
- `demos/README.md` - Demo usage guide and self-testing protocol

### To Be Implemented (Phase 8+)
- Production deployment configuration
- Systemd service files
- Email integration (optional)

## Quick Start Commands

```bash
# Install dependencies
uv sync

# Run Alembic migrations
uv run alembic upgrade head

# Run tests
uv run pytest tests/ -v

# Run daemon (Phase 5+)
uv run python -m reeve.pulse

# Run daemon with custom log level and API token
export PULSE_API_TOKEN=test-token-123
LOG_LEVEL=DEBUG uv run python -m reeve.pulse

# Run demos (interactive real-world examples)
uv run python demos/phase1_database_demo.py
uv run python demos/phase2_queue_demo.py
uv run python demos/phase3_mcp_demo.py
uv run python demos/phase4_executor_demo.py --mock
uv run python demos/phase5_daemon_demo.py --mock
export PULSE_API_TOKEN=test-token-123 && uv run python demos/phase6_api_demo.py
uv run python demos/phase7_telegram_demo.py

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

When starting Phase 8, use this prompt:

```
I'm ready to implement Phase 8 (Production Deployment) for the Pulse Queue system.

Please implement:
1. Systemd service files for:
   - Pulse daemon (reeve-daemon.service)
   - Telegram listener (reeve-telegram.service)
2. Installation script with:
   - Virtual environment setup
   - Dependency installation
   - Service registration
   - Log directory creation
3. Configuration validation script
4. Update documentation with deployment guides
5. Create production best practices guide

Refer to docs/IMPLEMENTATION_ROADMAP.md for Phase 8 specifications.
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

## Contributing

For external contributors and maintainers, see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development environment setup
- Pull request process
- Issue reporting guidelines
- Contributor recognition

## Dependencies Version Lock

Current versions (from `uv.lock`):
- SQLAlchemy: 2.0.45
- aiosqlite: 0.22.1
- Alembic: 1.18.1
- FastAPI: 0.128.0
- Pydantic: 2.12.5
- httpx: 0.27.0 (added in Phase 6)
- MCP: 1.25.0

---

**Last Updated**: 2026-01-23 (Phase 7 completed)
**Current Commit**: fcb3c5b (Phase 7: Telegram Integration)
**Current Migration**: 07ce7ae63b4a
**Test Status**: 191/191 tests PASSED
