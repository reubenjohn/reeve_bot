"""
Tests for the HapiStreamParser module.

Tests cover:
- Line parsing: Individual event types (system, assistant, user, result)
- Full stream parsing: Success and error cases
- Edge cases: Blank lines, non-JSON content, malformed JSON
- Tool extraction: Single and multiple tool_use blocks
- Enum behavior: String conversion and value access
"""

import pytest

from reeve.pulse.stream_parser import (
    HapiEventType,
    HapiStreamEvent,
    HapiStreamParser,
    StreamParseResult,
    ToolResultInfo,
    ToolUseInfo,
)
from tests.fixtures.hapi_streams import (
    ERROR_RESULT,
    INIT_EVENT,
    SUCCESS_RESULT,
    TEXT_RESPONSE_EVENT,
    TOOL_RESULT_EVENT,
    TOOL_USE_EVENT,
    blank_lines_stream,
    error_stream,
    multi_tool_single_event_stream,
    multi_tool_stream,
    prefixed_stream,
    realistic_terminal_prefix_stream,
    success_stream,
    text_only_stream,
)

# ============================================================================
# parse_line() Tests - Individual Event Types
# ============================================================================


class TestParseLine:
    """Tests for parse_line() method."""

    def test_parse_init_event(self):
        """Test parsing system/init event extracts session_id."""
        parser = HapiStreamParser()
        event = parser.parse_line(INIT_EVENT)

        assert event is not None
        assert event.type == HapiEventType.SYSTEM
        assert event.subtype == "init"
        assert event.session_id == "test-session-123"
        assert event.is_error is False
        assert event.error_message is None

    def test_parse_tool_use_event(self):
        """Test parsing assistant event extracts tool_use blocks."""
        parser = HapiStreamParser()
        event = parser.parse_line(TOOL_USE_EVENT)

        assert event is not None
        assert event.type == HapiEventType.ASSISTANT
        assert len(event.tool_uses) == 1
        assert event.tool_uses[0].name == "Bash"
        assert event.tool_uses[0].id == "tu_1"
        assert len(event.tool_results) == 0

    def test_parse_tool_result_event(self):
        """Test parsing user event extracts tool_result blocks."""
        parser = HapiStreamParser()
        event = parser.parse_line(TOOL_RESULT_EVENT)

        assert event is not None
        assert event.type == HapiEventType.USER
        assert len(event.tool_results) == 1
        assert event.tool_results[0].tool_use_id == "tu_1"
        assert len(event.tool_uses) == 0

    def test_parse_success_result(self):
        """Test parsing successful result event."""
        parser = HapiStreamParser()
        event = parser.parse_line(SUCCESS_RESULT)

        assert event is not None
        assert event.type == HapiEventType.RESULT
        assert event.subtype == "success"
        assert event.is_error is False
        assert event.session_id == "test-session-123"
        assert event.error_message is None

    def test_parse_error_result(self):
        """Test parsing error result event extracts error message."""
        parser = HapiStreamParser()
        event = parser.parse_line(ERROR_RESULT)

        assert event is not None
        assert event.type == HapiEventType.RESULT
        assert event.subtype == "error_during_execution"
        assert event.is_error is True
        assert event.error_message == "Error: OAuth token expired"

    def test_parse_text_response_event(self):
        """Test parsing assistant event with text content (no tool_use)."""
        parser = HapiStreamParser()
        event = parser.parse_line(TEXT_RESPONSE_EVENT)

        assert event is not None
        assert event.type == HapiEventType.ASSISTANT
        assert len(event.tool_uses) == 0
        assert len(event.tool_results) == 0

    def test_parse_blank_line_returns_none(self):
        """Test that blank/whitespace lines return None."""
        parser = HapiStreamParser()
        assert parser.parse_line("") is None
        assert parser.parse_line("   ") is None
        assert parser.parse_line("\n") is None
        assert parser.parse_line("\t") is None
        assert parser.parse_line("  \t  \n  ") is None

    def test_parse_non_json_returns_none(self):
        """Test that non-JSON lines (status messages) return None."""
        parser = HapiStreamParser()
        assert parser.parse_line("Starting HAPI...") is None
        assert parser.parse_line("Loading config") is None
        assert parser.parse_line("HAPI hub started") is None
        assert parser.parse_line("Waiting for response...") is None

    def test_parse_malformed_json_returns_none(self):
        """Test that malformed JSON lines return None."""
        parser = HapiStreamParser()
        assert parser.parse_line("{invalid json}") is None
        assert parser.parse_line('{"type":') is None
        assert parser.parse_line('{"incomplete": true') is None

    def test_parse_json_array_returns_none(self):
        """Test that JSON arrays (not objects) return None gracefully.

        The parser handles arrays by returning None since they don't have
        a .get() method like dicts. In production, hapi only emits JSON
        objects, so this edge case is acceptable.
        """
        parser = HapiStreamParser()
        # JSON arrays are valid JSON but not valid hapi events
        assert parser.parse_line("[1, 2, 3]") is None

    def test_parse_json_without_type_returns_none(self):
        """Test that JSON without type field returns None."""
        parser = HapiStreamParser()
        assert parser.parse_line('{"session_id": "test"}') is None
        assert parser.parse_line('{"data": "something"}') is None

    def test_parse_terminal_escape_sequence_returns_none(self):
        """Test that terminal escape sequences return None."""
        parser = HapiStreamParser()
        assert parser.parse_line(']9;9;"\\\\wsl.localhost\\Ubuntu\\home"') is None


# ============================================================================
# parse_all() Tests - Complete Stream Parsing
# ============================================================================


class TestParseAll:
    """Tests for parse_all() method."""

    def test_success_stream(self):
        """Test parsing a complete success stream."""
        parser = HapiStreamParser()
        result = parser.parse_all(success_stream())

        assert result.session_id == "test-session-123"
        assert result.is_error is False
        assert result.error_message is None
        assert result.tool_call_count == 1
        assert len(result.events) == 4  # init, tool_use, tool_result, result

    def test_success_stream_without_tools(self):
        """Test parsing success stream with no tool calls."""
        parser = HapiStreamParser()
        result = parser.parse_all(success_stream(with_tools=False))

        assert result.session_id == "test-session-123"
        assert result.is_error is False
        assert result.tool_call_count == 0
        assert len(result.events) == 2  # init, result

    def test_error_stream_preserves_session_id(self):
        """Critical: session_id must be extractable even on failures."""
        parser = HapiStreamParser()
        result = parser.parse_all(error_stream())

        # Session ID from init event should be captured
        assert result.session_id == "test-session-123"
        assert result.is_error is True
        assert result.error_message == "Error: OAuth token expired"

    def test_custom_session_id(self):
        """Test that custom session_id is propagated correctly."""
        parser = HapiStreamParser()
        result = parser.parse_all(success_stream(session_id="custom-id-456"))

        assert result.session_id == "custom-id-456"

    def test_custom_error_message(self):
        """Test that custom error message is propagated correctly."""
        parser = HapiStreamParser()
        result = parser.parse_all(error_stream(error_msg="API rate limited"))

        assert result.is_error is True
        assert result.error_message == "Error: API rate limited"

    def test_prefixed_stream(self):
        """Parser handles non-JSON prefix text (common in real hapi output)."""
        parser = HapiStreamParser()
        result = parser.parse_all(prefixed_stream())

        assert result.session_id == "test-session-123"
        assert result.is_error is False
        assert result.tool_call_count == 1

    def test_realistic_terminal_prefix_stream(self):
        """Parser handles realistic terminal escape sequences."""
        parser = HapiStreamParser()
        result = parser.parse_all(realistic_terminal_prefix_stream())

        assert result.session_id == "test-session-123"
        assert result.is_error is False

    def test_multi_tool_stream(self):
        """Test parsing stream with multiple sequential tool calls."""
        parser = HapiStreamParser()
        result = parser.parse_all(multi_tool_stream())

        assert result.tool_call_count == 2
        assert result.session_id == "test-session-123"
        assert result.is_error is False

    def test_multi_tool_single_event_stream(self):
        """Test parsing stream with multiple tool calls in single event."""
        parser = HapiStreamParser()
        result = parser.parse_all(multi_tool_single_event_stream())

        # Multiple tool calls in single event should count separately
        assert result.tool_call_count == 2
        assert result.session_id == "test-session-123"

    def test_text_only_stream(self):
        """Test parsing stream with only text response (no tools)."""
        parser = HapiStreamParser()
        result = parser.parse_all(text_only_stream())

        assert result.session_id == "test-session-123"
        assert result.is_error is False
        assert result.tool_call_count == 0

    def test_blank_lines_stream(self):
        """Test that blank lines in stream are handled correctly."""
        parser = HapiStreamParser()
        result = parser.parse_all(blank_lines_stream())

        assert result.session_id == "test-session-123"
        assert result.tool_call_count == 1
        # Only actual events are counted, not blank lines
        assert len(result.events) == 4


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_reset_clears_state(self):
        """Test that reset() clears all parser state."""
        parser = HapiStreamParser()

        # Parse a stream
        parser.parse_all(success_stream())

        # Verify state is populated
        assert parser._session_id == "test-session-123"
        assert parser._tool_call_count == 1
        assert len(parser._events) == 4

        # Reset
        parser.reset()

        # Verify state is cleared
        assert parser._session_id is None
        assert parser._tool_call_count == 0
        assert len(parser._events) == 0
        assert parser._is_error is False
        assert parser._error_message is None

    def test_parse_all_auto_resets(self):
        """Test that parse_all() automatically resets state."""
        parser = HapiStreamParser()

        # Parse first stream
        result1 = parser.parse_all(success_stream())
        assert result1.session_id == "test-session-123"

        # Parse second stream - should have fresh state
        result2 = parser.parse_all(error_stream(session_id="new-session"))
        assert result2.session_id == "new-session"
        assert result2.is_error is True
        # Should not have events from first stream
        assert len(result2.events) == 2

    def test_empty_stdout(self):
        """Test parsing empty stdout."""
        parser = HapiStreamParser()
        result = parser.parse_all("")

        assert result.session_id is None
        assert result.is_error is False
        assert result.tool_call_count == 0
        assert len(result.events) == 0

    def test_only_non_json_content(self):
        """Test parsing stdout with only non-JSON content."""
        parser = HapiStreamParser()
        result = parser.parse_all("Loading...\nStarting...\nDone")

        assert result.session_id is None
        assert result.is_error is False
        assert result.tool_call_count == 0
        assert len(result.events) == 0

    def test_unknown_event_type_ignored(self):
        """Test that unknown event types are ignored."""
        parser = HapiStreamParser()
        result = parser.parse_all('{"type":"unknown","data":"test"}')

        assert len(result.events) == 0

    def test_session_id_from_result_event(self):
        """Test that session_id is captured from result if not in init."""
        parser = HapiStreamParser()
        # Stream without init event, only result with session_id
        stream = '{"type":"result","session_id":"from-result","is_error":false}'
        result = parser.parse_all(stream)

        assert result.session_id == "from-result"

    def test_session_id_init_takes_precedence(self):
        """Test that session_id from init event takes precedence."""
        parser = HapiStreamParser()
        stream = "\n".join(
            [
                '{"type":"system","subtype":"init","session_id":"from-init"}',
                '{"type":"result","session_id":"from-result","is_error":false}',
            ]
        )
        result = parser.parse_all(stream)

        # Init event session_id should be used
        assert result.session_id == "from-init"

    def test_multiple_tool_results_single_event(self):
        """Test parsing user event with multiple tool results."""
        parser = HapiStreamParser()
        multi_result = (
            '{"type":"user","message":{"content":['
            '{"type":"tool_result","tool_use_id":"tu_1","content":"result1"},'
            '{"type":"tool_result","tool_use_id":"tu_2","content":"result2"}'
            "]}}"
        )
        event = parser.parse_line(multi_result)

        assert event is not None
        assert len(event.tool_results) == 2
        assert event.tool_results[0].tool_use_id == "tu_1"
        assert event.tool_results[1].tool_use_id == "tu_2"


# ============================================================================
# Enum Behavior Tests
# ============================================================================


class TestEnumBehavior:
    """Test enum string behavior."""

    def test_event_type_string_conversion(self):
        """Test that HapiEventType converts to string correctly."""
        assert str(HapiEventType.SYSTEM) == "system"
        assert str(HapiEventType.ASSISTANT) == "assistant"
        assert str(HapiEventType.USER) == "user"
        assert str(HapiEventType.RESULT) == "result"

    def test_event_type_value(self):
        """Test that HapiEventType values are correct."""
        assert HapiEventType.SYSTEM.value == "system"
        assert HapiEventType.ASSISTANT.value == "assistant"
        assert HapiEventType.USER.value == "user"
        assert HapiEventType.RESULT.value == "result"

    def test_event_type_from_string(self):
        """Test that HapiEventType can be created from string."""
        assert HapiEventType("system") == HapiEventType.SYSTEM
        assert HapiEventType("assistant") == HapiEventType.ASSISTANT
        assert HapiEventType("user") == HapiEventType.USER
        assert HapiEventType("result") == HapiEventType.RESULT

    def test_event_type_invalid_string_raises(self):
        """Test that invalid event type string raises ValueError."""
        with pytest.raises(ValueError):
            HapiEventType("invalid")


# ============================================================================
# Data Model Tests
# ============================================================================


class TestDataModels:
    """Test Pydantic model behavior."""

    def test_tool_use_info_creation(self):
        """Test ToolUseInfo model creation."""
        tool = ToolUseInfo(id="tu_test", name="Bash")
        assert tool.id == "tu_test"
        assert tool.name == "Bash"

    def test_tool_result_info_creation(self):
        """Test ToolResultInfo model creation."""
        result = ToolResultInfo(tool_use_id="tu_test")
        assert result.tool_use_id == "tu_test"

    def test_hapi_stream_event_defaults(self):
        """Test HapiStreamEvent default values."""
        event = HapiStreamEvent(type=HapiEventType.SYSTEM)

        assert event.subtype is None
        assert event.session_id is None
        assert event.is_error is False
        assert event.error_message is None
        assert event.tool_uses == []
        assert event.tool_results == []

    def test_stream_parse_result_defaults(self):
        """Test StreamParseResult default values."""
        result = StreamParseResult()

        assert result.session_id is None
        assert result.is_error is False
        assert result.error_message is None
        assert result.tool_call_count == 0
        assert result.events == []


# ============================================================================
# Incremental Parsing Tests
# ============================================================================


class TestIncrementalParsing:
    """Test line-by-line incremental parsing."""

    def test_incremental_state_accumulation(self):
        """Test that parse_line accumulates state correctly."""
        parser = HapiStreamParser()

        # Parse init
        event1 = parser.parse_line(INIT_EVENT)
        assert event1.type == HapiEventType.SYSTEM
        assert parser._session_id == "test-session-123"
        assert parser._tool_call_count == 0

        # Parse tool use
        event2 = parser.parse_line(TOOL_USE_EVENT)
        assert event2.type == HapiEventType.ASSISTANT
        assert parser._tool_call_count == 1

        # Parse tool result
        event3 = parser.parse_line(TOOL_RESULT_EVENT)
        assert event3.type == HapiEventType.USER

        # Parse result
        event4 = parser.parse_line(SUCCESS_RESULT)
        assert event4.type == HapiEventType.RESULT

        # Check accumulated state
        assert len(parser._events) == 4
        assert parser._session_id == "test-session-123"
        assert parser._tool_call_count == 1
        assert parser._is_error is False

    def test_incremental_error_detection(self):
        """Test that error is detected incrementally."""
        parser = HapiStreamParser()

        # Parse init
        parser.parse_line(INIT_EVENT)
        assert parser._is_error is False

        # Parse error result
        parser.parse_line(ERROR_RESULT)
        assert parser._is_error is True
        assert parser._error_message == "Error: OAuth token expired"
