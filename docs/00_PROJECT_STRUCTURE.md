# Project Structure

## Overview

The `reeve_bot` repository contains the **Engine** component of Project Reeve - the immutable logic and infrastructure that powers the proactive "Chief of Staff" system. This is separate from the user's personal context (the "Desk"), which lives in a separate `my_reeve/` repository.

## Directory Structure

```
reeve_bot/
├── docs/                           # Architecture and implementation documentation
│   ├── 00_PROJECT_STRUCTURE.md    # This file
│   ├── 01_PULSE_QUEUE_DESIGN.md   # Pulse queue architecture
│   ├── 02_MCP_INTEGRATION.md      # MCP server specifications
│   └── 03_DEPLOYMENT.md           # Deployment and operations guide
│
├── src/
│   ├── reeve/                      # Main package
│   │   ├── __init__.py
│   │   ├── pulse/                  # Pulse Queue System
│   │   │   ├── __init__.py
│   │   │   ├── daemon.py          # Main daemon process
│   │   │   ├── queue.py           # Queue management (SQLAlchemy)
│   │   │   ├── models.py          # Database models
│   │   │   ├── executor.py        # Pulse execution logic (Hapi launcher)
│   │   │   └── enums.py           # Priority, Status enums
│   │   │
│   │   ├── mcp/                    # MCP Servers
│   │   │   ├── __init__.py
│   │   │   ├── pulse_server.py    # Pulse Queue MCP Server
│   │   │   └── notification_server.py  # Telegram Notification MCP Server
│   │   │
│   │   ├── integrations/           # External integration listeners
│   │   │   ├── __init__.py
│   │   │   ├── telegram.py        # Telegram bot listener
│   │   │   ├── email.py           # Gmail listener (future)
│   │   │   └── whatsapp.py        # WhatsApp listener (future)
│   │   │
│   │   ├── api/                    # HTTP REST API
│   │   │   ├── __init__.py
│   │   │   ├── server.py          # FastAPI/aiohttp server
│   │   │   └── routes.py          # Pulse trigger endpoints
│   │   │
│   │   └── utils/                  # Shared utilities
│   │       ├── __init__.py
│   │       ├── config.py          # Configuration management
│   │       └── logging.py         # Logging setup
│   │
├── cli/                            # Command-line tools
│   ├── pulse.py                   # `pulse` CLI tool for queue management
│   └── reeve-daemon.py            # Daemon launcher
│
├── telegram_prototype/             # Original prototype (deprecated after migration)
│   └── ...
│
├── tests/                          # Test suite
│   ├── test_pulse_queue.py
│   ├── test_mcp_server.py
│   └── fixtures/
│
├── pyproject.toml                 # Main project configuration (uv-managed)
├── uv.lock                        # Dependency lock file
├── .python-version                # Python version (3.11)
├── .env.example                   # Environment variable template
└── README.md                      # Project documentation
```

## Package Design Principles

### 1. Separation of Concerns

- **`pulse/`**: Pure business logic for queue management (no I/O concerns)
- **`mcp/`**: MCP protocol adapters (Reeve ↔ Pulse Queue)
- **`api/`**: HTTP REST adapters (External Systems ↔ Pulse Queue)
- **`integrations/`**: Event listeners that POST to API or Pulse Queue directly
- **`cli/`**: User-facing command-line tools

### 2. Dependency Flow

```
┌─────────────┐         ┌─────────────┐
│   Reeve     │◄────────┤ MCP Server  │
│  (Claude)   │  stdio  │ (pulse_*)   │
└─────────────┘         └──────┬──────┘
                               │
                               ▼
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Telegram   │─HTTP──► │  HTTP API   │────────►│ Pulse Queue │
│  Listener   │         │  (FastAPI)  │         │  (Core)     │
└─────────────┘         └─────────────┘         └──────┬──────┘
                                                       │
                               ┌───────────────────────┘
                               ▼
                        ┌─────────────┐
                        │   SQLite    │
                        │  (via ORM)  │
                        └─────────────┘
```

### 3. Configuration Strategy

**Environment Variables** (`.env` file):
- `REEVE_DESK_PATH`: Path to user's Desk repository (e.g., `~/my_reeve/`)
- `PULSE_DB_PATH`: Path to SQLite database (default: `$REEVE_DESK_PATH/.reeve/pulse_queue.db`)
- `PULSE_API_PORT`: HTTP API port (default: `8765`)
- `PULSE_API_TOKEN`: Authentication token for HTTP API
- `HAPI_COMMAND`: Path to Hapi executable (default: `hapi`)

**Why this approach:**
- Allows different deployments (local dev, production, testing)
- User's Desk path is configurable (different users = different contexts)
- API token provides security for external triggers

### 4. Database Strategy

**SQLAlchemy + SQLite**:
- **Development/Production**: Single-user system, SQLite is perfect
- **Alembic Migrations**: Version-controlled schema changes
- **Why not Postgres?**: Overkill for single-user, adds deployment complexity
- **Future**: If multi-user, swap to Postgres with minimal code changes (ORM abstraction)

### 5. Execution Model

**Long-Running Daemon**:
- Single Python process running via systemd/supervisor
- Asyncio event loop for concurrency
- Runs multiple services in parallel:
  1. Pulse scheduler loop (checks queue every 1 second)
  2. MCP server (stdio, spawned by Reeve on-demand)
  3. HTTP API server (persistent, for external events)

### 6. MCP Server Design

**Two MCP Servers**:

1. **`pulse-queue` MCP Server** (src/reeve/mcp/pulse_server.py):
   - Tools: `schedule_pulse`, `list_upcoming_pulses`, `cancel_pulse`, `reschedule_pulse`
   - Used by: Reeve (primary interface)

2. **`telegram-notifier` MCP Server** (src/reeve/mcp/notification_server.py):
   - Tools: `send_notification`, `send_message`
   - Used by: Reeve (to push notifications to user)

**Why separate servers?**
- Logical separation (scheduling vs. output)
- Can be deployed independently
- Different security scopes

## Integration Points

### 1. Reeve (Hapi/Claude Code)

**Connection**: MCP stdio servers defined in `~/.config/claude-code/mcp_config.json`

```json
{
  "mcpServers": {
    "pulse-queue": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/reeve_bot", "python", "-m", "reeve.mcp.pulse_server"]
    },
    "telegram-notifier": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/reeve_bot", "python", "-m", "reeve.mcp.notification_server"]
    }
  }
}
```

**Usage**: Reeve calls `schedule_pulse()` when it needs to wake up in the future.

### 2. External Event Listeners (Telegram, Email, etc.)

**Connection**: HTTP POST to `http://localhost:8765/api/pulse/trigger`

**Authentication**: Bearer token in `Authorization` header

**Example**:
```python
# telegram_listener.py
requests.post('http://localhost:8765/api/pulse/trigger',
    headers={'Authorization': f'Bearer {API_TOKEN}'},
    json={
        'prompt': f'Telegram message from {user}: {text}',
        'priority': 'HIGH',
        'scheduled_at': 'now'
    }
)
```

### 3. The Desk (my_reeve/)

**Connection**: Pulse executor changes working directory to Desk before launching Hapi

**File Structure Expected**:
```
my_reeve/
├── CLAUDE.md           # System prompt ("You are Reeve...")
├── SKILLS.md           # Available tools/skills
├── Goals/              # High-level objectives
├── Responsibilities/   # Recurring duties
├── Preferences/        # User preferences
└── Diary/              # Reeve's internal logs
```

**Execution Flow**:
1. Pulse becomes due
2. Daemon executes pulse: `cd ~/my_reeve && hapi run --prompt "{pulse.prompt}"`
3. Hapi/Claude Code runs with Desk as PWD → has access to all context files

## Future Extensions

### 1. Activity Queue (Low-Urgency Events)

**Structure**:
```
src/reeve/activity/
├── queue.py           # Separate queue for passive events
└── models.py          # Activity models
```

**Design**: Separate table, different processing loop (batched summaries)

### 2. Sub-Agent Management

**Structure**:
```
src/reeve/agents/
├── manager.py         # Spawn/monitor sub-agents
├── blackboard.py      # Shared Desk file coordination
└── lifecycle.py       # Start/stop/cleanup
```

**Design**: Sub-agents run as separate Hapi sessions, report via Desk files

### 3. Additional Integrations

**Structure**:
```
src/reeve/integrations/
├── email.py           # Gmail listener
├── whatsapp.py        # WhatsApp listener
├── calendar.py        # Google Calendar sync
└── github.py          # GitHub webhook handler
```

**Design**: Each listener is an independent process that POSTs to HTTP API

## Technology Choices

### Why uv?

- **Fast**: Rust-based, faster than pip/poetry
- **Lock file**: Reproducible builds
- **Modern**: PEP 621 compliant pyproject.toml
- **Script runner**: `uv run python -m reeve.pulse.daemon`

### Why FastAPI (or aiohttp)?

- **Async**: Matches asyncio event loop in daemon
- **Type hints**: Pydantic validation
- **Auto-docs**: OpenAPI/Swagger for debugging
- **Lightweight**: Fast startup, low overhead

### Why SQLAlchemy?

- **ORM**: Type-safe models, migrations
- **Async support**: SQLAlchemy 2.0 async API
- **Portable**: Easy to swap SQLite → Postgres
- **Battle-tested**: Industry standard

### Why Systemd/Supervisor?

- **Process management**: Auto-restart on crash
- **Logging**: stdout → syslog/journald
- **Platform-native**: Works on Linux servers
- **Simple**: Declarative config files

## Development Workflow

### 1. Initial Setup

```bash
cd /path/to/reeve_bot
uv sync  # Install dependencies
cp .env.example .env  # Configure environment
uv run alembic upgrade head  # Initialize database
```

### 2. Running in Development

```bash
# Terminal 1: Run daemon
uv run python -m reeve.pulse.daemon

# Terminal 2: Trigger test pulse
uv run python cli/pulse.py schedule "Test pulse" --priority HIGH

# Terminal 3: Watch logs
tail -f ~/.reeve/logs/daemon.log
```

### 3. Running Tests

```bash
uv run pytest tests/
```

### 4. Production Deployment

```bash
# Install systemd service
sudo cp reeve-daemon.service /etc/systemd/system/
sudo systemctl enable reeve-daemon
sudo systemctl start reeve-daemon

# Check status
sudo systemctl status reeve-daemon
journalctl -u reeve-daemon -f
```

## Next Steps

See the following documentation for detailed implementation:

1. **[01_PULSE_QUEUE_DESIGN.md](01_PULSE_QUEUE_DESIGN.md)**: Database schema, queue logic, priority system
2. **[02_MCP_INTEGRATION.md](02_MCP_INTEGRATION.md)**: MCP server tools, type hints, documentation
3. **[03_DEPLOYMENT.md](03_DEPLOYMENT.md)**: Systemd setup, monitoring, troubleshooting
