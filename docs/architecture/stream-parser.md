# Stream Parser

## Overview

The `HapiStreamParser` parses JSONL output from hapi's `--output-format stream-json --verbose` mode. It extracts session information, tool usage metrics, and error details from the streaming output.

**Why it matters**: The parser enables better error diagnostics by extracting the `session_id` even when execution fails. This allows operators to investigate failed pulses in the Claude Code session history.

## Usage

```python
from reeve.pulse.stream_parser import HapiStreamParser

parser = HapiStreamParser()
result = parser.parse_all(stdout)

print(f"Session: {result.session_id}")
print(f"Error: {result.error_message}")
print(f"Tool calls: {result.tool_call_count}")
```

### Incremental Parsing

For streaming scenarios, parse lines as they arrive:

```python
parser = HapiStreamParser()
for line in stdout.split("\n"):
    event = parser.parse_line(line)
    if event:
        print(f"Event: {event.type}/{event.subtype}")
```

## Event Types

| Type | Subtype | Description | Key Fields |
|------|---------|-------------|------------|
| `system` | `init` | Session initialization | `session_id` |
| `assistant` | - | Claude's response | `tool_uses[]` |
| `user` | - | Tool results | `tool_results[]` |
| `result` | - | Final outcome | `is_error`, `error_message` |

## Data Models

### StreamParseResult

Aggregated result from parsing a complete stream.

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `str | None` | Session ID from init event (available early) |
| `is_error` | `bool` | Whether the stream ended with an error |
| `error_message` | `str | None` | Error message from result event |
| `tool_call_count` | `int` | Total number of tool calls made |
| `events` | `list[HapiStreamEvent]` | All parsed events |

### HapiStreamEvent

A single parsed event from the JSONL stream.

| Field | Type | Description |
|-------|------|-------------|
| `type` | `HapiEventType` | Event category |
| `subtype` | `str | None` | Event subtype (e.g., "init") |
| `session_id` | `str | None` | Session identifier if present |
| `is_error` | `bool` | Whether this is an error event |
| `error_message` | `str | None` | Error message if applicable |
| `tool_uses` | `list[ToolUseInfo]` | Tool calls in assistant events |
| `tool_results` | `list[ToolResultInfo]` | Results in user events |

### ToolUseInfo

Information about a tool call.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier for the tool use |
| `name` | `str` | Name of the tool being called |

### ToolResultInfo

Information about a tool result.

| Field | Type | Description |
|-------|------|-------------|
| `tool_use_id` | `str` | ID of the corresponding tool_use |

## Integration with Executor

The `PulseExecutor` uses the stream parser to extract diagnostics from hapi output:

```python
# In executor.py
class PulseExecutor:
    def __init__(self, ...):
        self.stream_parser = HapiStreamParser()

    async def execute(self, prompt: str, ...) -> ExecutionResult:
        # Run hapi with stream-json output
        process = await asyncio.create_subprocess_exec(
            hapi_command,
            "--output-format", "stream-json",
            "--verbose",
            ...
        )
        stdout, stderr = await process.communicate()

        # Parse output to extract session_id and error details
        parse_result = self.stream_parser.parse_all(stdout.decode())

        # Session ID is available even if execution failed!
        return ExecutionResult(
            success=process.returncode == 0,
            session_id=parse_result.session_id,
            error_message=parse_result.error_message,
            tool_call_count=parse_result.tool_call_count,
        )
```

The parser handles edge cases like:
- Terminal escape sequences prepended to JSON lines (WSL, some terminals)
- Non-JSON status messages interspersed in output
- Missing or malformed events
