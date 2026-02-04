"""
Hapi Stream Parser - Parses JSONL output from hapi stream-json format.

This module parses hapi's `--output-format stream-json --verbose` output,
which produces JSONL with one event per line. It extracts session information,
tool usage metrics, and error details.
"""

import json
import logging
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class HapiEventType(str, Enum):
    """
    Event types emitted by hapi in stream-json output mode.

    Each line in the JSONL stream has a "type" field indicating the event category.
    """

    SYSTEM = "system"  # Init events with session_id
    ASSISTANT = "assistant"  # Claude responses with tool_use
    USER = "user"  # Tool results
    RESULT = "result"  # Final success/error

    def __str__(self) -> str:
        """Return the string value for easy serialization."""
        return self.value


class ToolUseInfo(BaseModel):
    """
    Information about a tool call in an assistant event.

    Attributes:
        id: Unique identifier for the tool use
        name: Name of the tool being called
    """

    id: str = Field(..., description="Unique identifier for the tool use")
    name: str = Field(..., description="Name of the tool being called")


class ToolResultInfo(BaseModel):
    """
    Information about a tool result in a user event.

    Attributes:
        tool_use_id: ID of the corresponding tool_use this result responds to
    """

    tool_use_id: str = Field(..., description="ID of the corresponding tool_use")


class HapiStreamEvent(BaseModel):
    """
    A single parsed event from the JSONL stream.

    Represents one line of output from hapi stream-json format.

    Attributes:
        type: The event type (system, assistant, user, result)
        subtype: Optional subtype (e.g., "init" for system events)
        session_id: Session identifier if present in the event
        is_error: Whether this event indicates an error
        error_message: Error message if is_error is True
        tool_uses: List of tool calls in assistant events
        tool_results: List of tool results in user events
    """

    type: HapiEventType
    subtype: Optional[str] = None
    session_id: Optional[str] = None
    is_error: bool = False
    error_message: Optional[str] = None
    tool_uses: List[ToolUseInfo] = Field(default_factory=list)
    tool_results: List[ToolResultInfo] = Field(default_factory=list)


class StreamParseResult(BaseModel):
    """
    Aggregated result from parsing a complete stream.

    Combines information from all events in a hapi stream-json output
    into a single summary.

    Attributes:
        session_id: Session ID extracted from init event (available early)
        is_error: Whether the stream ended with an error
        error_message: Error message extracted from result event
        tool_call_count: Total number of tool calls made
        events: List of all parsed events
    """

    session_id: Optional[str] = Field(None, description="Session ID from init event")
    is_error: bool = Field(False, description="Whether the stream ended with an error")
    error_message: Optional[str] = Field(None, description="Error message from result event")
    tool_call_count: int = Field(0, description="Total number of tool calls made")
    events: List[HapiStreamEvent] = Field(default_factory=list, description="All parsed events")


class HapiStreamParser:
    """
    Parser for hapi --output-format stream-json --verbose output.

    This parser processes JSONL output line by line, extracting:
    - Session ID from init events (available early in the stream)
    - Tool usage information from assistant events
    - Tool results from user events
    - Final success/error status from result events

    Usage:
        parser = HapiStreamParser()
        result = parser.parse_all(stdout)
        print(f"Session: {result.session_id}, Tools: {result.tool_call_count}")

    The parser can also process lines incrementally:
        parser = HapiStreamParser()
        for line in stdout.split("\\n"):
            event = parser.parse_line(line)
            if event:
                print(f"Event: {event.type}/{event.subtype}")
    """

    def __init__(self) -> None:
        """Initialize the parser with empty state."""
        self.logger = logging.getLogger("reeve.stream_parser")
        self._events: List[HapiStreamEvent] = []
        self._session_id: Optional[str] = None
        self._is_error: bool = False
        self._error_message: Optional[str] = None
        self._tool_call_count: int = 0

    def parse_line(self, line: str) -> Optional[HapiStreamEvent]:
        """
        Parse a single JSONL line.

        Args:
            line: A single line from hapi output

        Returns:
            HapiStreamEvent if valid JSON event, None if blank/non-JSON
        """
        # Skip blank lines
        line = line.strip()
        if not line:
            return None

        # Strip terminal escape sequences (e.g., ]9;9;/path/to/dir before JSON)
        # WSL and some terminals prepend escape codes to output
        json_start = line.find("{")
        if json_start > 0:
            self.logger.debug(f"Stripping {json_start} chars of prefix before JSON")
            line = line[json_start:]
        elif json_start == -1:
            self.logger.debug(f"Skipping non-JSON line: {line[:50]}...")
            return None

        # Parse JSON (skip non-JSON lines like status messages)
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            self.logger.debug(f"Skipping non-JSON line: {line[:50]}...")
            return None

        # Extract event type
        event_type_str = data.get("type")
        if not event_type_str:
            return None

        try:
            event_type = HapiEventType(event_type_str)
        except ValueError:
            self.logger.debug(f"Unknown event type: {event_type_str}")
            return None

        # Build event based on type
        event = HapiStreamEvent(type=event_type)
        event.subtype = data.get("subtype")
        event.session_id = data.get("session_id")

        # Handle system/init - extract session_id early
        if event_type == HapiEventType.SYSTEM and event.subtype == "init":
            if event.session_id:
                self._session_id = event.session_id
                self.logger.info(f"Session ID from init: {event.session_id}")

        # Handle result events
        if event_type == HapiEventType.RESULT:
            event.is_error = data.get("is_error", False)
            if event.is_error:
                self._is_error = True
                # Extract error message from errors array (actual hapi format)
                # Format: {"errors": ["Error: message here", ...]}
                errors = data.get("errors", [])
                if errors and isinstance(errors, list):
                    event.error_message = errors[0]  # Take first error
                    self._error_message = event.error_message
                    self.logger.debug(f"Error extracted: {event.error_message[:100]}...")
            # Also capture session_id from result event (or any event)
            if event.session_id and not self._session_id:
                self._session_id = event.session_id

        # Handle assistant events - extract tool_use
        if event_type == HapiEventType.ASSISTANT:
            message = data.get("message", {})
            content = message.get("content", [])
            for item in content:
                if item.get("type") == "tool_use":
                    tool_info = ToolUseInfo(
                        id=item.get("id", ""),
                        name=item.get("name", ""),
                    )
                    event.tool_uses.append(tool_info)
                    self._tool_call_count += 1
                    self.logger.debug(f"Tool use: {tool_info.name}")

        # Handle user events - extract tool_result
        if event_type == HapiEventType.USER:
            message = data.get("message", {})
            content = message.get("content", [])
            for item in content:
                if item.get("type") == "tool_result":
                    result_info = ToolResultInfo(
                        tool_use_id=item.get("tool_use_id", ""),
                    )
                    event.tool_results.append(result_info)

        self.logger.debug(f"Parsed event: {event_type.value}/{event.subtype or '-'}")
        self._events.append(event)
        return event

    def parse_all(self, stdout: str) -> StreamParseResult:
        """
        Parse complete stdout from hapi.

        Args:
            stdout: Complete stdout string (may include non-JSON prefix)

        Returns:
            StreamParseResult with aggregated data
        """
        self.reset()

        for line in stdout.split("\n"):
            self.parse_line(line)

        return StreamParseResult(
            session_id=self._session_id,
            is_error=self._is_error,
            error_message=self._error_message,
            tool_call_count=self._tool_call_count,
            events=self._events.copy(),
        )

    def reset(self) -> None:
        """Clear parser state for reuse."""
        self._events = []
        self._session_id = None
        self._is_error = False
        self._error_message = None
        self._tool_call_count = 0
