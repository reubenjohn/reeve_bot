# Reeve Bot Demos

This directory contains interactive demonstration scripts for each phase of the Pulse Queue system. These demos show real-world functionality using actual APIs and services.

## Purpose

The demos serve multiple purposes:
- **Verify functionality** with real-world data and APIs
- **Provide examples** for users to understand what's possible
- **Enable self-testing** by Claude before handing off to users
- **Document usage** through concrete, runnable examples

## Available Demos

### Phase 1: Database Schema
```bash
uv run python demos/phase1_database_demo.py
```

Demonstrates:
- Database initialization
- Pulse model creation
- Enum integration
- Basic CRUD operations

### Phase 2: Queue Operations
```bash
uv run python demos/phase2_queue_demo.py
```

Demonstrates:
- Scheduling pulses with different priorities
- Priority-based ordering (CRITICAL → HIGH → NORMAL → LOW → DEFERRED)
- State transitions (PENDING → PROCESSING → COMPLETED/FAILED)
- Retry logic with exponential backoff
- Cancelling pulses

### Phase 3: MCP Integration
```bash
uv run python demos/phase3_mcp_demo.py
```

Demonstrates:
- Flexible time parsing (ISO 8601, relative times, keywords)
- Scheduling pulses with priorities, tags, and sticky notes
- Listing and formatting upcoming pulses
- Rescheduling and cancelling pulses
- Telegram notifications (if configured)

**Note:** To test Telegram notifications, set:
```bash
export TELEGRAM_BOT_TOKEN=your_bot_token
export TELEGRAM_CHAT_ID=your_chat_id
```

### Phase 4: Pulse Executor
```bash
# With real Hapi (if installed)
uv run python demos/phase4_executor_demo.py

# Mock mode (no Hapi required)
uv run python demos/phase4_executor_demo.py --mock
```

Demonstrates:
- Prompt building with and without sticky notes
- Hapi subprocess execution
- Timeout handling
- Error handling

### Phase 5: Pulse Daemon
```bash
# With real Hapi (if installed)
uv run python demos/phase5_daemon_demo.py

# Mock mode (no Hapi required)
uv run python demos/phase5_daemon_demo.py --mock
```

Demonstrates:
- Daemon startup and initialization
- Scheduler loop (polls every 1 second)
- Priority-based pulse execution
- Concurrent pulse execution
- Sticky notes integration
- Graceful shutdown (SIGINT/SIGTERM)
- Status monitoring in real-time

**Note:** The daemon will run for ~15 seconds, execute all scheduled pulses, then shutdown gracefully.

### Phase 6: HTTP API
```bash
# Set API token (required)
export PULSE_API_TOKEN=test-token

# Run demo (requires daemon to be running)
uv run python demos/phase6_api_demo.py
```

Demonstrates:
- Health check endpoint (GET /api/health)
- Bearer token authentication
- Schedule pulses via HTTP (now, relative, ISO 8601)
- List upcoming pulses (GET /api/pulse/upcoming)
- Daemon status (GET /api/status)
- Request/response formatting with httpx

**Note:** Start the daemon first in another terminal:
```bash
export PULSE_API_TOKEN=test-token
uv run python -m reeve.pulse
```

### Phase 7: Telegram Integration
```bash
uv run python demos/phase7_telegram_demo.py
```

Demonstrates:
- Mock Telegram API server (getMe, getUpdates endpoints)
- Mock Pulse API server (POST /api/pulse/schedule)
- Incoming message simulation (Update JSON format)
- Listener polling flow (long polling with offset)
- Pulse triggering via HTTP API (with auth, priority, tags)
- Offset persistence (atomic write to disk)

**Key technical details:**
- Long polling (100s timeout) for efficiency
- Chat ID filtering (only authorized user)
- Priority: `CRITICAL` for user messages
- Source tracking: `telegram`
- Tags: `["telegram", "user_message"]`
- Offset file: `~/.reeve/telegram_offset.txt`
- Exponential backoff on errors (up to 5 minutes)
- Graceful shutdown via SIGTERM/SIGINT

**Real-world flow:**
```
User sends message → Telegram API → Listener polls → Filters by chat_id →
Builds prompt → POSTs to Pulse API → Pulse created → Reeve wakes up
```

**To run with real Telegram:**
1. Create bot via @BotFather
2. Get your chat ID (send message to bot, check `/getUpdates`)
3. Configure environment:
   ```bash
   export TELEGRAM_BOT_TOKEN=your_bot_token
   export TELEGRAM_CHAT_ID=your_chat_id
   export PULSE_API_TOKEN=your_api_token
   ```
4. Run listener: `uv run python -m reeve.integrations.telegram`

### Phase 8: Future Demos

Demo scripts for Phase 8 (Production Deployment) will be created as that phase is implemented.

## Running All Demos

To run all completed phase demos in sequence:

```bash
# Phases 1-3 (no daemon required)
for demo in demos/phase{1,2,3}_*.py; do
    echo "=== Running $demo ==="
    uv run python "$demo"
    echo ""
done

# Phases 4-5 (mock mode, no daemon required)
for demo in demos/phase{4,5}_*.py; do
    echo "=== Running $demo ==="
    uv run python "$demo" --mock
    echo ""
done

# Phase 6 (requires daemon running in another terminal)
# Start daemon: export PULSE_API_TOKEN=test-token && uv run python -m reeve.pulse
# Then run: export PULSE_API_TOKEN=test-token && uv run python demos/phase6_api_demo.py

# Phase 7 (mock mode, no daemon or Telegram credentials required)
uv run python demos/phase7_telegram_demo.py
```

## Demo Data Cleanup

All demos:
- Use the production database (`~/.reeve/pulse_queue.db`)
- Create test data with clear labels (prefixed with "DEMO:")
- Clean up after themselves automatically
- Are idempotent (safe to run multiple times)

## Self-Testing Protocol (for Claude)

After implementing each phase, Claude should:

1. **Run automated tests first:**
   ```bash
   uv run pytest tests/ -v -k "phase_N"
   ```

2. **Run the demo script:**
   ```bash
   uv run python demos/phaseN_*_demo.py
   ```

3. **For MCP phases (3+), use MCP tools directly** in the Claude Code session

4. **Report results to user** with observations and next steps

## Real-World API Usage

| Phase | Real APIs Used |
|-------|----------------|
| 1-2 | SQLite database (local) |
| 3 | SQLite + Telegram Bot API (optional) |
| 4 | SQLite + Hapi CLI (if available, else mock) |
| 5 | SQLite + Hapi CLI + Daemon (background process) |
| 6 | SQLite + Hapi CLI + HTTP REST API |
| 7 | SQLite + Hapi CLI + HTTP API + Telegram Bot API |
| 8 | All of the above + systemd + cron |

## Demo Output Format

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

## Troubleshooting

### Database locked errors
If you get "database is locked" errors, make sure no other processes (daemon, tests) are accessing the database:
```bash
pkill -f "reeve.pulse"
```

### Telegram API errors
If Telegram notifications fail:
1. Verify credentials are set correctly
2. Check bot token is valid: `curl https://api.telegram.org/bot<TOKEN>/getMe`
3. Verify chat ID is correct

### Hapi not found
Phase 4 demo will automatically fall back to mock mode if Hapi is not found. To use real Hapi:
1. Install Hapi: Follow setup instructions
2. Ensure it's in your PATH: `which hapi`

## Contributing

When adding new demos:
1. Follow the existing naming convention: `phaseN_description_demo.py`
2. Include comprehensive docstrings
3. Use emoji indicators (✓, ❌, ⚠, etc.)
4. Clean up demo data in a `finally` block
5. Provide clear output with separators
6. Update this README with usage instructions
