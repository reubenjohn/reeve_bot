# Phase 4 Enhancements: Session ID Extraction

## Summary

Enhanced the Phase 4 Pulse Executor to return session IDs by leveraging Claude Code's `--json` mode. The executor now returns a Pydantic model with the session ID, enabling multi-turn pulse workflows.

## Changes Made

### 1. ExecutionResult Pydantic Model

**File**: `src/reeve/pulse/executor.py`

Created a new `ExecutionResult` Pydantic model to replace the dictionary return type:

```python
class ExecutionResult(BaseModel):
    """Result of a pulse execution."""
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool
    session_id: Optional[str]  # NEW: Extracted from JSON output
```

**Benefits**:
- Type-safe return values
- IDE autocomplete support
- Validation at runtime
- Clean API surface

### 2. JSON Mode Integration

**File**: `src/reeve/pulse/executor.py`

Updated the executor to use Claude Code's `--json` flag:

```python
# Before:
cmd = [self.hapi_command, "--print"]

# After:
cmd = [self.hapi_command, "--print", "--json"]
```

**Implementation**:
- Parses JSON output from Claude Code
- Extracts `session_id` field from the response
- Falls back to `None` if JSON parsing fails (graceful degradation)
- Logs parsing failures for debugging

### 3. Enhanced Demo 3

**File**: `demos/phase4_executor_demo.py`

Completely rewrote Demo 3 to showcase session ID extraction and resumption:

**Before**: Mock demonstration of `--resume` flag construction
**After**: Real two-step workflow:
1. Create new session and capture its `session_id`
2. Resume that session using the captured `session_id`

**Example flow**:
```python
# Step 1: Create session
result1 = await executor.execute("Remember this number: 42")
session_id = result1.session_id  # Extracted from JSON

# Step 2: Resume session
result2 = await executor.execute(
    "What number did I ask you to remember?",
    session_id=session_id  # Use captured session_id
)
# Expected output: "42" (proves session continuity)
```

### 4. Updated Tests

**File**: `tests/test_pulse_executor.py`

- Updated all 18 existing tests to use `ExecutionResult` model
- Added 2 new tests:
  - `test_session_id_extraction_from_json`: Verifies JSON parsing
  - `test_session_id_none_on_invalid_json`: Tests graceful degradation
- All tests mock JSON output with `session_id` field
- Tests verify `--json` flag is included in commands

**Test Results**: 71/71 tests PASSED (up from 69)

## Use Cases

### 1. Multi-Turn Pulse Workflows

Enable pulses to continue conversations:

```python
# Pulse 1: Research task
result1 = await executor.execute("Find the best ski resorts in Tahoe")

# Pulse 2: Follow-up (resumes context)
result2 = await executor.execute(
    "Create a comparison table of those resorts",
    session_id=result1.session_id
)
```

### 2. Background Task Tracking

Store session IDs in the database to track pulse execution:

```python
pulse = await queue.schedule_pulse(
    prompt="Daily briefing",
    priority=PulsePriority.NORMAL
)

result = await executor.execute(pulse.prompt)

# Store session_id in pulse record for resumption
await queue.update_pulse_session(pulse.id, result.session_id)
```

### 3. User Interaction Continuity

Resume sessions when user responds to a notification:

```python
# Pulse: Ask user a question via Telegram
result = await executor.execute("Should I book the flight to Tokyo?")
await notify_user(result.stdout, session_id=result.session_id)

# Later: User replies "yes"
# Resume the session to continue the booking flow
result2 = await executor.execute(
    f"User replied: {user_message}",
    session_id=stored_session_id
)
```

## Technical Details

### Command Construction

**New Session**:
```bash
hapi --print --output-format json "Your prompt here"
```

**Resume Session**:
```bash
hapi --print --output-format json --resume abc123 "Your prompt here"
```

### JSON Response Format

Claude Code's `--output-format json` mode returns:

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 2000,
  "duration_api_ms": 3482,
  "num_turns": 1,
  "result": "Response text here",
  "session_id": "abc123-session-id",
  "total_cost_usd": 0.008564,
  "usage": { /* token usage stats */ },
  "modelUsage": { /* per-model usage */ },
  "permission_denials": [],
  "uuid": "request-uuid"
}
```

The executor:
- Stores the **entire JSON** in `ExecutionResult.stdout`
- Extracts the `session_id` field to `ExecutionResult.session_id`
- Users can parse the JSON from `stdout` to access `result`, costs, and usage data

### Error Handling

- **JSON parsing fails**: `session_id = None` (graceful degradation)
- **Non-zero exit code**: Raises `RuntimeError` (existing behavior)
- **Timeout**: Raises `RuntimeError` with `session_id = None`
- **Invalid UTF-8**: Uses error replacement, `session_id = None`

## Migration Guide

### For Existing Code

**Before**:
```python
result = await executor.execute("Test prompt")
print(result["stdout"])  # Dict access
```

**After**:
```python
result = await executor.execute("Test prompt")
print(result.stdout)      # Attribute access
print(result.session_id)  # NEW: Session ID available
```

### Type Annotations

**Before**:
```python
async def run_pulse() -> Dict[str, any]:
    return await executor.execute("Test")
```

**After**:
```python
async def run_pulse() -> ExecutionResult:
    return await executor.execute("Test")
```

## Future Work

### Phase 5: Daemon Integration

The daemon will:
1. Execute pulses using `PulseExecutor`
2. Store `session_id` in the `pulses` table
3. Use `session_id` for retry/resumption logic

### Potential Database Schema Addition

```python
# In pulses table:
session_id: Optional[str]  # Session ID from last execution attempt
```

This enables:
- Resuming failed pulses in the same session
- Multi-turn pulse workflows
- User interaction continuity

## References

- [executor.py](src/reeve/pulse/executor.py) - Implementation
- [phase4_executor_demo.py](demos/phase4_executor_demo.py) - Demo
- [test_pulse_executor.py](tests/test_pulse_executor.py) - Tests
- Claude Code `--json` mode documentation

---

**Last Updated**: 2026-01-22
**Status**: Complete and tested (71/71 tests passing)
