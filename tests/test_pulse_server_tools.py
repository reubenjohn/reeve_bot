"""
Tests for Pulse Server MCP Tools

Tests the MCP tools provided by the Pulse Queue MCP server.
"""

from unittest.mock import AsyncMock

import pytest

from reeve.pulse.enums import PulsePriority


class TestPulseQueueMCPTools:
    """Test the Pulse Queue MCP tools with real functions."""

    @pytest.mark.asyncio
    async def test_schedule_pulse_with_mock_queue(self):
        """Test scheduling a pulse with a mocked queue."""
        # Import the functions directly
        import reeve.mcp.pulse_server as pulse_server_module
        from reeve.mcp.pulse_server import schedule_pulse

        # Mock the queue
        mock_queue = AsyncMock()
        mock_queue.schedule_pulse.return_value = 42
        original_queue = pulse_server_module.queue
        pulse_server_module.queue = mock_queue

        try:
            result = await schedule_pulse(
                scheduled_at="in 2 hours",
                prompt="Test pulse",
                priority="normal",
            )

            # Verify the pulse was scheduled
            mock_queue.schedule_pulse.assert_called_once()
            call_args = mock_queue.schedule_pulse.call_args

            assert call_args.kwargs["prompt"] == "Test pulse"
            assert call_args.kwargs["priority"] == PulsePriority.NORMAL
            assert call_args.kwargs["created_by"] == "reeve"

            # Verify the response
            assert "✓ Pulse scheduled successfully" in result
            assert "Pulse ID: 42" in result
        finally:
            pulse_server_module.queue = original_queue

    @pytest.mark.asyncio
    async def test_schedule_pulse_invalid_time(self):
        """Test scheduling a pulse with invalid time format."""
        import reeve.mcp.pulse_server as pulse_server_module
        from reeve.mcp.pulse_server import schedule_pulse

        mock_queue = AsyncMock()
        original_queue = pulse_server_module.queue
        pulse_server_module.queue = mock_queue

        try:
            result = await schedule_pulse(
                scheduled_at="invalid_time",
                prompt="Test pulse",
                priority="normal",
            )

            # Should return error message
            assert "✗ Failed to schedule pulse" in result
            assert "Could not parse time string" in result

            # Queue should not be called
            mock_queue.schedule_pulse.assert_not_called()
        finally:
            pulse_server_module.queue = original_queue


class TestPulseQueueMCPIntegration:
    """Integration tests with real PulseQueue."""

    @pytest.mark.asyncio
    async def test_full_pulse_lifecycle(self):
        """Test scheduling, listing, and cancelling a pulse."""
        import reeve.mcp.pulse_server as pulse_server_module
        from reeve.mcp.pulse_server import cancel_pulse, list_upcoming_pulses, schedule_pulse
        from reeve.pulse.queue import PulseQueue

        # Create in-memory database
        queue = PulseQueue("sqlite+aiosqlite:///:memory:")
        await queue.initialize()
        original_queue = pulse_server_module.queue
        pulse_server_module.queue = queue

        try:
            # Schedule a pulse
            result = await schedule_pulse(
                scheduled_at="in 1 hour",
                prompt="Integration test pulse",
                priority="normal",
            )

            assert "✓ Pulse scheduled successfully" in result
            assert "Pulse ID: 1" in result

            # List pulses
            result = await list_upcoming_pulses()
            assert "Integration test pulse" in result
            assert "[0001]" in result

            # Cancel the pulse
            result = await cancel_pulse(pulse_id=1)
            assert "✓ Pulse 1 cancelled successfully" in result

            # List should now be empty (cancelled pulses excluded by default)
            result = await list_upcoming_pulses()
            assert "No upcoming pulses scheduled" in result

            await queue.close()
        finally:
            pulse_server_module.queue = original_queue
