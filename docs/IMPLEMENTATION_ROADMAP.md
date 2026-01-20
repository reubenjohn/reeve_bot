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
     - `send_notification()` - Push notifications via Telegram
     - `send_message_with_link()` - Notifications with inline keyboard buttons
   - Integrated with Telegram Bot API
   - Supports MarkdownV2, HTML, and plain text formatting
   - Priority levels: silent, normal, critical
   - Error handling for API failures

3. **MCP Configuration** ✅
   - Created `mcp_config.json.example` template
   - Documentation: `docs/MCP_SETUP.md` with setup and troubleshooting
   - Both servers configured with `uv run` commands
   - Server startup tested successfully

4. **Testing** ✅
   - Created `tests/test_mcp_servers.py` with 16 tests:
     - 9 time parsing tests (ISO, relative, keywords, edge cases)
     - 2 emoji helper tests
     - 2 pulse queue MCP tool tests
     - 2 Telegram notifier tests
     - 1 full integration test (schedule → list → cancel)
   - All tests pass (49/49 total across all phases)

**Deliverables**:
- ✅ Two working MCP servers built with FastMCP
- ✅ Type-safe tool definitions with Pydantic validation
- ✅ Comprehensive documentation for Claude and users
- ✅ 16 comprehensive tests with mocking and integration coverage
- ✅ Example configuration and setup guide

**Validation**:
```bash
# Run tests
uv run pytest tests/test_mcp_servers.py -v
# Result: 16/16 tests PASSED

# Test server startup
uv run python -m reeve.mcp.pulse_server
# Server starts and waits for stdio input ✓

uv run python -m reeve.mcp.notification_server
# Server starts (requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars) ✓

# Manual testing with Claude Code
# Configure MCP servers in ~/.config/claude-code/mcp_config.json
# Then in Claude Code session, tools are automatically available
```

---

## Phase 4: Pulse Executor (Day 2, Afternoon)

**Goal**: Execute pulses by launching Hapi sessions.

### Tasks

1. **PulseExecutor Class** (`src/reeve/pulse/executor.py`)
   - Implement `execute()` method
   - Launch Hapi subprocess with correct working directory
   - Handle sticky notes (prepend to prompt)
   - Capture stdout/stderr
   - Report success/failure
   - See [03_DAEMON_AND_API.md](03_DAEMON_AND_API.md)

2. **Testing**
   - Mock Hapi command for unit tests
   - Test prompt building with sticky notes
   - Test error handling (Hapi crash, timeout, etc.)

**Deliverables**:
- ⌛ Working executor that can launch Hapi
- ⌛ Tests with mocked Hapi

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

---

## Phase 5: Daemon (Day 3, Morning)

**Goal**: Build the main daemon process that ties everything together.

### Tasks

1. **Daemon Class** (`src/reeve/pulse/daemon.py`)
   - Implement `PulseDaemon` class
   - Implement `_scheduler_loop()` - polls every 1 second
   - Implement `_execute_pulse()` - async pulse execution
   - Implement `_build_prompt()` - adds sticky notes
   - Handle graceful shutdown (SIGTERM/SIGINT)
   - See [03_DAEMON_AND_API.md](03_DAEMON_AND_API.md)

2. **Logging** (`src/reeve/utils/logging.py`)
   - Setup structured logging
   - Log to file + stdout
   - Different log levels for dev/prod

3. **Testing**
   - Run daemon manually
   - Schedule pulses via MCP
   - Watch them execute
   - Verify database updates

**Deliverables**:
- ⌛ Functional daemon process
- ⌛ Pulse execution working end-to-end
- ⌛ Proper logging

**Validation**:
```bash
# Terminal 1: Start daemon
uv run python -m reeve.pulse.daemon

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
uv run python -m reeve.pulse.daemon

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
uv run python -m reeve.pulse.daemon

# Terminal 2: Start Telegram listener
uv run python -m reeve.integrations.telegram

# Terminal 3: Send Telegram message
# Should see:
# - Listener: "📩 Telegram message from User: hello"
# - Listener: "✓ Pulse 123 triggered"
# - Daemon: "Executing pulse 123: Telegram message from User: hello"
# - Daemon: "Pulse 123 completed successfully"
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

## Success Criteria

The Pulse Queue system is complete when:

1. 🔄 **Reeve can schedule its own wake-ups** (Partially Complete)
   - ✅ MCP tools work from Claude Code (Phase 3)
   - ⌛ Pulses execute at correct times (Phase 4-5: Executor + Daemon)
   - ⌛ Session resumption works (Phase 4-5)

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
   - ✅ Implementation guide complete (Phases 1-3 documented)
   - ✅ MCP setup guide complete (docs/MCP_SETUP.md)
   - ⌛ Deployment guide complete (Phase 8)
   - ⌛ Troubleshooting guide complete (Phase 8)
   - ✅ Code well-commented (Phases 1-3)

5. 🔄 **Tested** (Partially Complete)
   - ✅ Unit tests for queue and MCP components (49/49 tests passing)
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
uv run python -m reeve.pulse.daemon
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
| 4. Executor | Hapi subprocess execution | ⌛ Pending | 1-2 hours |
| 5. Daemon | Main daemon loop | ⌛ Pending | 2-3 hours |
| 6. HTTP API | FastAPI endpoints | ⌛ Pending | 2-3 hours |
| 7. Telegram | Listener integration | ⌛ Pending | 1-2 hours |
| 8. Deployment | Systemd, monitoring | ⌛ Pending | 2-3 hours |
| 9. Testing | Integration tests, polish | ⌛ Pending | 3-4 hours |
| **Total** | | **3/9 Complete** | **8 hours spent, 11-20 hours remaining** |

**Progress**: Phases 1-3 completed (Foundation, Queue Management, MCP Integration)
**Next**: Phase 4 - Pulse Executor

---

## Change Log

- **2026-01-19**: Phase 3 (MCP Integration) completed
  - Implemented Pulse Queue MCP server with 4 tools
  - Implemented Telegram Notifier MCP server with 2 tools
  - Created comprehensive test suite (16 tests)
  - Added MCP setup guide and configuration template
  - All 49 tests passing

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
