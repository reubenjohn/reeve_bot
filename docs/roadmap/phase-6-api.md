← [Back to Roadmap Index](index.md)

# Phase 6: HTTP API ✅ COMPLETED

**Goal**: Allow external systems to trigger pulses.

**Status**: ✅ Completed

## Tasks

1. **FastAPI Server** (`src/reeve/api/server.py`) ✅
   - Implemented `create_app()` factory function (295 lines)
   - Implemented endpoints:
     - `POST /api/pulse/schedule` - Create pulse ✅
     - `GET /api/pulse/upcoming` - List pulses ✅
     - `GET /api/health` - Health check (no auth) ✅
     - `GET /api/status` - Daemon status ✅
   - Bearer token authentication with custom dependency ✅
   - Pydantic models for request/response validation ✅
   - Flexible time parsing via `parse_time_string()` utility ✅
   - See [03_DAEMON_AND_API.md](../03_DAEMON_AND_API.md)

2. **Integrate with Daemon** ✅
   - Integrated API server in `__main__.py` ✅
   - API runs concurrently with scheduler using asyncio ✅
   - Shared PulseQueue instance for database access ✅
   - Graceful shutdown handling for both components ✅

3. **Time Parsing Utility** (`src/reeve/utils/time_parser.py`) ✅
   - Extracted shared time parsing logic (79 lines) ✅
   - Used by both MCP server and API server ✅
   - Supports ISO 8601, relative times, and keywords ✅

4. **Testing** ✅
   - 8 comprehensive unit tests (`tests/test_api_server.py`) ✅
   - All endpoint tests (schedule, list, health, status) ✅
   - Authentication tests (valid, invalid, missing) ✅
   - All tests pass: 154/154 ✅

5. **Demo Script** (`demos/phase6_api_demo.py`) ✅
   - 8 comprehensive demo functions (418 lines) ✅
   - Health check, authentication, schedule (now/relative/ISO), list, status, cleanup ✅
   - Uses httpx for async HTTP requests ✅
   - Interactive flow with daemon running check ✅

## Deliverables

- ✅ Working REST API with 4 endpoints
- ✅ API runs alongside daemon concurrently
- ✅ Bearer token authentication working
- ✅ Comprehensive test suite and demo script

## Validation

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

## Demo

### Prerequisites

```bash
# Set API token in .env file
echo "PULSE_API_TOKEN=your_secret_token_here" >> .env
```

### Step 1: Start daemon with API (Terminal 1)

```bash
uv run python -m reeve.pulse

# Expected output:
# 2026-01-19 10:30:00 | INFO | Starting Pulse Daemon...
# 2026-01-19 10:30:00 | INFO | Starting HTTP API on port 8765...
# 2026-01-19 10:30:00 | INFO | API docs available at http://localhost:8765/docs
# 2026-01-19 10:30:00 | INFO | Scheduler loop started
```

### Step 2: Run demo script (Terminal 2)

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

### Step 3: Manual curl testing

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

### Step 4: Explore API docs

```bash
# Open browser to http://localhost:8765/docs
# FastAPI provides interactive Swagger UI for testing all endpoints
```

---

**Previous**: [Phase 5: Daemon](phase-5-daemon.md)

**Next**: [Phase 7: Telegram Integration](phase-7-telegram.md)
