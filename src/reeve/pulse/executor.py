"""
Pulse Executor - Launches Hapi sessions to execute pulses.

This module handles the actual execution of pulses by spawning Hapi/Claude Code
sessions with the pulse's prompt as the initial context.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ExecutionResult(BaseModel):
    """
    Result of a pulse execution.

    Attributes:
        stdout: Standard output from Hapi/Claude Code
        stderr: Standard error from Hapi/Claude Code
        return_code: Process exit code (0 = success, -1 = timeout)
        timed_out: Whether the execution timed out
        session_id: Session ID of the executed session (new or resumed)
    """

    stdout: str = Field(..., description="Standard output from Hapi/Claude Code")
    stderr: str = Field(..., description="Standard error from Hapi/Claude Code")
    return_code: int = Field(..., description="Process exit code (0 = success, -1 = timeout)")
    timed_out: bool = Field(..., description="Whether the execution timed out")
    session_id: Optional[str] = Field(None, description="Session ID of the executed session")


class PulseExecutor:
    """
    Executes pulses by launching Hapi sessions.

    This executor is responsible for:
    1. Launching Hapi subprocess with correct working directory
    2. Building the full prompt (including sticky notes appended)
    3. Capturing stdout/stderr
    4. Reporting success/failure
    5. Handling timeouts and crashes gracefully
    """

    def __init__(
        self,
        hapi_command: str,
        desk_path: str,
        timeout_seconds: int = 3600,
    ):
        """
        Initialize the executor.

        Args:
            hapi_command: Path to Hapi executable (e.g., "hapi", "/usr/local/bin/hapi")
            desk_path: Path to the user's Desk directory (working directory for Hapi)
            timeout_seconds: Maximum execution time in seconds (default: 3600 = 1 hour)
        """
        self.hapi_command = hapi_command
        self.desk_path = Path(desk_path).expanduser().resolve()
        self.timeout_seconds = timeout_seconds
        self.logger = logging.getLogger("reeve.executor")

    async def execute(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        working_dir: Optional[str] = None,
        timeout_override: Optional[int] = None,
    ) -> ExecutionResult:
        """
        Execute a pulse by launching a Hapi session.

        Args:
            prompt: The instruction/context for Reeve (may include sticky notes)
            session_id: Optional session ID to resume
            working_dir: Override working directory (defaults to desk_path)
            timeout_override: Override timeout for this specific execution

        Returns:
            ExecutionResult with stdout, stderr, return_code, timed_out, and session_id

        Raises:
            RuntimeError: If Hapi execution fails (non-zero exit code)
        """
        cwd = Path(working_dir).expanduser().resolve() if working_dir else self.desk_path
        timeout = timeout_override if timeout_override is not None else self.timeout_seconds

        # Validate working directory exists
        if not cwd.exists():
            raise RuntimeError(f"Working directory does not exist: {cwd}")

        # Build Hapi command
        # Use --print for non-interactive execution (automated pulse execution)
        # Use --output-format json to get structured output with session_id
        cmd = [self.hapi_command, "--print", "--output-format", "json"]

        # Add session resume flag if provided
        if session_id:
            cmd.extend(["--resume", session_id])

        # Add prompt as positional argument (must be last)
        cmd.append(prompt)

        self.logger.debug(f"Executing: {' '.join(cmd)} (cwd: {cwd}, timeout: {timeout}s)")

        # Execute Hapi as subprocess
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                timed_out = False
            except asyncio.TimeoutError:
                self.logger.warning(f"Hapi execution timed out after {timeout}s")
                # Kill the process
                process.kill()
                await process.wait()
                timed_out = True
                stdout = b""
                stderr = b"Execution timed out"

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            return_code = process.returncode if not timed_out else -1

            # Parse JSON output to extract session_id (if available)
            extracted_session_id = None
            if not timed_out and return_code == 0:
                try:
                    # Claude Code --output-format json outputs JSON with session_id
                    json_output = json.loads(stdout_str)
                    extracted_session_id = json_output.get("session_id")
                except (json.JSONDecodeError, KeyError):
                    # If JSON parsing fails, we'll proceed without session_id
                    self.logger.debug("Could not parse session_id from JSON output")

            result = ExecutionResult(
                stdout=stdout_str,
                stderr=stderr_str,
                return_code=return_code,
                timed_out=timed_out,
                session_id=extracted_session_id,
            )

            # Check for errors
            if timed_out:
                raise RuntimeError(f"Hapi execution timed out after {timeout}s: {result.stderr}")

            if process.returncode != 0:
                raise RuntimeError(
                    f"Hapi execution failed (exit code {process.returncode}): " f"{result.stderr}"
                )

            self.logger.info(
                f"Hapi execution completed successfully (session_id: {extracted_session_id})"
            )
            return result

        except FileNotFoundError:
            raise RuntimeError(
                f"Hapi command not found: {self.hapi_command}. "
                f"Make sure Hapi is installed and HAPI_COMMAND is set correctly."
            )
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Unexpected error during Hapi execution: {str(e)}")

    def build_prompt(
        self,
        base_prompt: str,
        sticky_notes: Optional[list[str]] = None,
    ) -> str:
        """
        Build the full prompt including sticky notes.

        Sticky notes are appended to the base prompt to provide additional
        context or reminders. They are formatted with a clear header to
        distinguish them from the main prompt.

        Args:
            base_prompt: The main prompt/instruction
            sticky_notes: Optional list of reminder strings to append

        Returns:
            Full prompt string with formatted sticky notes appended

        Example:
            >>> executor.build_prompt(
            ...     "Daily morning briefing",
            ...     ["Check if user replied to ski trip", "Follow up on PR review"]
            ... )
            "Daily morning briefing

            📌 Reminders:
              - Check if user replied to ski trip
              - Follow up on PR review"
        """
        if not sticky_notes:
            return base_prompt

        parts = [base_prompt, ""]  # Base prompt + blank line

        # Add sticky notes section
        parts.append("📌 Reminders:")
        for note in sticky_notes:
            parts.append(f"  - {note}")

        return "\n".join(parts)
