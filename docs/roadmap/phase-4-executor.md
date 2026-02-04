← [Back to Roadmap Index](index.md)

# Phase 4: Pulse Executor ✅ COMPLETED

**Goal**: Execute pulses by launching Hapi sessions.

**Status**: ✅ Completed on 2026-01-19

## Tasks

1. **PulseExecutor Class** (`src/reeve/pulse/executor.py`) ✅
   - Implemented `execute()` method with full async support
   - Launches Hapi subprocess with correct working directory
   - Handles sticky notes (appended to prompt, not prepended)
   - Captures stdout/stderr with UTF-8 error handling
   - Reports success/failure with detailed error messages
   - Includes timeout handling with configurable defaults
   - See [Daemon & API](../architecture/daemon-api.md)

2. **Testing** ✅
   - 18 comprehensive unit tests with mocked Hapi command
   - Tests prompt building with and without sticky notes
   - Tests error handling (Hapi crash, timeout, command not found, invalid paths)
   - Tests configuration (path expansion, custom timeout)
   - Integration-style tests for full execution flow

## Deliverables

- ✅ Working executor that can launch Hapi with full error handling
- ✅ 18 comprehensive tests with mocked Hapi (all passing)

## Validation

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

## Demo

### With Real Hapi

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

### Mock Mode (if Hapi not available)

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

**Previous**: [Phase 3: MCP Servers](phase-3-mcp.md)

**Next**: [Phase 5: Daemon](phase-5-daemon.md)
