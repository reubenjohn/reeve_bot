"""
Unit tests for PulseExecutor.

Tests pulse execution by launching Hapi sessions, including:
- Basic execution with mocked Hapi command
- Prompt building with sticky notes
- Session resumption
- Error handling (crashes, timeouts, invalid paths)
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reeve.pulse.executor import ExecutionResult, PulseExecutor


def create_mock_process(stdout_data: bytes, stderr_data: bytes, returncode: int = 0):
    """Create a mock process with streaming stdout/stderr support."""
    mock_process = AsyncMock()
    mock_process.returncode = returncode

    # Create mock streams that return data once then empty
    async def make_stream(data: bytes):
        """Create a mock stream reader."""
        reader = AsyncMock()
        reader._data_returned = False

        async def read_chunk(size):
            if not reader._data_returned:
                reader._data_returned = True
                return data
            return b""

        reader.read = read_chunk
        return reader

    # We need to set up stdout/stderr as async generators
    mock_process.stdout = AsyncMock()
    mock_process.stderr = AsyncMock()

    # Track if data has been returned
    stdout_returned = [False]
    stderr_returned = [False]

    async def stdout_read(size=4096):
        if not stdout_returned[0]:
            stdout_returned[0] = True
            return stdout_data
        return b""

    async def stderr_read(size=4096):
        if not stderr_returned[0]:
            stderr_returned[0] = True
            return stderr_data
        return b""

    mock_process.stdout.read = stdout_read
    mock_process.stderr.read = stderr_read
    mock_process.wait = AsyncMock()

    return mock_process


@pytest.fixture
def executor():
    """Create a PulseExecutor instance for testing."""
    return PulseExecutor(
        hapi_command="hapi",
        desk_path="/tmp/test_desk",
        timeout_seconds=10,
    )


@pytest.fixture
def mock_desk(tmp_path):
    """Create a temporary desk directory."""
    desk_path = tmp_path / "desk"
    desk_path.mkdir()
    return desk_path


# ============================================================================
# Prompt Building Tests
# ============================================================================


def test_build_prompt_without_sticky_notes(executor):
    """Test prompt building with no sticky notes."""
    prompt = executor.build_prompt("Check calendar for today")
    assert prompt == "Check calendar for today"


def test_build_prompt_with_sticky_notes(executor):
    """Test prompt building with sticky notes appended."""
    base_prompt = "Daily morning briefing"
    sticky_notes = [
        "Check if user replied to ski trip",
        "Follow up on PR review",
    ]

    result = executor.build_prompt(base_prompt, sticky_notes)

    expected = """Daily morning briefing

📌 Reminders:
  - Check if user replied to ski trip
  - Follow up on PR review"""

    assert result == expected


def test_build_prompt_with_empty_sticky_notes(executor):
    """Test prompt building with empty sticky notes list."""
    prompt = executor.build_prompt("Check calendar", [])
    assert prompt == "Check calendar"


def test_build_prompt_with_single_sticky_note(executor):
    """Test prompt building with a single sticky note."""
    result = executor.build_prompt("Morning briefing", ["Check ticket prices"])

    expected = """Morning briefing

📌 Reminders:
  - Check ticket prices"""

    assert result == expected


# ============================================================================
# Execution Tests
# ============================================================================


@pytest.mark.asyncio
async def test_execute_basic_success(executor, mock_desk):
    """Test successful Hapi execution."""
    # Mock JSON output with session_id
    json_output = json.dumps({"session_id": "test-session-123", "output": "Hapi output"})
    mock_process = create_mock_process(json_output.encode(), b"", returncode=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await executor.execute(
            prompt="Test prompt",
            working_dir=str(mock_desk),
        )

    assert isinstance(result, ExecutionResult)
    assert result.session_id == "test-session-123"
    assert result.stderr == ""
    assert result.return_code == 0
    assert result.timed_out is False


@pytest.mark.asyncio
async def test_execute_with_session_id(executor, mock_desk):
    """Test execution with session resume."""
    json_output = json.dumps({"session_id": "session-123", "output": "Resumed session"})
    mock_process = create_mock_process(json_output.encode(), b"", returncode=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await executor.execute(
            prompt="Continue work",
            session_id="session-123",
            working_dir=str(mock_desk),
        )

    # Verify --resume flag was passed
    call_args = mock_exec.call_args[0]
    assert "--resume" in call_args
    assert "session-123" in call_args
    assert "--output-format" in call_args
    assert "json" in call_args
    assert result.return_code == 0
    assert result.session_id == "session-123"


@pytest.mark.asyncio
async def test_execute_with_stderr(executor, mock_desk):
    """Test execution with stderr output but success."""
    json_output = json.dumps({"session_id": "test-session", "output": "Success"})
    mock_process = create_mock_process(
        json_output.encode(), b"Warning: deprecated API", returncode=0
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await executor.execute(
            prompt="Test prompt",
            working_dir=str(mock_desk),
        )

    assert result.session_id == "test-session"
    assert result.stderr == "Warning: deprecated API"
    assert result.return_code == 0


@pytest.mark.asyncio
async def test_execute_uses_desk_path_by_default(executor):
    """Test that executor uses desk_path as default working directory."""
    json_output = json.dumps({"session_id": "test-session", "output": "Output"})
    mock_process = create_mock_process(json_output.encode(), b"", returncode=0)

    # Create the default desk path
    desk_path = Path("/tmp/test_desk")
    desk_path.mkdir(parents=True, exist_ok=True)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        await executor.execute(prompt="Test")

    # Verify cwd argument
    call_kwargs = mock_exec.call_args[1]
    assert call_kwargs["cwd"] == str(desk_path.resolve())

    # Cleanup
    desk_path.rmdir()


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
async def test_execute_nonzero_exit_code(executor, mock_desk):
    """Test execution failure with non-zero exit code."""
    mock_process = create_mock_process(b"", b"Error: command failed", returncode=1)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(RuntimeError, match="Hapi execution failed.*exit code 1"):
            await executor.execute(
                prompt="Test prompt",
                working_dir=str(mock_desk),
            )


@pytest.mark.asyncio
async def test_execute_command_not_found(executor, mock_desk):
    """Test execution when Hapi command doesn't exist."""
    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError("hapi not found"),
    ):
        with pytest.raises(RuntimeError, match="Hapi command not found"):
            await executor.execute(
                prompt="Test prompt",
                working_dir=str(mock_desk),
            )


@pytest.mark.asyncio
async def test_execute_working_dir_not_exists(executor):
    """Test execution when working directory doesn't exist."""
    with pytest.raises(RuntimeError, match="Working directory does not exist"):
        await executor.execute(
            prompt="Test prompt",
            working_dir="/nonexistent/path",
        )


@pytest.mark.asyncio
async def test_execute_timeout(executor, mock_desk):
    """Test execution timeout handling."""
    mock_process = AsyncMock()

    # Simulate timeout by having read never return
    async def never_completes(size=4096):
        await asyncio.sleep(100)  # Sleep longer than timeout
        return b""

    mock_process.stdout = AsyncMock()
    mock_process.stdout.read = never_completes
    mock_process.stderr = AsyncMock()
    mock_process.stderr.read = never_completes
    mock_process.kill = MagicMock()
    mock_process.wait = AsyncMock()
    mock_process.returncode = -1

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        # Use a very short timeout for testing
        with pytest.raises(RuntimeError, match="timed out"):
            await executor.execute(
                prompt="Test prompt",
                working_dir=str(mock_desk),
                timeout_override=0.1,  # 100ms timeout
            )

    # Verify process was killed
    mock_process.kill.assert_called_once()


@pytest.mark.asyncio
async def test_execute_handles_utf8_errors(executor, mock_desk):
    """Test execution handles invalid UTF-8 in output."""
    # Invalid UTF-8 bytes (not valid JSON)
    mock_process = create_mock_process(b"\xff\xfe Invalid UTF-8", b"", returncode=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await executor.execute(
            prompt="Test prompt",
            working_dir=str(mock_desk),
        )

    # Should not raise, should use error replacement
    assert result.return_code == 0
    assert isinstance(result.stdout, str)
    # session_id should be None since JSON parsing failed
    assert result.session_id is None


# ============================================================================
# Configuration Tests
# ============================================================================


def test_executor_expands_desk_path():
    """Test that executor expands ~ in desk_path."""
    executor = PulseExecutor(
        hapi_command="hapi",
        desk_path="~/my_reeve",
    )

    # Should be expanded to absolute path
    assert executor.desk_path.is_absolute()
    assert "~" not in str(executor.desk_path)


def test_executor_custom_timeout():
    """Test executor with custom timeout."""
    executor = PulseExecutor(
        hapi_command="hapi",
        desk_path="/tmp/desk",
        timeout_seconds=7200,  # 2 hours
    )

    assert executor.timeout_seconds == 7200


# ============================================================================
# Integration-style Tests
# ============================================================================


@pytest.mark.asyncio
async def test_full_execution_flow(executor, mock_desk):
    """Test complete execution flow from prompt to result."""
    base_prompt = "Daily briefing"
    sticky_notes = ["Check calendar", "Review emails"]

    # Build full prompt with sticky notes
    full_prompt = executor.build_prompt(base_prompt, sticky_notes)

    # Mock Hapi execution with JSON output
    json_output = json.dumps(
        {"session_id": "session-abc", "output": "Briefing completed successfully"}
    )
    mock_process = create_mock_process(json_output.encode(), b"", returncode=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await executor.execute(
            prompt=full_prompt,
            session_id="session-abc",
            working_dir=str(mock_desk),
        )

    # Verify the command was constructed correctly
    call_args = mock_exec.call_args[0]
    assert "hapi" in call_args
    assert "--print" in call_args
    assert "--output-format" in call_args
    assert "json" in call_args
    assert "--resume" in call_args
    assert "session-abc" in call_args
    assert full_prompt in call_args  # Prompt is passed as positional arg

    # Verify the result
    assert result.return_code == 0
    assert result.session_id == "session-abc"
    assert result.timed_out is False


@pytest.mark.asyncio
async def test_timeout_override_works(executor, mock_desk):
    """Test that timeout_override parameter works."""
    mock_process = AsyncMock()

    # Simulate a slow read operation
    async def slow_read(size=4096):
        await asyncio.sleep(0.5)
        return b""

    mock_process.stdout = AsyncMock()
    mock_process.stdout.read = slow_read
    mock_process.stderr = AsyncMock()
    mock_process.stderr.read = slow_read
    mock_process.kill = MagicMock()
    mock_process.wait = AsyncMock()
    mock_process.returncode = -1

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        # Should timeout with override of 0.1s
        with pytest.raises(RuntimeError, match="timed out"):
            await executor.execute(
                prompt="Test",
                working_dir=str(mock_desk),
                timeout_override=0.1,
            )


@pytest.mark.asyncio
async def test_working_dir_override(executor, tmp_path):
    """Test working directory override."""
    custom_dir = tmp_path / "custom_workspace"
    custom_dir.mkdir()

    json_output = json.dumps({"session_id": "test-session", "output": "Output"})
    mock_process = create_mock_process(json_output.encode(), b"", returncode=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        await executor.execute(
            prompt="Test",
            working_dir=str(custom_dir),
        )

    # Verify custom directory was used
    call_kwargs = mock_exec.call_args[1]
    assert call_kwargs["cwd"] == str(custom_dir.resolve())


@pytest.mark.asyncio
async def test_session_id_extraction_from_json(executor, mock_desk):
    """Test that session_id is properly extracted from JSON output."""
    json_output = json.dumps(
        {"session_id": "new-session-xyz", "output": "Task completed", "status": "success"}
    )
    mock_process = create_mock_process(json_output.encode(), b"", returncode=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await executor.execute(
            prompt="Test prompt",
            working_dir=str(mock_desk),
        )

    # Verify session_id was extracted from JSON
    assert result.session_id == "new-session-xyz"
    assert result.return_code == 0


@pytest.mark.asyncio
async def test_session_id_extraction_with_prefix_text(executor, mock_desk):
    """Test that session_id is extracted even when JSON has prefix text (real hapi output)."""
    # Real hapi output has terminal sequences and status messages before JSON
    prefix_text = (
        ']9;9;"\\\\wsl.localhost\\Ubuntu\\home\\user\\desk"\n'
        "Starting HAPI hub in background...\n"
        "HAPI hub started\n"
    )
    json_output = json.dumps(
        {"session_id": "abc-123-def", "result": "Done", "type": "result"}
    )
    full_output = prefix_text + json_output
    mock_process = create_mock_process(full_output.encode(), b"", returncode=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await executor.execute(
            prompt="Test prompt",
            working_dir=str(mock_desk),
        )

    # session_id should be extracted despite prefix text
    assert result.session_id == "abc-123-def"
    assert result.return_code == 0


@pytest.mark.asyncio
async def test_session_id_none_on_invalid_json(executor, mock_desk):
    """Test that session_id is None when JSON parsing fails."""
    # Return non-JSON output
    mock_process = create_mock_process(b"Plain text output", b"", returncode=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await executor.execute(
            prompt="Test prompt",
            working_dir=str(mock_desk),
        )

    # session_id should be None since JSON parsing failed
    assert result.session_id is None
    assert result.return_code == 0
