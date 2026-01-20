"""
Unit tests for PulseExecutor.

Tests pulse execution by launching Hapi sessions, including:
- Basic execution with mocked Hapi command
- Prompt building with sticky notes
- Session resumption
- Error handling (crashes, timeouts, invalid paths)
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reeve.pulse.executor import PulseExecutor


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
    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"Hapi output", b""))
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await executor.execute(
            prompt="Test prompt",
            working_dir=str(mock_desk),
        )

    assert result["stdout"] == "Hapi output"
    assert result["stderr"] == ""
    assert result["return_code"] == 0
    assert result["timed_out"] is False


@pytest.mark.asyncio
async def test_execute_with_session_id(executor, mock_desk):
    """Test execution with session resume."""
    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"Resumed session", b""))
    mock_process.returncode = 0

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
    assert result["return_code"] == 0


@pytest.mark.asyncio
async def test_execute_with_stderr(executor, mock_desk):
    """Test execution with stderr output but success."""
    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(
        return_value=(b"Success", b"Warning: deprecated API")
    )
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await executor.execute(
            prompt="Test prompt",
            working_dir=str(mock_desk),
        )

    assert result["stdout"] == "Success"
    assert result["stderr"] == "Warning: deprecated API"
    assert result["return_code"] == 0


@pytest.mark.asyncio
async def test_execute_uses_desk_path_by_default(executor):
    """Test that executor uses desk_path as default working directory."""
    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"Output", b""))
    mock_process.returncode = 0

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
    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(
        return_value=(b"", b"Error: command failed")
    )
    mock_process.returncode = 1

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
    # Simulate timeout by having communicate never return
    async def never_completes():
        await asyncio.sleep(100)  # Sleep longer than timeout
        return (b"", b"")

    mock_process.communicate = never_completes
    mock_process.kill = MagicMock()
    mock_process.wait = AsyncMock()

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
    mock_process = AsyncMock()
    # Invalid UTF-8 bytes
    mock_process.communicate = AsyncMock(
        return_value=(b"\xff\xfe Invalid UTF-8", b"")
    )
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await executor.execute(
            prompt="Test prompt",
            working_dir=str(mock_desk),
        )

    # Should not raise, should use error replacement
    assert result["return_code"] == 0
    assert isinstance(result["stdout"], str)


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

    # Mock Hapi execution
    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(
        return_value=(b"Briefing completed successfully", b"")
    )
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await executor.execute(
            prompt=full_prompt,
            session_id="session-abc",
            working_dir=str(mock_desk),
        )

    # Verify the command was constructed correctly
    call_args = mock_exec.call_args[0]
    assert "hapi" in call_args
    assert "run" in call_args
    assert "--resume" in call_args
    assert "session-abc" in call_args
    assert "--text" in call_args

    # Verify the result
    assert result["return_code"] == 0
    assert "successfully" in result["stdout"]
    assert result["timed_out"] is False


@pytest.mark.asyncio
async def test_timeout_override_works(executor, mock_desk):
    """Test that timeout_override parameter works."""
    mock_process = AsyncMock()

    # Simulate a slow operation
    async def slow_communicate():
        await asyncio.sleep(0.5)
        return (b"Output", b"")

    mock_process.communicate = slow_communicate
    mock_process.kill = MagicMock()
    mock_process.wait = AsyncMock()

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

    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"Output", b""))
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        await executor.execute(
            prompt="Test",
            working_dir=str(custom_dir),
        )

    # Verify custom directory was used
    call_kwargs = mock_exec.call_args[1]
    assert call_kwargs["cwd"] == str(custom_dir.resolve())
