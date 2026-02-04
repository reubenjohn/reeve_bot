"""
Tests for debug tools: TimingBreakdown and trigger_pulse.
"""

import asyncio
import logging
import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from reeve.debug.timing import TimingBreakdown, timed_section
from reeve.pulse.executor import PulseExecutor, ExecutionResult


class TestTimingBreakdown:
    """Tests for the TimingBreakdown class."""

    def test_basic_timing(self):
        """Test basic timing without marks."""
        with TimingBreakdown("test", auto_log=False) as t:
            time.sleep(0.01)  # 10ms

        breakdown = t.get_breakdown()
        assert "total" in breakdown
        assert breakdown["total"] >= 10  # At least 10ms

    def test_timing_with_marks(self):
        """Test timing with named marks."""
        with TimingBreakdown("test", auto_log=False) as t:
            time.sleep(0.01)
            t.mark("step1")
            time.sleep(0.02)
            t.mark("step2")

        breakdown = t.get_breakdown()
        assert "step1" in breakdown
        assert "step2" in breakdown
        assert "total" in breakdown
        assert breakdown["step1"] >= 10
        assert breakdown["step2"] >= 20

    def test_auto_logging(self, caplog):
        """Test that auto_log=True logs the breakdown."""
        with caplog.at_level(logging.INFO):
            with TimingBreakdown("test_op", auto_log=True) as t:
                t.mark("init")
                time.sleep(0.001)

        assert "test_op:" in caplog.text
        assert "init=" in caplog.text
        assert "total=" in caplog.text

    def test_no_auto_logging(self, caplog):
        """Test that auto_log=False doesn't log."""
        with caplog.at_level(logging.INFO):
            with TimingBreakdown("test_op", auto_log=False) as t:
                t.mark("init")

        assert "test_op:" not in caplog.text

    def test_format_breakdown(self):
        """Test formatted string output."""
        with TimingBreakdown("test", auto_log=False) as t:
            t.mark("step1")
            time.sleep(0.01)
            t.mark("step2")

        formatted = t.format_breakdown()
        assert "step1=" in formatted
        assert "step2=" in formatted
        assert "total=" in formatted
        assert "ms" in formatted

    def test_get_breakdown_before_exit(self):
        """Test getting breakdown while still inside context."""
        with TimingBreakdown("test", auto_log=False) as t:
            t.mark("step1")
            breakdown = t.get_breakdown()
            assert "step1" in breakdown
            assert "total" in breakdown

    def test_empty_breakdown_before_enter(self):
        """Test breakdown returns empty dict before context entered."""
        t = TimingBreakdown("test", auto_log=False)
        assert t.get_breakdown() == {}

    def test_exception_not_suppressed(self):
        """Test that exceptions are not suppressed."""
        with pytest.raises(ValueError):
            with TimingBreakdown("test", auto_log=False) as t:
                t.mark("before_error")
                raise ValueError("Test error")

    def test_custom_log_level(self, caplog):
        """Test custom logging level."""
        with caplog.at_level(logging.DEBUG):
            with TimingBreakdown("test_op", log_level=logging.DEBUG, auto_log=True) as t:
                t.mark("init")

        assert "test_op:" in caplog.text

    def test_timed_section_convenience_function(self, caplog):
        """Test the timed_section convenience function."""
        with caplog.at_level(logging.INFO):
            with timed_section("my_operation") as t:
                t.mark("step1")

        assert "my_operation:" in caplog.text


class TestExecutorDryRun:
    """Tests for the dry_run parameter in PulseExecutor."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create a PulseExecutor with a temporary working directory."""
        return PulseExecutor(
            hapi_command="hapi",
            desk_path=str(tmp_path),
            timeout_seconds=60,
        )

    @pytest.mark.asyncio
    async def test_dry_run_returns_success(self, executor):
        """Test that dry_run returns success without executing."""
        result = await executor.execute(
            prompt="Test prompt",
            dry_run=True,
        )

        assert isinstance(result, ExecutionResult)
        assert result.return_code == 0
        assert result.timed_out is False
        assert result.session_id is None
        assert "[DRY RUN]" in result.stdout

    @pytest.mark.asyncio
    async def test_dry_run_does_not_spawn_subprocess(self, executor):
        """Test that dry_run doesn't actually spawn a subprocess."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            result = await executor.execute(
                prompt="Test prompt",
                dry_run=True,
            )

            # Subprocess should not be called in dry run mode
            mock_subprocess.assert_not_called()
            assert result.return_code == 0

    @pytest.mark.asyncio
    async def test_dry_run_logs_command(self, executor, caplog):
        """Test that dry_run logs what would be executed."""
        with caplog.at_level(logging.INFO):
            await executor.execute(
                prompt="Test prompt",
                dry_run=True,
            )

        assert "[DRY RUN]" in caplog.text
        assert "Would execute:" in caplog.text

    @pytest.mark.asyncio
    async def test_dry_run_with_session_id(self, executor):
        """Test dry_run with session_id parameter."""
        result = await executor.execute(
            prompt="Resume test",
            session_id="test-session-123",
            dry_run=True,
        )

        assert result.return_code == 0
        assert "[DRY RUN]" in result.stdout

    @pytest.mark.asyncio
    async def test_dry_run_validates_working_dir(self, executor):
        """Test that dry_run still validates working directory exists."""
        # Create a new executor with a non-existent path
        bad_executor = PulseExecutor(
            hapi_command="hapi",
            desk_path="/nonexistent/path/that/does/not/exist",
            timeout_seconds=60,
        )

        with pytest.raises(RuntimeError, match="Working directory does not exist"):
            await bad_executor.execute(
                prompt="Test prompt",
                dry_run=True,
            )

    @pytest.mark.asyncio
    async def test_normal_execution_still_works(self, executor):
        """Test that normal (non-dry-run) execution still spawns subprocess."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b'{"session_id": "test-123"}',
            b"",
        )
        mock_process.returncode = 0

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ) as mock_subprocess:
            result = await executor.execute(
                prompt="Test prompt",
                dry_run=False,
            )

            # Subprocess should be called in normal mode
            mock_subprocess.assert_called_once()
            assert result.session_id == "test-123"
