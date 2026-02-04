← [Back to Roadmap Index](index.md)

# Phase 3: MCP Servers ✅ COMPLETED

**Goal**: Expose queue functionality to Reeve via MCP tools.

**Status**: ✅ Completed on 2026-01-19

## Tasks

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

## Deliverables

- ✅ Two working MCP servers built with FastMCP
- ✅ Type-safe tool definitions with Pydantic validation
- ✅ Comprehensive documentation for Claude and users
- ✅ 18 comprehensive tests split across 3 files with mocking and integration coverage
- ✅ Example configuration and setup guide

## Validation

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

## Demo

### Step 1: Configure MCP servers (one-time setup)

```bash
# Copy example config
cp mcp_config.json.example ~/.config/claude-code/mcp_config.json

# Edit to add Telegram credentials (optional for telegram-notifier)
# TELEGRAM_BOT_TOKEN: Get from @BotFather on Telegram
# TELEGRAM_CHAT_ID: Your Telegram user ID
```

### Step 2a: Demo via Interactive Script

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

### Step 2b: Demo via Claude Code (after MCP configuration)

In a Claude Code session, use the MCP tools directly:

1. Schedule a pulse:
   ```
   schedule_pulse(
     scheduled_at="in 30 minutes",
     prompt="Test notification from MCP",
     priority="high"
   )
   ```

2. List upcoming pulses:
   ```
   list_upcoming_pulses(limit=10)
   ```

3. Send a notification:
   ```
   send_notification(
     message="Testing Telegram integration!",
     priority="normal"
   )
   ```

4. Cancel a pulse:
   ```
   cancel_pulse(pulse_id=1)
   ```

---

**Previous**: [Phase 2: Queue Management](phase-2-queue.md)

**Next**: [Phase 4: Pulse Executor](phase-4-executor.md)
