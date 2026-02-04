# Architecture Documentation

This directory contains the technical architecture documentation for the Reeve Bot pulse queue system.

## Documents

| Document | Description | When to Read |
|----------|-------------|--------------|
| [Project Structure](project-structure.md) | Directory layout and file organization | Starting development, understanding codebase |
| [Pulse Queue Design](pulse-queue.md) | Database schema, models, queue logic | Working on pulse scheduling or storage |
| [MCP Integration](mcp-integration.md) | MCP server specifications | Building or modifying MCP tools |
| [Daemon & API](daemon-api.md) | Daemon orchestration and HTTP API | Working on execution or external triggers |
| [Deployment](deployment.md) | Production deployment guide | Deploying to production |

## Quick Reference

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Reeve Bot                            │
├─────────────────────────────────────────────────────────────┤
│  MCP Servers          │  HTTP API        │  Integrations    │
│  ├─ Pulse Queue       │  ├─ /schedule    │  └─ Telegram     │
│  └─ Telegram Notifier │  ├─ /upcoming    │                  │
│                       │  └─ /health      │                  │
├─────────────────────────────────────────────────────────────┤
│                     Pulse Daemon                            │
│  ├─ Scheduler Loop (1s polling)                             │
│  ├─ Executor (Hapi subprocess)                              │
│  └─ Retry Logic (exponential backoff)                       │
├─────────────────────────────────────────────────────────────┤
│                     Pulse Queue                             │
│  └─ SQLite + SQLAlchemy (async)                             │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Pulse Creation**: MCP tool / HTTP API / Telegram → PulseQueue → SQLite
2. **Pulse Execution**: Daemon polls → PulseExecutor → Hapi subprocess
3. **Notifications**: Hapi session → Telegram Notifier MCP → User

## See Also

- [Implementation Roadmap](../roadmap/index.md) - Phase-by-phase implementation details
- [MCP Setup Guide](../MCP_SETUP.md) - Configuring MCP servers for Claude Code
