# Pulse Queue System Documentation

## Overview

This directory contains comprehensive documentation for implementing the Pulse Queue system - the core scheduling mechanism that enables Reeve's proactive "Chief of Staff" behavior.

## Quick Start

**New to the project?** Start here:

1. Read [00_PROJECT_STRUCTURE.md](00_PROJECT_STRUCTURE.md) - Understand overall architecture
2. Read [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) - Step-by-step implementation guide
3. Follow the roadmap phases in order

**Implementing a specific component?** Jump to:

- **Database & Queue Logic**: [01_PULSE_QUEUE_DESIGN.md](01_PULSE_QUEUE_DESIGN.md)
- **MCP Tools for Reeve**: [02_MCP_INTEGRATION.md](02_MCP_INTEGRATION.md)
- **Daemon & HTTP API**: [03_DAEMON_AND_API.md](03_DAEMON_AND_API.md)
- **Production Deployment**: [04_DEPLOYMENT.md](04_DEPLOYMENT.md)

---

## Document Index

### [00_PROJECT_STRUCTURE.md](00_PROJECT_STRUCTURE.md)
**What**: Overall system architecture and directory organization

**Key Topics**:
- Dual-repo architecture (Engine vs. Desk)
- Package design principles
- Dependency flow diagrams
- Integration points (Reeve, Telegram, Email, etc.)
- Future extension points

**When to read**: Before starting implementation, to understand the big picture

---

### [01_PULSE_QUEUE_DESIGN.md](01_PULSE_QUEUE_DESIGN.md)
**What**: Detailed design of the pulse queue and database layer

**Key Topics**:
- Core concepts (Pulse, Priority, Status)
- Database schema (SQLAlchemy models)
- Priority system (5 levels: critical → deferred)
- Queue management logic (PulseQueue class)
- Retry mechanisms and failure handling
- Design rationale for key decisions

**When to read**: Phase 1-2 of implementation (Foundation & Queue)

**Key Code**:
- `PulsePriority` enum
- `PulseStatus` enum
- `Pulse` SQLAlchemy model
- `PulseQueue` async class

---

### [02_MCP_INTEGRATION.md](02_MCP_INTEGRATION.md)
**What**: MCP server specifications and tool definitions

**Key Topics**:
- Two MCP servers (pulse-queue, telegram-notifier)
- Tool definitions with proper type hints
- Comprehensive docstrings for Claude
- Configuration (mcp_config.json)
- Testing MCP tools

**When to read**: Phase 3 of implementation (MCP Servers)

**Key Code**:
- `src/reeve/mcp/pulse_server.py` - Full implementation
- `src/reeve/mcp/notification_server.py` - Full implementation
- Tool schemas with `Annotated[Type, Field(...)]`

**Example Tools**:
```python
schedule_pulse(
    scheduled_at="tomorrow at 9am",
    prompt="Daily briefing",
    priority="normal"
)

send_notification(
    message="🔔 Task completed!",
    parse_mode="MarkdownV2"
)
```

---

### [03_DAEMON_AND_API.md](03_DAEMON_AND_API.md)
**What**: Daemon process and HTTP API implementation

**Key Topics**:
- PulseDaemon main loop (scheduler + API)
- PulseExecutor (launches Hapi sessions)
- FastAPI HTTP endpoints
- External integration pattern (Telegram listener)
- Configuration management

**When to read**: Phase 4-7 of implementation (Executor, Daemon, API, Integrations)

**Key Code**:
- `src/reeve/pulse/daemon.py` - Main daemon
- `src/reeve/pulse/executor.py` - Hapi launcher
- `src/reeve/api/server.py` - FastAPI app
- `src/reeve/integrations/telegram.py` - Telegram listener

**Key Endpoints**:
```bash
POST /api/pulse/trigger   # Create pulse
GET  /api/pulse/upcoming  # List pulses
GET  /api/health          # Health check
```

---

### [04_DEPLOYMENT.md](04_DEPLOYMENT.md)
**What**: Production deployment guide

**Key Topics**:
- Systemd service setup
- Monitoring and logging
- Database backups
- Security hardening
- Troubleshooting common issues
- Upgrade/rollback procedures

**When to read**: Phase 8-9 of implementation (Deployment & Testing)

**Key Files**:
- `reeve-daemon.service` - Systemd service for daemon
- `reeve-telegram.service` - Systemd service for Telegram listener
- Log rotation config
- Backup scripts

---

### [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)
**What**: Step-by-step implementation guide with 9 phases

**Key Topics**:
- Phase-by-phase breakdown
- Deliverables and validation for each phase
- Estimated timelines
- Dependencies between phases
- Success criteria
- Next session prompt

**When to read**: Throughout implementation, as your primary guide

**Phases**:
1. Foundation (structure, models, migrations)
2. Queue Management (PulseQueue class)
3. MCP Servers (tools for Reeve)
4. Pulse Executor (Hapi launcher)
5. Daemon (main loop)
6. HTTP API (external triggers)
7. Telegram Integration (listener)
8. Deployment (systemd)
9. Testing & Polish

---

## Architecture Diagrams

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Reeve Ecosystem                     │
│                                                             │
│  ┌──────────────┐                    ┌──────────────┐      │
│  │   Reeve      │◄──── MCP stdio ────┤ Pulse Queue  │      │
│  │ (Claude Code)│                    │  MCP Server  │      │
│  └──────┬───────┘                    └──────┬───────┘      │
│         │                                   │              │
│         │ Calls schedule_pulse()            │              │
│         │                                   ▼              │
│  ┌──────▼───────┐                    ┌─────────────┐      │
│  │  Telegram    │◄──── MCP stdio ────┤  Telegram   │      │
│  │  Notifier    │                    │ Notifier MCP│      │
│  │              │                    └─────────────┘      │
│  └──────────────┘                                         │
│                                                            │
└────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      Pulse Daemon Process                    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Scheduler   │  │   HTTP API   │  │  Executor    │     │
│  │   Loop       │  │  (FastAPI)   │  │  (Hapi)      │     │
│  │              │  │              │  │              │     │
│  │  Every 1s:   │  │  POST /pulse │  │  Launches    │     │
│  │  - Get due   │  │  GET /status │  │  Hapi        │     │
│  │  - Execute   │  │  GET /health │  │  sessions    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────▲───────┘     │
│         │                 │                  │             │
│         │                 │                  │             │
│         └─────────────────┴──────────────────┘             │
│                           ▼                                │
│                    ┌──────────────┐                        │
│                    │ PulseQueue   │                        │
│                    │ (Business    │                        │
│                    │  Logic)      │                        │
│                    └──────┬───────┘                        │
│                           ▼                                │
│                    ┌──────────────┐                        │
│                    │  SQLite DB   │                        │
│                    │  (pulses)    │                        │
│                    └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    External Integrations                     │
│                                                             │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────┐ │
│  │  Telegram    │     │    Email     │     │   Other     │ │
│  │  Listener    │     │   Listener   │     │  Webhooks   │ │
│  │              │     │   (future)   │     │  (future)   │ │
│  └──────┬───────┘     └──────┬───────┘     └──────┬──────┘ │
│         │                    │                     │        │
│         └────────────────────┴─────────────────────┘        │
│                              │                              │
│                    POST to HTTP API                         │
│                              │                              │
│                              ▼                              │
│                    Pulse Daemon (above)                     │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow: Telegram Message → Pulse Execution

```
1. User sends Telegram message
         │
         ▼
2. Telegram Listener receives message
         │
         ▼
3. POST /api/pulse/trigger
    {
      "prompt": "Telegram message from Alice: Hello",
      "scheduled_at": "now",
      "priority": "high"
    }
         │
         ▼
4. API validates and creates Pulse in database
    INSERT INTO pulses (scheduled_at, prompt, priority, ...)
         │
         ▼
5. Daemon scheduler loop detects due pulse (within 1 second)
    SELECT * FROM pulses WHERE scheduled_at <= NOW() AND status = 'pending'
         │
         ▼
6. Mark pulse as PROCESSING
    UPDATE pulses SET status = 'processing' WHERE id = X
         │
         ▼
7. PulseExecutor launches Hapi session
    cd ~/my_reeve && hapi run --text "Telegram message from Alice: Hello"
         │
         ▼
8. Reeve (Claude Code) processes message
    - Has access to Desk (Goals, Responsibilities, etc.)
    - Can call MCP tools (schedule_pulse, send_notification)
         │
         ▼
9. Reeve calls send_notification() to reply
    send_notification("Hi Alice! How can I help?")
         │
         ▼
10. Telegram Notifier MCP sends message to user
    POST https://api.telegram.org/botXXX/sendMessage
         │
         ▼
11. Mark pulse as COMPLETED
    UPDATE pulses SET status = 'completed', executed_at = NOW()
         │
         ▼
12. User receives Telegram notification from Reeve
```

### Pulse Lifecycle

```
                    ┌─────────────┐
                    │   PENDING   │ ◄─── schedule_pulse() creates pulse
                    └──────┬──────┘
                           │
           Daemon scheduler_loop() detects due pulse
                           │
                           ▼
                    ┌─────────────┐
                    │ PROCESSING  │ ◄─── mark_processing()
                    └──────┬──────┘
                           │
                   PulseExecutor.execute()
                           │
                ┌──────────┴──────────┐
                │                     │
           Success                 Failure
                │                     │
                ▼                     ▼
        ┌─────────────┐       ┌─────────────┐
        │  COMPLETED  │       │   FAILED    │
        └─────────────┘       └──────┬──────┘
                                     │
                              retry_count < max_retries?
                                     │
                        ┌────────────┴────────────┐
                        │                         │
                       Yes                       No
                        │                         │
                        ▼                         ▼
            Create new PENDING pulse      Remains FAILED
            (exponential backoff)         (manual intervention)

        User can call cancel_pulse() at any time:
        PENDING → CANCELLED
```

---

## Key Design Principles

### 1. Separation of Concerns

- **Queue logic** (`queue.py`): Pure business logic, database operations
- **Executor** (`executor.py`): Subprocess management, Hapi launching
- **Daemon** (`daemon.py`): Orchestration, scheduling loop
- **API** (`server.py`): HTTP protocol, authentication
- **MCP Servers** (`mcp/`): Tool definitions, Reeve interface

Each module has a single responsibility and clean interfaces.

### 2. Async-First Architecture

All I/O operations use `asyncio`:
- Database queries (`async with session`)
- HTTP requests (`await response.json()`)
- Subprocess execution (`asyncio.create_subprocess_exec`)

**Why**: Enables high concurrency without threading complexity.

### 3. Type Safety

All code uses:
- Type hints (`def foo(x: int) -> str`)
- Pydantic models (API validation)
- SQLAlchemy models (database schema)
- Enum classes (priorities, statuses)

**Why**: Catch bugs at development time, improve IDE support.

### 4. Observable & Debuggable

- Comprehensive logging at all levels
- SQLite database is inspectable with any SQLite client
- Clear error messages
- Health check endpoints

**Why**: Easy to diagnose issues in production.

### 5. Extensible

- Plugin architecture for integrations (just POST to API)
- MCP tools can be added without changing core logic
- Database schema supports migrations (Alembic)
- Priority levels are semantic, not hardcoded integers

**Why**: Easy to add features (Email listener, WhatsApp, Calendar sync) without major refactoring.

---

## Common Workflows

### For Reeve (Claude Code)

**Schedule a morning briefing**:
```python
schedule_pulse(
    scheduled_at="tomorrow at 9am",
    prompt="Daily morning briefing: review calendar, check email, summarize priorities",
    priority="normal",
    tags=["daily", "morning"]
)
```

**Set a follow-up reminder**:
```python
schedule_pulse(
    scheduled_at="in 2 hours",
    prompt="Check if user replied to snowboarding trip in group chat",
    priority="high",
    sticky_notes=["Sent message at 2:30 PM", "Waiting for Alex and Jamie"],
    tags=["follow_up", "social"]
)
```

**Send a notification**:
```python
send_notification(
    message="✓ Daily briefing complete. 3 meetings today, 2 urgent emails.",
    priority="normal"
)
```

### For External Systems (Telegram, Email, etc.)

**Trigger pulse from Telegram listener**:
```python
import requests

response = requests.post(
    'http://localhost:8765/api/pulse/trigger',
    headers={'Authorization': 'Bearer your_token'},
    json={
        'prompt': 'Telegram message from Alice: Can we meet tomorrow?',
        'scheduled_at': 'now',
        'priority': 'high',
        'source': 'telegram',
        'tags': ['telegram', 'user_message']
    }
)

pulse_id = response.json()['pulse_id']
```

### For System Administrators

**Check daemon status**:
```bash
sudo systemctl status reeve-daemon
sudo journalctl -u reeve-daemon -f
```

**Backup database**:
```bash
/usr/local/bin/reeve-backup
```

**Query pulse queue**:
```bash
sqlite3 ~/.reeve/pulse_queue.db "SELECT * FROM pulses WHERE status='pending' ORDER BY scheduled_at LIMIT 10;"
```

---

## Testing Strategy

### Unit Tests
- `tests/test_enums.py` - Enum validations
- `tests/test_models.py` - Database model constraints
- `tests/test_queue.py` - PulseQueue business logic
- `tests/test_executor.py` - Hapi execution (mocked)
- `tests/test_api.py` - FastAPI endpoints

**Run**: `uv run pytest tests/`

### Integration Tests
- End-to-end flows (MCP → Queue → Execution)
- External trigger flows (API → Queue → Execution)
- Failure scenarios (retry logic, error handling)

**Run**: `uv run pytest tests/integration/`

### Manual Testing
- Deploy to staging environment
- Send real Telegram messages
- Schedule pulses via Claude Code
- Verify execution and notifications

---

## Troubleshooting Quick Reference

### Daemon won't start
```bash
# Check logs
sudo journalctl -u reeve-daemon -xe

# Common issues:
# - Database locked: Kill other processes using DB
# - Missing deps: Run `uv sync`
# - Permission error: Check ~/.reeve ownership
```

### Pulses not executing
```bash
# Check scheduler loop is running
sudo journalctl -u reeve-daemon | grep "Executing pulse"

# Query stuck pulses
sqlite3 ~/.reeve/pulse_queue.db "SELECT * FROM pulses WHERE status='processing';"

# Reset stuck pulses
sqlite3 ~/.reeve/pulse_queue.db "UPDATE pulses SET status='pending' WHERE status='processing';"
```

### API not responding
```bash
# Check if port is bound
sudo netstat -tlnp | grep 8765

# Test health endpoint
curl http://localhost:8765/api/health

# Check authentication
curl -H "Authorization: Bearer wrong_token" http://localhost:8765/api/pulse/upcoming
# Should return 403
```

**Full troubleshooting guide**: [04_DEPLOYMENT.md](04_DEPLOYMENT.md)

---

## Contributing

When implementing new features or fixing bugs:

1. **Read the relevant design doc** for context
2. **Write tests first** (TDD approach)
3. **Follow type hints** and code quality standards
4. **Update documentation** if behavior changes
5. **Test end-to-end** before committing

---

## Questions?

If you're implementing the system and have questions:

1. Check if it's addressed in one of the design docs
2. Review the [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) for guidance
3. Look for similar patterns in the code examples
4. Test your understanding by writing unit tests

---

## License

This documentation is part of the Reeve project. See repository LICENSE for details.
