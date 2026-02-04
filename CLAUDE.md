# Reeve Bot - Implementation Context

## End Vision: The Proactive AI Chief of Staff

**Project Reeve** is building a proactive AI assistant that operates on a **"Push" paradigm** rather than waiting passively for prompts. Reeve functions as a high-fidelity proxy between the user and the world—filtering noise (email, group chats), coordinating logistics, and anticipating needs based on time and context. It acts as a **Gatekeeper** (protecting attention), **Proxy** (handling communication), and **Coach** (adapting to the user's energy and priorities).

The system uses a **Dual-Repo Architecture**: the **Engine** (`reeve-bot/`) contains immutable logic, while the **Desk** (`my_reeve/`) contains the user's personal context (Goals, Responsibilities, Preferences). Reeve "wakes up" on a **Pulse**—either periodically (hourly heartbeat) or aperiodically (self-scheduled alarms). When a pulse fires, it launches a Hapi/Claude Code session with access to the Desk. External events (Telegram messages, emails, calendar changes) can also trigger pulses via an HTTP API.

See [README.md](README.md) for the full philosophy and use cases.

---

## Project Overview

**Reeve Bot** (`reeve-bot/`) is the Engine component of Project Reeve. This repository contains the **Pulse Queue System**, which enables Reeve to schedule its own wake-ups and respond to external events.

A **Pulse** is a scheduled wake-up event for Reeve. When a pulse fires, it launches a Hapi/Claude Code session with a specific prompt and context, enabling proactive rather than reactive behavior.

## Current Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Foundation (DB, Models) | Completed |
| 2 | Queue Management | Completed |
| 3 | MCP Integration | Completed |
| 4 | Pulse Executor | Completed |
| 5 | Pulse Daemon | Completed |
| 6 | HTTP API | Completed |
| 7 | Telegram Integration | Completed |
| 8 | Production Deployment | Completed |

**Test Status**: 191/191 tests passing

See [Implementation Roadmap](docs/roadmap/index.md) for detailed phase documentation.

## Architecture Decisions

### Database
- **SQLite** with async support (`aiosqlite`) - single-user system
- Alembic for migrations

### Async Design
- All queue operations are async
- Concurrent MCP server + HTTP API + scheduler

### Priority System
```python
CRITICAL  # User messages, emergencies
HIGH      # External events, user-facing tasks
NORMAL    # Regular maintenance, scheduled checks
LOW       # Background tasks
DEFERRED  # Intentionally postponed
```

### Status Lifecycle
```
PENDING → PROCESSING → COMPLETED (success)
                     → FAILED (with retry)
                     → CANCELLED (manual)
```

### Key Design Patterns

1. **Composite Indexes**: Main query pattern optimized with `idx_pulse_execution` on `(status, scheduled_at, priority)`

2. **Retry Logic**: On failure, `scheduled_at` = now + 2^retry_count minutes (exponential backoff)

3. **String Enums**: All enums inherit from `str` for JSON serialization and human-readable DB values

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

## Documentation Responsibilities

When making changes to the codebase, keep documentation in sync:

| File | Purpose | Sync With |
|------|---------|-----------|
| `README.md` | **Teaser** - brief intro, links to full docs | Links only, no repeated content |
| `docs/index.md` | Full documentation homepage | Canonical source for detailed content |
| `docs/architecture/*.md` | Technical design docs | Code changes in relevant areas |
| `docs/roadmap/*.md` | Implementation phases | Progress updates |
| `CLAUDE.md` | AI assistant context | Implementation status, file references |

### Documentation Style Guidelines
- **Minimal redundancy**: Don't repeat content across files. Use references/links instead.
- **README as engaging teaser**: Spark curiosity by hinting at *why it matters*, not just what it is. Keep users interested and engaged.
  - Pattern: "Brief description. This is important/core because X. [Learn more](url)"
  - Goal: Make the reader want to click "Learn more"
- **docs/ as canonical source**: Detailed explanations belong in `docs/`, not README.
- **Links over content**: Prefer `[Learn more](url)` over duplicating paragraphs.

**Example teaser (good):**
> Your context lives in a **separate Git repo**. This separation is a core design philosophy that enables data ownership and rollback. [Learn more](url)

**Not (too much detail for README):**
> Your context lives in a separate repo with Goals/, Responsibilities/, Preferences/. You can update Reeve without touching your context. Roll back mistakes with git revert...

**Note:** `docs/IDEAS.md` is exploratory and doesn't need to match implementation.

### Mermaid Diagram Conventions
- Use `base` theme with `classDef` for component color differentiation
- Color scheme:
  - **Core** (`#4a90a4` blue): Pulse API, Executor, Reeve, Pulse Queue MCP
  - **External** (`#6b9b76` green): Event listeners, external MCPs
  - **Database** (`#c4955a` amber): Storage components
- Prefer vertical (`TB`) layout to reduce horizontal scrolling
- Use `direction LR` inside subgraphs for horizontal arrangement

## File References

### Documentation
- [Architecture](docs/architecture/index.md) - Technical design docs
- [Deployment](docs/architecture/deployment.md) - Production systemd deployment
- [Roadmap](docs/roadmap/index.md) - Implementation phases
- [MCP Setup](docs/MCP_SETUP.md) - Claude Code integration
- [Ideas](docs/IDEAS.md) - Exploratory ideas and future concepts

### Source Code
- `src/reeve/pulse/` - Core pulse queue (models, queue, executor, daemon)
- `src/reeve/mcp/` - MCP servers (pulse_server, notification_server)
- `src/reeve/api/` - HTTP REST API (FastAPI)
- `src/reeve/integrations/` - External listeners (Telegram)
- `src/reeve/utils/` - Shared utilities (config, logging, time_parser)

See [Project Structure](docs/architecture/project-structure.md) for complete layout.

## Quick Start Commands

```bash
# Install dependencies
uv sync

# Run Alembic migrations
uv run alembic upgrade head

# Run tests
uv run pytest tests/ -v

# Run daemon
export PULSE_API_TOKEN=test-token-123
uv run python -m reeve.pulse

# Run demos
uv run python demos/phase1_database_demo.py
uv run python demos/phase2_queue_demo.py
# ... see demos/README.md for full list

# Format code
uv run black src/ && uv run isort src/

# Check types
uv run mypy src/

# Systemd service management (production)
sudo systemctl status reeve-daemon reeve-telegram
sudo journalctl -u reeve-daemon -f
```

## Production Deployment

In production, Reeve runs as two systemd services:

- **reeve-daemon**: The main Pulse Daemon (scheduler + API server)
- **reeve-telegram**: Telegram message listener that triggers pulses

```bash
# Check service status
sudo systemctl status reeve-daemon reeve-telegram

# View logs
sudo journalctl -u reeve-daemon -f    # Daemon logs
sudo journalctl -u reeve-telegram -f  # Telegram listener logs

# Restart services
sudo systemctl restart reeve-daemon reeve-telegram
```

Service files are installed in `/etc/systemd/system/`. See [Deployment Guide](docs/architecture/deployment.md) for full setup instructions including systemd configuration, monitoring, and troubleshooting.

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

## Design Principles

1. **Keep it simple**: Don't over-engineer. SQLite is sufficient.
2. **Async by default**: All I/O operations are async.
3. **Type-safe**: Use type hints and enums everywhere.
4. **Testable**: Use dependency injection, in-memory databases for tests.
5. **Documented**: Code should be self-explanatory with good docstrings.
6. **Fail gracefully**: Check preconditions, return None/False on errors.
7. **Idempotent**: Operations should be safe to retry.
8. **Validate assumptions first**: Before implementing changes to CLI/executor integration, test actual behavior manually:
   ```bash
   # Example: Check Claude Code output format before assuming streaming helps
   cd ~/reeve_desk && claude --print --output-format json "Test prompt"
   ```

## Code Style

- **Type Hints**: All functions must have complete type hints
- **Docstrings**: All public methods with Description, Args, Returns
- **Black**: line-length = 100
- **isort**: profile = "black"
- **mypy**: type checking enabled

## Git Workflow

```bash
# Phase commits should be atomic
git add -A
git commit -m "Implement Phase N: [Title]

[Detailed description of what was implemented]

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

## Task Tracking

Use GitHub Issues for tracking maintenance tasks, bugs, and feature requests:

```bash
# List open issues
gh issue list

# Create new issue
gh issue create --title "Title" --body "Description" --label "label-name"

# View issue details
gh issue view 123
```

Available labels: `code-quality`, `testing`, `documentation`, `tech-debt`, `context-engineering`, `security`

## Planning Complex Tasks

**Whenever plan mode is active**, follow the guidelines in `.claude/skills/plan-with-subagents/SKILL.md`. Plan mode implies complexity, so these principles always apply:

- Break tasks into parallelizable phases by file independence
- Use sub-agents generously (Explore, Plan, Bash, general-purpose)
- Minimize context per agent - pass only what's needed
- Commit incrementally per phase for easy rollback

See the skill file for detailed guidelines on agent type selection and execution templates.

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
- httpx: 0.27.0
- MCP: 1.25.0

---

**Last Updated**: 2026-02-03
**Current Migration**: 07ce7ae63b4a
**Test Status**: 191/191 tests PASSED
