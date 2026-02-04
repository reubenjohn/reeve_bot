# Implementation Roadmap

This document provides a step-by-step implementation guide for building the Pulse Queue system from scratch. Follow this roadmap in order, as later phases depend on earlier foundations.

**Estimated Total Effort**: 3-4 days for full implementation + testing

## Phase Overview

| Phase | Title | Status |
|-------|-------|--------|
| [Phase 1](phase-1-foundation.md) | Foundation | ✅ Completed |
| [Phase 2](phase-2-queue.md) | Queue Management | ✅ Completed |
| [Phase 3](phase-3-mcp.md) | MCP Servers | ✅ Completed |
| [Phase 4](phase-4-executor.md) | Pulse Executor | ✅ Completed |
| [Phase 5](phase-5-daemon.md) | Daemon | ✅ Completed |
| [Phase 6](phase-6-api.md) | HTTP API | ✅ Completed |
| [Phase 7](phase-7-telegram.md) | Telegram Integration | ✅ Completed |
| [Phase 8](phase-8-deployment.md) | Deployment | ✅ Completed |
| [Phase 9](phase-9-testing.md) | Integration Testing & Polish | ⏳ Pending |

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

## Success Criteria

The Pulse Queue system is complete when:

1. **Reeve can schedule its own wake-ups**
   - ✅ MCP tools work from Claude Code (Phase 3)
   - ✅ Executor can launch Hapi sessions (Phase 4)
   - ✅ Pulses execute at correct times (Phase 5)
   - ✅ Session resumption supported by executor (Phase 4)
   - ✅ End-to-end scheduling + execution (Phase 5)

2. **External events trigger Reeve**
   - ✅ Telegram messages → immediate pulses (Phase 7)
   - ✅ HTTP API accessible to other integrations (Phase 6)
   - ✅ Authentication enforced (Phase 6)

3. **Production-ready**
   - ✅ Runs as systemd service (Phase 8)
   - ✅ Automatic restarts on crash (Phase 8)
   - ✅ Logs rotated and monitored (Phase 8)
   - ✅ Database backed up daily (Phase 8)

4. **Documented**
   - ✅ Implementation guide complete
   - ✅ MCP setup guide complete (docs/MCP_SETUP.md)
   - ✅ Deployment guide complete (Phase 8)
   - ✅ Troubleshooting guide complete (Phase 8)
   - ✅ Code well-commented

5. **Tested**
   - ✅ Unit tests for queue, MCP, and executor components (191/191 tests passing)
   - ⏳ Integration tests for full flows (Phase 9)
   - ⏳ Manual testing completed (Phase 9)
   - ⏳ Performance acceptable (Phase 9)

## Demo Scripts

All demo scripts are in the `demos/` directory:

| Script | Description |
|--------|-------------|
| `phase1_database_demo.py` | Database schema and model creation |
| `phase2_queue_demo.py` | Queue operations (schedule, query, retry) |
| `phase3_mcp_demo.py` | MCP tools integration |
| `phase4_executor_demo.py` | Pulse execution with Hapi |
| `phase5_daemon_demo.py` | Daemon orchestration |
| `phase6_api_demo.py` | HTTP API endpoints |
| `phase7_telegram_demo.py` | Telegram bot integration |
| `phase8_deployment_demo.sh` | Systemd deployment |

## Quick Start

```bash
# Install dependencies
uv sync

# Run Alembic migrations
uv run alembic upgrade head

# Run tests
uv run pytest tests/ -v

# Run daemon (Phase 5+)
uv run python -m reeve.pulse
```

## Code Quality Standards

- **Type hints**: All functions fully typed
- **Docstrings**: All public APIs documented
- **Error handling**: Graceful failures with logging
- **Testing**: Aim for >80% coverage
- **Formatting**: Use `black` and `isort`
