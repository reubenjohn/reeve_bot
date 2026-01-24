# Pulse Queue System - Implementation Roadmap

## Overview

This document provides a step-by-step implementation guide for building the Pulse Queue system from scratch. Follow this roadmap in order, as later phases depend on earlier foundations.

**Estimated Total Effort**: 3-4 days for full implementation + testing

---

## Phase 1: Foundation ✅ COMPLETED

**Goal**: Set up project structure, dependencies, and database schema.

**Status**: ✅ Completed on 2026-01-19 (Commit: ece5e41)

### Tasks

1. **Project Structure** ✅
   - Create directory structure as per [00_PROJECT_STRUCTURE.md](00_PROJECT_STRUCTURE.md)
   - Initialize `src/reeve/` package with `__init__.py` files

2. **Dependencies** ✅
   - Update `pyproject.toml` with required packages:
     ```toml
     [project]
     name = "reeve-bot"
     version = "0.1.0"
     requires-python = ">=3.11"
     dependencies = [
         "sqlalchemy>=2.0",
         "aiosqlite>=0.19.0",
         "alembic>=1.13.0",
         "fastapi>=0.109.0",
         "uvicorn>=0.27.0",
         "pydantic>=2.5.0",
         "requests>=2.32.0",
         "mcp>=0.9.0",  # MCP SDK
         "python-dotenv>=1.0.0",
     ]
     ```
   - Run: `uv sync`

3. **Enums** ✅ (`src/reeve/pulse/enums.py`)
   - Implement `PulsePriority(str, Enum)` with 5 levels
   - Implement `PulseStatus(str, Enum)` with 5 states
   - See [01_PULSE_QUEUE_DESIGN.md](01_PULSE_QUEUE_DESIGN.md) for full definitions

4. **Database Models** ✅ (`src/reeve/pulse/models.py`)
   - Implement `Pulse` SQLAlchemy model
   - Define all columns as specified in design doc
   - Add composite indexes
   - Test model creation:
     ```python
     from reeve.pulse.models import Base, Pulse
     from sqlalchemy import create_engine
     engine = create_engine("sqlite:///test.db")
     Base.metadata.create_all(engine)
     ```

5. **Alembic Setup** ✅
   - Initialize: `uv run alembic init alembic`
   - Configure `alembic.ini` with `sqlalchemy.url`
   - Configure `alembic/env.py` with model auto-discovery
   - Create initial migration:
     ```bash
     uv run alembic revision --autogenerate -m "Create pulses table"
     uv run alembic upgrade head
     ```
   - Verify: `sqlite3 ~/.reeve/pulse_queue.db .schema`

**Deliverables**:
- ✅ Clean project structure
- ✅ Working database with `pulses` table (Migration: 07ce7ae63b4a)
- ✅ Type-safe enums
- ✅ Alembic migrations working
- ✅ Validation tests passing

**Validation**:
```python
# Test script
from reeve.pulse.models import Pulse
from reeve.pulse.enums import PulsePriority, PulseStatus
from datetime import datetime, timezone

pulse = Pulse(
    scheduled_at=datetime.now(timezone.utc),
    prompt="Test pulse",
    priority=PulsePriority.NORMAL,
    status=PulseStatus.PENDING
)
print(f"Created: {pulse}")
```

**Demo**: Database Schema
```bash
# Run the demo script
uv run python demos/phase1_database_demo.py

# Expected output:
# ✓ Database initialized at ~/.reeve/pulse_queue.db
# ✓ Created pulse with ID: 1
# ✓ Verified pulse in database:
#   - Scheduled at: 2026-01-19 10:30:00+00:00
#   - Priority: NORMAL
#   - Status: PENDING
# ✓ Phase 1 Demo Complete!
```

---

## Phase 2: Queue Management ✅ COMPLETED

**Goal**: Implement core business logic for queue operations.

**Status**: ✅ Completed on 2026-01-19 (Commit: 52eac4c)

### Tasks

1. **PulseQueue Class** (`src/reeve/pulse/queue.py`) ✅
   - Implemented async SQLAlchemy session management
   - Implemented all methods:
     - `schedule_pulse()` - Create new pulse
     - `get_due_pulses()` - Query pending pulses with priority ordering
     - `get_upcoming_pulses()` - List future pulses
     - `get_pulse()` - Retrieve pulse by ID
     - `mark_processing()` - Transition to processing
     - `mark_completed()` - Mark success
     - `mark_failed()` - Handle failures + retry logic with exponential backoff
     - `cancel_pulse()` - Cancel pending
     - `reschedule_pulse()` - Change time
     - `initialize()` - Initialize database schema
     - `close()` - Clean up resources
   - Priority ordering using SQLAlchemy CASE statement

2. **Unit Tests** (`tests/test_pulse_queue.py`) ✅
   - Test database: `sqlite+aiosqlite:///:memory:`
   - 29 comprehensive unit tests covering:
     - All CRUD operations
     - Priority ordering (CRITICAL → HIGH → NORMAL → LOW → DEFERRED)
     - Time-based FIFO within same priority
     - Retry logic with exponential backoff (2^retry_count minutes)
     - Concurrent operations
     - Edge cases (nonexistent pulses, invalid states, etc.)
     - Timezone awareness

3. **Configuration** (`src/reeve/utils/config.py`) ✅
   - Implemented `ReeveConfig` class with environment variable support
   - Path expansion for `~` and `$VAR`
   - Database URL handling (async and sync modes)
   - Singleton pattern with `get_config()` and `reload_config()`

4. **Enhanced Database Models** (`src/reeve/pulse/models.py`) ✅
   - Added `TZDateTime` custom type for proper timezone handling with SQLite
   - Updated to SQLAlchemy 2.0 style (`orm.declarative_base`)
   - All datetime fields preserve timezone information

5. **Validation Tests** (`tests/test_phase2_validation.py`) ✅
   - Integration test from roadmap validation example
   - End-to-end workflow validation

**Deliverables**:
- ✅ Fully functional `PulseQueue` class
- ✅ 100% test coverage for queue operations (33/33 tests passed)
- ✅ Configuration management
- ✅ Timezone-aware datetime handling
- ✅ Code formatted with black and isort

**Validation**:
```bash
# All tests passing
uv run pytest tests/ -v
# Result: 33 passed (3 Phase 1 + 1 Phase 2 integration + 29 Phase 2 unit tests)
```

**Demo**: Queue Operations
```bash
# Run the demo script
uv run python demos/phase2_queue_demo.py

# Expected output:
# ✓ Initialized PulseQueue
# ✓ Scheduled pulse #1: "High priority task" (due in 5 seconds, priority: HIGH)
# ✓ Scheduled pulse #2: "Normal maintenance" (due in 10 seconds, priority: NORMAL)
# ✓ Scheduled pulse #3: "Low priority cleanup" (due in 15 seconds, priority: LOW)
#
# Upcoming pulses (3):
# 🔔 #1 - HIGH - in 5s - "High priority task"
# ⏰ #2 - NORMAL - in 10s - "Normal maintenance"
# 📋 #3 - LOW - in 15s - "Low priority cleanup"
#
# ✓ Marked pulse #1 as PROCESSING
# ✓ Marked pulse #1 as COMPLETED
#
# ✓ Simulating failure for pulse #2...
# ✓ Marked pulse #2 as FAILED (retry_count=1, will retry in 2 minutes)
#
# ✓ Cancelled pulse #3
#
# Final status:
# - Pulse #1: COMPLETED ✅
# - Pulse #2: PENDING (scheduled for retry in ~2 minutes) 🔄
# - Pulse #3: CANCELLED ❌
#
# ✓ Phase 2 Demo Complete!
```

---

## Phase 3: MCP Servers ✅ COMPLETED

**Goal**: Expose queue functionality to Reeve via MCP tools.

**Status**: ✅ Completed on 2026-01-19

### Tasks

1. **Pulse Queue MCP Server** (`src/reeve/mcp/pulse_server.py`) ✅
   - Implemented all tools using FastMCP:
     - `schedule_pulse()` - Schedule pulses with flexible time parsing
     - `list_upcoming_pulses()` - View scheduled pulses with visual formatting
     - `cancel_pulse()` - Cancel pending pulses
     - `reschedule_pulse()` - Change pulse timing
   - Type-safe with `Annotated[Type, Field(...)]`
   - Comprehensive docstrings with usage examples
   - Helper functions:
     - `_parse_time_string()` - ISO 8601, relative times ("in 2 hours"), keywords ("now")
     - `_priority_emoji()` and `_status_emoji()` - Visual indicators
   - Graceful error handling with user-friendly messages

2. **Telegram Notifier MCP Server** (`src/reeve/mcp/notification_server.py`) ✅
   - Implemented tools using FastMCP:
     - `send_notification()` - Push notifications via Telegram with auto-generated session links
   - Auto-detects session ID via FastMCP Context and generates "View in Claude Code" button
   - Integrated with Telegram Bot API
   - Supports MarkdownV2, HTML, and plain text formatting
   - Priority levels: silent, normal, critical (controls notification sound)
   - Configurable Hapi base URL via `HAPI_BASE_URL` environment variable
   - Error handling for API failures

3. **MCP Configuration** ✅
   - Created `mcp_config.json.example` template
   - Documentation: `docs/MCP_SETUP.md` with setup and troubleshooting
   - Both servers configured with `uv run` commands
   - Server startup tested successfully

4. **Testing** ✅
   - Created MCP server test suite (split into 3 files, 18 tests total):
     - `tests/test_pulse_server_helpers.py` - 11 tests (time parsing, emoji helpers)
     - `tests/test_pulse_server_tools.py` - 3 tests (MCP tools, integration)
     - `tests/test_notification_server.py` - 4 tests (Telegram notifier)
   - All tests pass (51/51 total across all phases)

**Deliverables**:
- ✅ Two working MCP servers built with FastMCP
- ✅ Type-safe tool definitions with Pydantic validation
- ✅ Comprehensive documentation for Claude and users
- ✅ 18 comprehensive tests split across 3 files with mocking and integration coverage
- ✅ Example configuration and setup guide

**Validation**:
```bash
# Run tests
uv run pytest tests/test_pulse_server_helpers.py tests/test_pulse_server_tools.py tests/test_notification_server.py -v
# Result: 18/18 tests PASSED

# Test server startup
uv run python -m reeve.mcp.pulse_server
# Server starts and waits for stdio input ✓

uv run python -m reeve.mcp.notification_server
# Server starts (requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars) ✓

# Manual testing with Claude Code
# Configure MCP servers in ~/.config/claude-code/mcp_config.json
# Then in Claude Code session, tools are automatically available
```

**Demo**: MCP Tools Integration

**Step 1: Configure MCP servers** (one-time setup)
```bash
# Copy example config
cp mcp_config.json.example ~/.config/claude-code/mcp_config.json

# Edit to add Telegram credentials (optional for telegram-notifier)
# TELEGRAM_BOT_TOKEN: Get from @BotFather on Telegram
# TELEGRAM_CHAT_ID: Your Telegram user ID
```

**Step 2a: Demo via Interactive Script**
```bash
# Run the demo script (doesn't require MCP configuration)
uv run python demos/phase3_mcp_demo.py

# Expected output:
# ✓ Testing Pulse Queue MCP Tools
# ✓ Scheduled pulse #1: "Morning briefing" (in 1 hour, priority: HIGH)
# ✓ Scheduled pulse #2: "Afternoon check-in" (in 4 hours, priority: NORMAL)
# ✓ Listed 2 upcoming pulses
# ✓ Rescheduled pulse #1 to 30 minutes from now
# ✓ Cancelled pulse #2
#
# ✓ Testing Telegram Notifier MCP Tool
# ✓ Sent test notification: "Phase 3 demo completed! 🎉"
#   (Check your Telegram for the message)
#
# ✓ Phase 3 Demo Complete!
```

**Step 2b: Demo via Claude Code** (after MCP configuration)
```
In a Claude Code session, use the MCP tools directly:

1. Schedule a pulse:
   schedule_pulse(
     scheduled_at="in 30 minutes",
     prompt="Test notification from MCP",
     priority="high"
   )

2. List upcoming pulses:
   list_upcoming_pulses(limit=10)

3. Send a notification:
   send_notification(
     message="Testing Telegram integration!",
     priority="normal"
   )

4. Cancel a pulse:
   cancel_pulse(pulse_id=1)
```

---

## Phase 4: Pulse Executor ✅ COMPLETED

**Goal**: Execute pulses by launching Hapi sessions.

**Status**: ✅ Completed on 2026-01-19

### Tasks

1. **PulseExecutor Class** (`src/reeve/pulse/executor.py`) ✅
   - Implemented `execute()` method with full async support
   - Launches Hapi subprocess with correct working directory
   - Handles sticky notes (appended to prompt, not prepended)
   - Captures stdout/stderr with UTF-8 error handling
   - Reports success/failure with detailed error messages
   - Includes timeout handling with configurable defaults
   - See [03_DAEMON_AND_API.md](03_DAEMON_AND_API.md)

2. **Testing** ✅
   - 18 comprehensive unit tests with mocked Hapi command
   - Tests prompt building with and without sticky notes
   - Tests error handling (Hapi crash, timeout, command not found, invalid paths)
   - Tests configuration (path expansion, custom timeout)
   - Integration-style tests for full execution flow

**Deliverables**:
- ✅ Working executor that can launch Hapi with full error handling
- ✅ 18 comprehensive tests with mocked Hapi (all passing)

**Validation**:
```python
# Test script
import asyncio
from reeve.pulse.executor import PulseExecutor

async def test():
    executor = PulseExecutor("hapi", "~/my_reeve")

    result = await executor.execute(
        prompt="Echo hello world and exit",
        working_dir="~/my_reeve"
    )

    print(f"Return code: {result['return_code']}")
    print(f"Output: {result['stdout']}")

asyncio.run(test())
```

**Demo**: Pulse Executor with Real Hapi

**Note**: This demo requires Hapi to be installed and configured. If Hapi is not available, the demo will use a mock executor.

```bash
# Run the demo script
uv run python demos/phase4_executor_demo.py

# Expected output (with real Hapi):
# ✓ Testing PulseExecutor
# ✓ Building prompt with sticky notes...
#
# Prompt to send:
# ─────────────────────────────────────
# Tell me a programming joke and then exit
#
# 📌 Reminders:
#   - Keep it short
#   - Make it funny
# ─────────────────────────────────────
#
# ✓ Launching Hapi session...
# ✓ Execution completed successfully!
#
# Output:
# ─────────────────────────────────────
# Why do programmers prefer dark mode?
# Because light attracts bugs! 🐛
# ─────────────────────────────────────
#
# Execution time: 2.3 seconds
# ✓ Phase 4 Demo Complete!
```

**Alternative Demo** (if Hapi not available):
```bash
# The demo script will automatically detect if Hapi is available
# If not, it will demonstrate the executor with a mock command
uv run python demos/phase4_executor_demo.py --mock

# Expected output (mock mode):
# ℹ Hapi not found, using mock executor
# ✓ Mock execution successful
# ✓ Prompt building tested
# ✓ Timeout handling tested
# ✓ Error handling tested
# ✓ Phase 4 Demo Complete (mock mode)!
```

---

## Phase 5: Daemon ✅ COMPLETED

**Goal**: Build the main daemon process that ties everything together.

**Status**: ✅ Completed on 2026-01-22 (Commit: b9b9714)

### Tasks

1. **Daemon Class** (`src/reeve/pulse/daemon.py`) ✅
   - Implemented `PulseDaemon` class (273 lines)
   - Implemented `_scheduler_loop()` - polls every 1 second
   - Implemented `_execute_pulse()` - async pulse execution with error handling
   - Handles prompt building with sticky notes via PulseExecutor
   - Graceful shutdown (SIGTERM/SIGINT) with 30-second grace period
   - See [03_DAEMON_AND_API.md](03_DAEMON_AND_API.md)

2. **Logging** (`src/reeve/utils/logging.py`) ✅
   - Implemented `setup_logging()` function (72 lines)
   - RotatingFileHandler with 10MB max, 5 backups
   - Structured logging format
   - Console + file output (configurable)

3. **Entry Point** (`src/reeve/pulse/__main__.py`) ✅
   - Implemented module entry point (59 lines)
   - Configuration loading and logging setup
   - Graceful KeyboardInterrupt handling

4. **Testing** ✅
   - 21 comprehensive unit tests (tests/test_pulse_daemon.py)
   - 2 integration/validation tests (tests/test_phase5_validation.py)
   - All tests pass: 94/94

**Deliverables**:
- ✅ Functional daemon process
- ✅ Pulse execution working end-to-end
- ✅ Proper logging with file rotation
- ✅ Comprehensive test suite

**Validation**:
```bash
# Terminal 1: Start daemon
uv run python -m reeve.pulse

# Terminal 2: Schedule pulse via MCP (in Claude Code)
schedule_pulse(
    scheduled_at="in 10 seconds",
    prompt="Test pulse execution",
    priority="high"
)

# Terminal 1: Watch logs for execution
# Should see: "Executing pulse X: Test pulse execution..."
# Should see: "Pulse X completed successfully in Yms"
```

**Demo**: End-to-End Pulse Execution

**Step 1: Start the daemon**
```bash
# Terminal 1: Start daemon in foreground
uv run python -m reeve.pulse

# Expected output:
# 2026-01-19 10:30:00 | INFO | Starting Pulse Daemon...
# 2026-01-19 10:30:00 | INFO | Database: ~/.reeve/pulse_queue.db
# 2026-01-19 10:30:00 | INFO | Scheduler loop started (polling every 1s)
# 2026-01-19 10:30:00 | INFO | Ready to execute pulses
```

**Step 2: Schedule pulses via MCP** (in Claude Code or via demo script)
```bash
# Terminal 2: Run the demo script
uv run python demos/phase5_daemon_demo.py

# The script will:
# 1. Schedule 3 pulses with different priorities and timing
# 2. Watch the daemon execute them in priority order
# 3. Verify retry logic on simulated failures
# 4. Test graceful shutdown
```

**Expected daemon output**:
```
2026-01-19 10:30:05 | INFO | Found 3 due pulses
2026-01-19 10:30:05 | INFO | Executing pulse #1 (CRITICAL): "Emergency system check"
2026-01-19 10:30:05 | INFO | Launching Hapi session...
2026-01-19 10:30:08 | INFO | Pulse #1 completed successfully (3.2s)
2026-01-19 10:30:10 | INFO | Executing pulse #2 (HIGH): "Morning briefing"
2026-01-19 10:30:10 | INFO | Launching Hapi session...
2026-01-19 10:30:13 | INFO | Pulse #2 completed successfully (2.8s)
2026-01-19 10:30:15 | INFO | Executing pulse #3 (NORMAL): "Check calendar"
2026-01-19 10:30:15 | INFO | Launching Hapi session...
2026-01-19 10:30:18 | INFO | Pulse #3 completed successfully (2.1s)
```

**Step 3: Test retry logic**
```bash
# The demo script will schedule a pulse that intentionally fails
# Expected daemon output:
2026-01-19 10:31:00 | INFO | Executing pulse #4 (HIGH): "Flaky task"
2026-01-19 10:31:00 | INFO | Launching Hapi session...
2026-01-19 10:31:02 | ERROR | Pulse #4 failed: Hapi returned error code 1
2026-01-19 10:31:02 | INFO | Scheduling retry #1 in 2 minutes
2026-01-19 10:33:02 | INFO | Executing pulse #5 (HIGH): "Flaky task (retry 1)"
2026-01-19 10:33:02 | INFO | Launching Hapi session...
2026-01-19 10:33:05 | INFO | Pulse #5 completed successfully (2.5s)
```

**Step 4: Test graceful shutdown**
```bash
# In Terminal 1, press Ctrl+C
^C2026-01-19 10:35:00 | INFO | Received shutdown signal
2026-01-19 10:35:00 | INFO | Waiting for 1 running pulse to complete...
2026-01-19 10:35:02 | INFO | All pulses completed
2026-01-19 10:35:02 | INFO | Daemon shut down gracefully
```

---

## Phase 6: HTTP API (Day 3, Afternoon)

**Goal**: Allow external systems to trigger pulses.

### Tasks

1. **FastAPI Server** (`src/reeve/api/server.py`)
   - Implement `create_api_server()` function
   - Implement endpoints:
     - `POST /api/pulse/trigger` - Create pulse
     - `GET /api/pulse/upcoming` - List pulses
     - `GET /api/health` - Health check
     - `GET /api/status` - Daemon status
   - Add authentication (Bearer token)
   - Use Pydantic models for validation
   - See [03_DAEMON_AND_API.md](03_DAEMON_AND_API.md)

2. **Integrate with Daemon**
   - Add `_run_api_server()` method to daemon
   - Run API concurrently with scheduler

3. **Testing**
   - Unit tests for each endpoint
   - Integration test: API → Database → Execution
   - Test authentication (valid/invalid tokens)

**Deliverables**:
- ⌛ Working REST API
- ⌛ API runs alongside daemon
- ⌛ Token authentication working

**Validation**:
```bash
# Start daemon (includes API)
uv run python -m reeve.pulse

# Test health endpoint
curl http://localhost:8765/api/health

# Trigger pulse
curl -X POST http://localhost:8765/api/pulse/trigger \
  -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Test from API",
    "scheduled_at": "now",
    "priority": "high",
    "source": "curl"
  }'

# List upcoming
curl -H "Authorization: Bearer your_token" \
  http://localhost:8765/api/pulse/upcoming?limit=10
```

**Demo**: HTTP API Integration

**Prerequisites**:
```bash
# Set API token in .env file
echo "PULSE_API_TOKEN=your_secret_token_here" >> .env
```

**Step 1: Start daemon with API** (Terminal 1)
```bash
uv run python -m reeve.pulse

# Expected output:
# 2026-01-19 10:30:00 | INFO | Starting Pulse Daemon...
# 2026-01-19 10:30:00 | INFO | Starting HTTP API on port 8765...
# 2026-01-19 10:30:00 | INFO | API docs available at http://localhost:8765/docs
# 2026-01-19 10:30:00 | INFO | Scheduler loop started
```

**Step 2: Run demo script** (Terminal 2)
```bash
uv run python demos/phase6_api_demo.py

# The script will test all API endpoints:
# ✓ Health check
# ✓ Status endpoint
# ✓ Trigger pulse (immediate)
# ✓ Trigger pulse (scheduled)
# ✓ List upcoming pulses
# ✓ Authentication (valid token)
# ✓ Authentication (invalid token - should fail)
#
# Expected output:
# ✓ Health check: {"status": "healthy", "version": "0.1.0"}
# ✓ Status: {"daemon_uptime": "5m", "pulses_executed": 42, "pending": 3}
# ✓ Triggered immediate pulse: {"pulse_id": 123, "scheduled_at": "now"}
# ✓ Triggered scheduled pulse: {"pulse_id": 124, "scheduled_at": "2026-01-19T11:00:00Z"}
# ✓ Listed 2 upcoming pulses
# ✓ Invalid token rejected with 401
# ✓ Phase 6 Demo Complete!
```

**Step 3: Manual curl testing**
```bash
# Health check (no auth required)
curl http://localhost:8765/api/health

# Trigger a pulse
curl -X POST http://localhost:8765/api/pulse/trigger \
  -H "Authorization: Bearer your_secret_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Check my calendar and send me a summary",
    "scheduled_at": "now",
    "priority": "high",
    "source": "manual_curl"
  }'

# Expected response:
# {"pulse_id": 125, "scheduled_at": "2026-01-19T10:30:15Z", "status": "pending"}

# Watch Terminal 1 (daemon logs):
# 2026-01-19 10:30:15 | INFO | API: Received pulse trigger from manual_curl
# 2026-01-19 10:30:15 | INFO | Executing pulse #125 (HIGH): "Check my calendar..."
# 2026-01-19 10:30:18 | INFO | Pulse #125 completed successfully (2.8s)
```

**Step 4: Explore API docs**
```bash
# Open browser to http://localhost:8765/docs
# FastAPI provides interactive Swagger UI for testing all endpoints
```

---

## Phase 7: Telegram Integration (Day 4, Morning)

**Goal**: Migrate Telegram listener to use new architecture.

### Tasks

1. **New Telegram Listener** (`src/reeve/integrations/telegram.py`)
   - Implement `TelegramListener` class
   - Poll Telegram API for messages
   - POST to Pulse API instead of calling Goose directly
   - See [03_DAEMON_AND_API.md](03_DAEMON_AND_API.md)

2. **Testing**
   - Test with real Telegram bot
   - Send message → should create pulse → should execute → Reeve should respond

3. **Deprecate Prototype**
   - Move `telegram_prototype/` to `telegram_prototype_old/`
   - Update documentation

**Deliverables**:
- ⌛ Production-ready Telegram listener
- ⌛ End-to-end message flow working
- ⌛ Prototype deprecated

**Validation**:
```bash
# Terminal 1: Start daemon
uv run python -m reeve.pulse

# Terminal 2: Start Telegram listener
uv run python -m reeve.integrations.telegram

# Terminal 3: Send Telegram message
# Should see:
# - Listener: "📩 Telegram message from User: hello"
# - Listener: "✓ Pulse 123 triggered"
# - Daemon: "Executing pulse 123: Telegram message from User: hello"
# - Daemon: "Pulse 123 completed successfully"
```

**Demo**: Telegram Integration (Full Loop)

**Prerequisites**:
```bash
# Ensure Telegram credentials are in .env
# TELEGRAM_BOT_TOKEN=your_bot_token
# TELEGRAM_CHAT_ID=your_chat_id
# PULSE_API_TOKEN=your_secret_token
```

**Step 1: Start daemon** (Terminal 1)
```bash
uv run python -m reeve.pulse

# Expected output:
# 2026-01-19 10:30:00 | INFO | Starting Pulse Daemon...
# 2026-01-19 10:30:00 | INFO | Starting HTTP API on port 8765...
# 2026-01-19 10:30:00 | INFO | Scheduler loop started
```

**Step 2: Start Telegram listener** (Terminal 2)
```bash
uv run python -m reeve.integrations.telegram

# Expected output:
# 2026-01-19 10:30:05 | INFO | Starting Telegram Listener...
# 2026-01-19 10:30:05 | INFO | Bot username: @YourBotName
# 2026-01-19 10:30:05 | INFO | Listening for messages from chat_id: 123456789
# 2026-01-19 10:30:05 | INFO | Polling for updates...
```

**Step 3: Run demo script** (Terminal 3)
```bash
uv run python demos/phase7_telegram_demo.py

# The script will:
# 1. Send a test message to the bot
# 2. Verify the listener receives it
# 3. Verify a pulse is triggered via API
# 4. Verify the daemon executes it
# 5. Verify Reeve responds back via Telegram
```

**Expected output across terminals**:

**Terminal 2 (Telegram Listener)**:
```
2026-01-19 10:30:10 | INFO | 📩 Telegram message from User (123456789): hello
2026-01-19 10:30:10 | INFO | Triggering pulse via API...
2026-01-19 10:30:10 | INFO | ✓ Pulse 42 triggered
```

**Terminal 1 (Daemon)**:
```
2026-01-19 10:30:10 | INFO | API: Received pulse trigger from telegram
2026-01-19 10:30:10 | INFO | Executing pulse #42 (CRITICAL): "Telegram message from User: hello"
2026-01-19 10:30:10 | INFO | Launching Hapi session...
2026-01-19 10:30:13 | INFO | Pulse #42 completed successfully (3.1s)
```

**Your Telegram App**:
```
[Your message]
hello

[Bot's response]
Hi! I received your message. How can I help you today?

💬 View in Claude Code: https://hapi.example.com/session/abc123
```

**Step 4: Test complex interactions**
```bash
# Send: "What's on my calendar today?"
# Expected: Bot responds with your calendar summary

# Send: "Remind me to call John in 2 hours"
# Expected: Bot confirms and schedules a pulse

# Send: "What's the weather like?"
# Expected: Bot fetches weather and responds
```

---

## Phase 8: Deployment (Day 4, Afternoon)

**Goal**: Production deployment with systemd.

### Tasks

1. **Systemd Service Files**
   - Create `reeve-daemon.service`
   - Create `reeve-telegram.service`
   - See [04_DEPLOYMENT.md](04_DEPLOYMENT.md) for templates

2. **Install Services**
   - Copy to `/etc/systemd/system/`
   - Enable and start services
   - Verify with `systemctl status`

3. **Monitoring Setup**
   - Configure log rotation
   - Setup health check cron
   - Setup database backups

4. **Documentation**
   - Update `.env.example` with all variables
   - Write deployment checklist
   - Document troubleshooting steps

**Deliverables**:
- ⌛ Daemon running as systemd service
- ⌛ Telegram listener as systemd service
- ⌛ Monitoring and backups configured
- ⌛ Complete deployment documentation

**Validation**:
```bash
# Check services
sudo systemctl status reeve-daemon
sudo systemctl status reeve-telegram

# Test end-to-end
# Send Telegram message → Reeve responds

# Check logs
sudo journalctl -u reeve-daemon -f
```

**Demo**: Production Deployment

**Step 1: Install as systemd services**
```bash
# Run the deployment script
sudo bash demos/phase8_deployment_demo.sh

# Expected output:
# ✓ Created systemd service: reeve-daemon.service
# ✓ Created systemd service: reeve-telegram.service
# ✓ Reloaded systemd daemon
# ✓ Enabled reeve-daemon.service
# ✓ Enabled reeve-telegram.service
# ✓ Started reeve-daemon.service
# ✓ Started reeve-telegram.service
# ✓ Services are running
```

**Step 2: Verify services are running**
```bash
sudo systemctl status reeve-daemon

# Expected output:
# ● reeve-daemon.service - Reeve Pulse Queue Daemon
#    Loaded: loaded (/etc/systemd/system/reeve-daemon.service; enabled)
#    Active: active (running) since Sun 2026-01-19 10:30:00 UTC; 5min ago
#    Main PID: 12345 (python)
#    Tasks: 3 (limit: 4915)
#    Memory: 45.2M
#    CGroup: /system.slice/reeve-daemon.service
#            └─12345 /usr/bin/python -m reeve.pulse
#
# Jan 19 10:30:00 hostname systemd[1]: Started Reeve Pulse Queue Daemon
# Jan 19 10:30:00 hostname python[12345]: INFO | Starting Pulse Daemon...
# Jan 19 10:30:00 hostname python[12345]: INFO | Scheduler loop started
```

**Step 3: Test end-to-end functionality**
```bash
# Send a Telegram message
# Expected: Bot responds within a few seconds

# Check daemon logs
sudo journalctl -u reeve-daemon -n 50

# Expected to see pulse execution logs
```

**Step 4: Test automatic restart**
```bash
# Simulate a crash
sudo kill -9 $(pgrep -f "reeve.pulse.daemon")

# Wait a few seconds, then check status
sleep 5
sudo systemctl status reeve-daemon

# Expected: Service should auto-restart
# Active: active (running) since Sun 2026-01-19 10:35:15 UTC; 2s ago
```

**Step 5: Verify monitoring and backups**
```bash
# Check log rotation
ls -lh /var/log/reeve/

# Check database backup
ls -lh ~/.reeve/backups/

# Check health check cron
crontab -l | grep reeve

# Expected:
# */5 * * * * /usr/local/bin/reeve-health-check.sh
# 0 3 * * * /usr/local/bin/reeve-backup.sh
```

**Step 6: Graceful shutdown test**
```bash
# Stop services
sudo systemctl stop reeve-daemon
sudo systemctl stop reeve-telegram

# Verify they stopped cleanly
sudo journalctl -u reeve-daemon -n 10

# Expected to see graceful shutdown logs:
# Jan 19 10:40:00 hostname python[12345]: INFO | Received shutdown signal
# Jan 19 10:40:00 hostname python[12345]: INFO | Waiting for running pulses...
# Jan 19 10:40:02 hostname python[12345]: INFO | Daemon shut down gracefully
```

---

## Phase 9: Integration Testing & Polish (Ongoing)

**Goal**: Ensure everything works together reliably.

### Tasks

1. **Integration Test Suite**
   - Write end-to-end tests covering full flow:
     - MCP → Queue → Execution
     - External trigger → API → Queue → Execution
     - Telegram → API → Queue → Execution → Response
   - Test failure scenarios (Hapi crash, DB lock, etc.)
   - Test retry logic

2. **Performance Testing**
   - Load test: 1000 pulses scheduled simultaneously
   - Measure execution latency
   - Optimize slow queries

3. **Documentation**
   - Update README.md with architecture diagram
   - Add usage examples
   - Document common workflows

4. **Edge Cases**
   - Test timezone handling
   - Test very long prompts (>1000 chars)
   - Test rapid pulse scheduling
   - Test database recovery after crash

**Deliverables**:
- ⌛ Comprehensive test suite
- ⌛ Performance benchmarks
- ⌛ Updated documentation
- ⌛ Hardened error handling

---

## Demo Strategy & Self-Testing

### Philosophy

After each phase is complete, there are **two levels of validation**:

1. **Automated Tests**: Unit tests and integration tests (already covered in each phase)
2. **Real-World Demos**: Interactive demonstrations using actual APIs and services

The demos serve multiple purposes:
- **Verify functionality** with real-world data and APIs
- **Provide examples** for users to understand what's possible
- **Enable testing** by Claude before handing off to the user
- **Document usage** through concrete examples

### Demo Scripts Location

All demo scripts are in the `demos/` directory:
```
demos/
  phase1_database_demo.py       # Database schema and model creation
  phase2_queue_demo.py          # Queue operations (schedule, query, retry)
  phase3_mcp_demo.py            # MCP tools integration
  phase4_executor_demo.py       # Pulse execution with Hapi
  phase5_daemon_demo.py         # Daemon orchestration
  phase6_api_demo.py            # HTTP API endpoints
  phase7_telegram_demo.py       # Telegram bot integration
  phase8_deployment_demo.sh     # Systemd deployment
```

### Self-Testing Protocol (for Claude)

After implementing each phase, Claude should:

1. **Run automated tests first**:
   ```bash
   uv run pytest tests/ -v -k "phase_N"
   ```

2. **Run the demo script**:
   ```bash
   uv run python demos/phaseN_*_demo.py
   ```

3. **For MCP phases (3+), use MCP tools directly**:
   - Claude has access to the MCP servers in the current session
   - Can call `schedule_pulse()`, `list_upcoming_pulses()`, etc. directly
   - Can verify responses and behavior in real-time

4. **For daemon/API phases (5+), test with background processes**:
   ```bash
   # Start daemon in background
   uv run python -m reeve.pulse &

   # Run demo script to interact with it
   uv run python demos/phase5_daemon_demo.py

   # Clean up background process
   pkill -f "reeve.pulse.daemon"
   ```

5. **For Telegram phases (3, 7), test with real Telegram API** (if credentials available):
   - Use `send_notification()` MCP tool to send test message
   - Verify message appears in Telegram
   - For Phase 7, verify full message loop

6. **Report results to user**:
   - Confirm what was tested
   - Share any interesting output or observations
   - Flag any issues or unexpected behavior
   - Provide next steps for user to try

### Example Self-Testing Workflow

**After completing Phase 3 (MCP Integration)**:

```
Claude's internal process:

1. Run tests: ✅ 51/51 tests passed
2. Run demo script: ✅ Successfully scheduled/listed/cancelled pulses
3. Test MCP tools directly:
   - schedule_pulse(scheduled_at="in 1 minute", prompt="Test", priority="high")
   - list_upcoming_pulses(limit=5)
   - Result: ✅ Tools work correctly, pulse scheduled
4. Test Telegram notifier (if configured):
   - send_notification(message="Test from Claude", priority="normal")
   - Check: ✅ Message sent, Telegram API responded
5. Report to user:
   "✅ Phase 3 complete and tested! I've verified:
    - All 18 MCP tests pass
    - Demo script works
    - MCP tools are functional (scheduled a test pulse)
    - Telegram notifier works (sent test message)

    Ready for you to try! Use the demo commands in the updated roadmap."
```

### Real-World API Usage

Each demo uses real APIs where appropriate:

| Phase | Real APIs Used |
|-------|----------------|
| 1-2 | SQLite database (local) |
| 3 | SQLite database + Telegram Bot API (optional) |
| 4 | SQLite + Hapi CLI (if available, else mock) |
| 5 | SQLite + Hapi CLI |
| 6 | SQLite + Hapi CLI + HTTP REST API |
| 7 | SQLite + Hapi CLI + HTTP API + Telegram Bot API |
| 8 | All of the above + systemd + cron |

### Running Demos Safely

All demo scripts:
- Use the actual production database (`~/.reeve/pulse_queue.db`)
- Create test data with clear labels (e.g., "DEMO: Test pulse")
- Clean up after themselves (optional `--cleanup` flag)
- Are idempotent (safe to run multiple times)
- Provide verbose output for debugging

### Demo Output Format

Each demo follows this structure:
```
✓ [Step description]
  - [Detail 1]
  - [Detail 2]

Expected output:
─────────────────────────────────────
[Actual output from API/command]
─────────────────────────────────────

✓ Phase N Demo Complete!
```

---

## Success Criteria

The Pulse Queue system is complete when:

1. 🔄 **Reeve can schedule its own wake-ups** (Partially Complete)
   - ✅ MCP tools work from Claude Code (Phase 3)
   - ✅ Executor can launch Hapi sessions (Phase 4)
   - ⌛ Pulses execute at correct times (Phase 5: Daemon)
   - ✅ Session resumption supported by executor (Phase 4)
   - ⌛ End-to-end scheduling + execution (Phase 5)

2. ⌛ **External events trigger Reeve**
   - ⌛ Telegram messages → immediate pulses (Phase 6-7: API + Telegram)
   - ⌛ HTTP API accessible to other integrations (Phase 6)
   - ⌛ Authentication enforced (Phase 6)

3. ⌛ **Production-ready**
   - ⌛ Runs as systemd service (Phase 8)
   - ⌛ Automatic restarts on crash (Phase 8)
   - ⌛ Logs rotated and monitored (Phase 8)
   - ⌛ Database backed up daily (Phase 8)

4. 🔄 **Documented** (Partially Complete)
   - ✅ Implementation guide complete (Phases 1-4 documented)
   - ✅ MCP setup guide complete (docs/MCP_SETUP.md)
   - ⌛ Deployment guide complete (Phase 8)
   - ⌛ Troubleshooting guide complete (Phase 8)
   - ✅ Code well-commented (Phases 1-4)

5. 🔄 **Tested** (Partially Complete)
   - ✅ Unit tests for queue, MCP, and executor components (69/69 tests passing)
   - ⌛ Integration tests for full flows (Phase 9)
   - ⌛ Manual testing completed (Phase 9)
   - ⌛ Performance acceptable (Phase 9)

---

## Implementation Notes

### Code Quality Standards

- **Type hints**: All functions fully typed
- **Docstrings**: All public APIs documented
- **Error handling**: Graceful failures with logging
- **Testing**: Aim for >80% coverage
- **Formatting**: Use `black` and `isort`

### Development Workflow

```bash
# Start development session
cd ~/workspace/reeve_bot
uv sync

# Run tests
uv run pytest tests/ -v

# Format code
uv run black src/
uv run isort src/

# Type check
uv run mypy src/

# Run daemon (dev mode)
uv run python -m reeve.pulse
```

### Git Workflow

```bash
# Feature branch
git checkout -b feature/pulse-queue-phase-1

# Commit frequently
git add src/reeve/pulse/enums.py
git commit -m "Add PulsePriority and PulseStatus enums"

# Merge when phase complete
git checkout main
git merge feature/pulse-queue-phase-1
```

---

## Dependencies Between Phases

```
Phase 1 (Foundation)
    ↓
Phase 2 (Queue) ←─────┐
    ↓                 │
    ├─→ Phase 3 (MCP) │
    │       ↓         │
    └─→ Phase 4 (Executor)
            ↓         │
        Phase 5 (Daemon)
            ↓         │
        Phase 6 (API) ←┘
            ↓
        Phase 7 (Telegram)
            ↓
        Phase 8 (Deployment)
            ↓
        Phase 9 (Testing)
```

**Key**: Phases 3-6 can partially overlap, but each depends on Phase 2 (Queue).

---

## Next Session Prompt

When starting Phase 4, use this prompt:

```
I'm ready to implement Phase 4 (Pulse Executor) for the Pulse Queue system.

Please implement:
1. PulseExecutor class (src/reeve/pulse/executor.py) that:
   - Launches Hapi subprocess with correct working directory
   - Handles sticky notes (prepends them to the prompt)
   - Captures stdout/stderr
   - Reports success/failure
   - Handles timeouts and crashes gracefully
2. Unit tests with mocked Hapi command
3. Test prompt building with sticky notes
4. Test error handling (Hapi crash, timeout, etc.)

Refer to docs/03_DAEMON_AND_API.md for the complete executor specifications.

Let's begin!
```

---

## Estimated Timeline

| Phase | Tasks | Status | Time Spent |
|-------|-------|--------|------------|
| 1. Foundation | Project structure, models, migrations | ✅ Complete | ~2 hours |
| 2. Queue | PulseQueue class + tests | ✅ Complete | ~3 hours |
| 3. MCP Servers | Two MCP servers with tools | ✅ Complete | ~3 hours |
| 4. Executor | Hapi subprocess execution | ✅ Complete | ~1.5 hours |
| 5. Daemon | Main daemon loop | ✅ Complete | ~3 hours |
| 6. HTTP API | FastAPI endpoints | ⌛ Pending | 2-3 hours |
| 7. Telegram | Listener integration | ⌛ Pending | 1-2 hours |
| 8. Deployment | Systemd, monitoring | ⌛ Pending | 2-3 hours |
| 9. Testing | Integration tests, polish | ⌛ Pending | 3-4 hours |
| **Total** | | **5/9 Complete** | **~12.5 hours spent, 8-14 hours remaining** |

**Progress**: Phases 1-5 completed (Foundation, Queue Management, MCP Integration, Pulse Executor, Daemon)
**Next**: Phase 6 - HTTP API

---

## Change Log

- **2026-01-23**: Phase 5 (Pulse Daemon) completed
  - Implemented PulseDaemon class with scheduler loop (273 lines)
  - Added logging configuration with file rotation (72 lines)
  - Created entry point for module execution (59 lines)
  - Implemented 21 comprehensive unit tests for daemon operations
  - Created 2 integration tests for end-to-end validation
  - Key features: concurrent execution, graceful shutdown, error recovery
  - Total: 94/94 tests passing

- **2026-01-19**: Phase 4 (Pulse Executor) completed
  - Implemented PulseExecutor class with async Hapi subprocess execution
  - Added prompt building with sticky notes appended (not prepended)
  - Implemented timeout handling with configurable defaults
  - Created 18 comprehensive unit tests with mocked subprocess
  - All tests cover execution, error handling, and configuration
  - Total: 69/69 tests passing

- **2026-01-19**: Phase 3 (MCP Integration) completed
  - Implemented Pulse Queue MCP server with 4 tools
  - Implemented Telegram Notifier MCP server with 2 tools
  - Created comprehensive test suite (18 tests across 3 files)
  - Added MCP setup guide and configuration template
  - Total: 51/51 tests passing

- **2026-01-19**: Phase 2 (Queue Management) completed
  - Implemented PulseQueue class with 11 methods
  - Created 29 unit tests
  - Added configuration management
  - Enhanced database models with timezone support

- **2026-01-19**: Phase 1 (Foundation) completed
  - Set up project structure
  - Created database models and enums
  - Configured Alembic migrations
  - Created initial validation tests

---

Good luck with the implementation! Refer back to the detailed design docs as needed.
