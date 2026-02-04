"""
Reusable JSONL fixtures for testing hapi stream parsing.

This module provides test data for the HapiStreamParser, including individual
events and stream builders for common test scenarios.

Usage:
    from tests.fixtures.hapi_streams import INIT_EVENT, success_stream, error_stream

    def test_something():
        result = parser.parse_all(success_stream())
        assert result.session_id == "test-session-123"
"""

# ============================================================================
# Individual Events (raw JSON strings)
# ============================================================================

# System init event - first event in any stream, provides session_id
INIT_EVENT = (
    '{"type":"system","subtype":"init","session_id":"test-session-123",'
    '"tools":["Read","Write","Bash","Glob","Grep"]}'
)

# Assistant event with tool_use block
TOOL_USE_EVENT = (
    '{"type":"assistant","message":{"content":[{"type":"tool_use",'
    '"id":"tu_1","name":"Bash","input":{"command":"date"}}]}}'
)

# User event with tool_result block
TOOL_RESULT_EVENT = (
    '{"type":"user","message":{"content":[{"type":"tool_result",'
    '"tool_use_id":"tu_1","content":"Wed Feb 4 09:00:00 PST 2026"}]}}'
)

# Successful result event
SUCCESS_RESULT = (
    '{"type":"result","subtype":"success","session_id":"test-session-123",' '"is_error":false}'
)

# Error result event (actual hapi format uses "errors" array, not "error" object)
ERROR_RESULT = (
    '{"type":"result","subtype":"error_during_execution","is_error":true,'
    '"errors":["Error: OAuth token expired"]}'
)

# Assistant event with text response (no tool use)
TEXT_RESPONSE_EVENT = (
    '{"type":"assistant","message":{"content":[{"type":"text",'
    '"text":"I completed the task successfully."}]}}'
)


# ============================================================================
# Stream Builders
# ============================================================================


def success_stream(session_id: str = "test-session-123", with_tools: bool = True) -> str:
    """
    Build a complete success stream.

    Args:
        session_id: Session ID to use in init and result events
        with_tools: Whether to include tool_use and tool_result events

    Returns:
        JSONL string representing a successful hapi execution
    """
    events = [INIT_EVENT.replace("test-session-123", session_id)]
    if with_tools:
        events.extend([TOOL_USE_EVENT, TOOL_RESULT_EVENT])
    events.append(SUCCESS_RESULT.replace("test-session-123", session_id))
    return "\n".join(events)


def error_stream(
    session_id: str = "test-session-123", error_msg: str = "OAuth token expired"
) -> str:
    """
    Build an error stream.

    Note: The session_id is still available from the init event, even when
    execution fails. This is critical for tracking failed sessions.

    Args:
        session_id: Session ID to use in init event
        error_msg: Error message to include in the result event (without "Error: " prefix)

    Returns:
        JSONL string representing a failed hapi execution
    """
    # Build a custom error result with the specified message
    # The errors array format is ["Error: <message>"]
    error_result = (
        '{"type":"result","subtype":"error_during_execution","is_error":true,'
        f'"errors":["Error: {error_msg}"]}}'
    )
    return "\n".join(
        [
            INIT_EVENT.replace("test-session-123", session_id),
            error_result,
        ]
    )


def prefixed_stream(prefix: str = "Starting HAPI...\n") -> str:
    """
    Stream with non-JSON prefix text (realistic hapi output).

    Real hapi output often includes terminal escape sequences and status
    messages before the JSON events begin.

    Args:
        prefix: Non-JSON text to prepend to the stream

    Returns:
        JSONL string with non-JSON prefix followed by a success stream
    """
    return prefix + success_stream()


def multi_tool_stream(session_id: str = "test-session-123") -> str:
    """
    Stream with multiple tool calls.

    Simulates a hapi session that makes multiple tool calls during execution.

    Args:
        session_id: Session ID to use throughout the stream

    Returns:
        JSONL string with two tool call cycles
    """
    tool_use_2 = (
        '{"type":"assistant","message":{"content":[{"type":"tool_use",'
        '"id":"tu_2","name":"Read","input":{"path":"/tmp/test"}}]}}'
    )
    tool_result_2 = (
        '{"type":"user","message":{"content":[{"type":"tool_result",'
        '"tool_use_id":"tu_2","content":"file contents"}]}}'
    )
    return "\n".join(
        [
            INIT_EVENT.replace("test-session-123", session_id),
            TOOL_USE_EVENT,
            TOOL_RESULT_EVENT,
            tool_use_2,
            tool_result_2,
            SUCCESS_RESULT.replace("test-session-123", session_id),
        ]
    )


def multi_tool_single_event_stream(session_id: str = "test-session-123") -> str:
    """
    Stream with multiple tool uses in a single assistant event.

    Claude can make multiple tool calls in parallel, which results in a
    single assistant event containing multiple tool_use blocks.

    Args:
        session_id: Session ID to use throughout the stream

    Returns:
        JSONL string with an assistant event containing two tool calls
    """
    multi_tool_use = (
        '{"type":"assistant","message":{"content":['
        '{"type":"tool_use","id":"tu_1","name":"Bash","input":{"command":"pwd"}},'
        '{"type":"tool_use","id":"tu_2","name":"Glob","input":{"pattern":"*.py"}}'
        "]}}"
    )
    multi_tool_result = (
        '{"type":"user","message":{"content":['
        '{"type":"tool_result","tool_use_id":"tu_1","content":"/home/user"},'
        '{"type":"tool_result","tool_use_id":"tu_2","content":"main.py\\ntest.py"}'
        "]}}"
    )
    return "\n".join(
        [
            INIT_EVENT.replace("test-session-123", session_id),
            multi_tool_use,
            multi_tool_result,
            SUCCESS_RESULT.replace("test-session-123", session_id),
        ]
    )


def text_only_stream(session_id: str = "test-session-123") -> str:
    """
    Stream with only text response (no tool calls).

    Some hapi sessions complete without any tool calls, returning only
    a text response.

    Args:
        session_id: Session ID to use throughout the stream

    Returns:
        JSONL string with text response but no tool usage
    """
    return "\n".join(
        [
            INIT_EVENT.replace("test-session-123", session_id),
            TEXT_RESPONSE_EVENT,
            SUCCESS_RESULT.replace("test-session-123", session_id),
        ]
    )


def realistic_terminal_prefix_stream() -> str:
    """
    Stream with realistic terminal prefix (escape codes, status messages).

    Real hapi output includes terminal escape sequences for directory
    changes and status messages before JSON events.

    Returns:
        JSONL string with realistic terminal prefix
    """
    prefix = (
        ']9;9;"\\\\wsl.localhost\\Ubuntu\\home\\user\\desk"\n'
        "Starting HAPI hub in background...\n"
        "HAPI hub started\n"
    )
    return prefix + success_stream()


def blank_lines_stream(session_id: str = "test-session-123") -> str:
    """
    Stream with blank lines between events.

    Tests that parser handles blank lines correctly.

    Args:
        session_id: Session ID to use throughout the stream

    Returns:
        JSONL string with blank lines interspersed
    """
    return "\n".join(
        [
            "",
            INIT_EVENT.replace("test-session-123", session_id),
            "",
            "   ",  # whitespace-only line
            TOOL_USE_EVENT,
            "",
            TOOL_RESULT_EVENT,
            SUCCESS_RESULT.replace("test-session-123", session_id),
            "",
        ]
    )
