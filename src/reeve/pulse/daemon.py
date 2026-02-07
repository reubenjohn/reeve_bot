"""
Pulse Daemon - Main orchestrator for pulse execution.

This daemon runs continuously in the background, managing:
1. Pulse scheduler (checks queue every 1 second)
2. Concurrent pulse execution
3. Graceful shutdown handling

Usage:
    # Development
    python -m reeve.pulse

    # Production (via systemd)
    systemctl start reeve-daemon
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone
from typing import Optional

from reeve.pulse.executor import PulseExecutor
from reeve.pulse.models import Pulse
from reeve.pulse.queue import PulseQueue
from reeve.utils.config import ReeveConfig


class PulseDaemon:
    """
    Main daemon process that orchestrates pulse execution.

    The daemon continuously polls for due pulses and executes them
    concurrently via the PulseExecutor. It handles graceful shutdown
    and automatic retry on failures.
    """

    def __init__(self, config: ReeveConfig):
        """
        Initialize the daemon.

        Args:
            config: ReeveConfig instance with database URL, Hapi command, etc.
        """
        self.config = config
        self.queue = PulseQueue(config.pulse_db_url)
        self.executor = PulseExecutor(
            hapi_command=config.hapi_command,
            desk_path=config.reeve_desk_path,
        )
        self.logger = logging.getLogger("reeve.daemon")

        # State
        self.running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        self.api_task: Optional[asyncio.Task] = None
        self.executing_pulses: set[asyncio.Task] = set()
        self.shutdown_event = asyncio.Event()
        self.max_concurrent = config.pulse_max_concurrent

    async def _execute_pulse(self, pulse: Pulse) -> None:
        """
        Execute a single pulse and update database.

        This method:
        1. Builds the full prompt (including sticky notes)
        2. Executes via PulseExecutor
        3. Tracks execution duration
        4. Marks pulse as COMPLETED or FAILED (with retry)

        Args:
            pulse: The Pulse model instance to execute
        """
        start_time = datetime.now(timezone.utc)
        pulse_id = pulse.id
        prompt_preview = pulse.prompt[:50] + "..." if len(pulse.prompt) > 50 else pulse.prompt

        self.logger.info(f"Executing pulse {pulse_id}: {prompt_preview}")

        try:
            # Build full prompt with sticky notes appended
            full_prompt = self.executor.build_prompt(pulse.prompt, pulse.sticky_notes)  # type: ignore[arg-type]

            # Execute via PulseExecutor
            result = await self.executor.execute(
                prompt=full_prompt,
                session_id=pulse.session_id,  # type: ignore[arg-type]
                working_dir=self.config.reeve_desk_path,
            )

            # Calculate duration in milliseconds
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            # Mark as completed
            await self.queue.mark_completed(pulse_id, duration_ms)  # type: ignore[arg-type]

            self.logger.info(
                f"Pulse {pulse_id} completed successfully in {duration_ms}ms "
                f"(session_id: {result.session_id})"
            )

        except Exception as e:
            # Log the error with full traceback
            self.logger.error(f"Pulse {pulse_id} failed: {e}", exc_info=True)

            # Mark as failed (will auto-retry if retries remaining)
            retry_pulse_id = await self.queue.mark_failed(
                pulse_id,  # type: ignore[arg-type]
                error_message=str(e),
                should_retry=True,
            )

            if retry_pulse_id:
                self.logger.info(f"Pulse {pulse_id} scheduled for retry as pulse {retry_pulse_id}")
            else:
                self.logger.error(f"Pulse {pulse_id} failed permanently (no retries left)")

    async def _scheduler_loop(self) -> None:
        """
        Main scheduler loop: poll for due pulses every 1 second and execute concurrently.

        The loop:
        1. Gets up to 10 due pulses (ordered by priority)
        2. Marks each as PROCESSING (atomic check)
        3. Spawns non-blocking execution tasks
        4. Sleeps 1 second before next iteration
        5. Handles errors gracefully without crashing
        """
        self.logger.info("Scheduler loop started")

        while self.running:
            try:
                # Check available slots
                current_executing = len(self.executing_pulses)
                available_slots = self.max_concurrent - current_executing

                if available_slots <= 0:
                    self.logger.debug(f"At max capacity ({current_executing}/{self.max_concurrent}), waiting...")
                    await asyncio.sleep(1)
                    continue

                # Fetch only what we can handle
                fetch_limit = min(10, available_slots)

                # Get due pulses (up to fetch_limit at a time, ordered by priority)
                pulses = await self.queue.get_due_pulses(limit=fetch_limit)

                # Spawn execution task for each pulse
                for pulse in pulses:
                    # Mark as processing (atomic, prevents duplicate execution)
                    success = await self.queue.mark_processing(pulse.id)  # type: ignore[arg-type]
                    if not success:
                        # Pulse already processing or completed, skip
                        self.logger.warning(
                            f"Pulse {pulse.id} already processing/completed, skipping"
                        )
                        continue

                    # Create non-blocking task
                    task = asyncio.create_task(
                        self._execute_pulse(pulse),
                        name=f"pulse-{pulse.id}",
                    )

                    # Track for graceful shutdown
                    self.executing_pulses.add(task)
                    task.add_done_callback(self.executing_pulses.discard)

                # Sleep 1 second before next check
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                # Shutdown requested
                self.logger.info("Scheduler loop cancelled, shutting down")
                break
            except Exception as e:
                # Log error but don't crash - back off and retry
                self.logger.error(f"Scheduler loop error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Back off 5 seconds on error

        self.logger.info("Scheduler loop stopped")

    async def _run_api_server(self) -> None:
        """
        Run the FastAPI server using uvicorn.

        This method:
        1. Imports FastAPI app factory from reeve.api.server
        2. Configures uvicorn.Server with host and port from config
        3. Runs server with asyncio cancellation handling
        4. Cleans up on shutdown or cancellation

        The API server runs concurrently with the scheduler loop, allowing
        external systems to trigger pulses via HTTP while the scheduler
        manages execution.
        """
        import uvicorn

        from reeve.api.server import create_app

        self.logger.info(f"Starting API server on http://127.0.0.1:{self.config.pulse_api_port}")

        # Create FastAPI app
        app = create_app(self.queue, self.config)

        # Configure uvicorn server
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self.config.pulse_api_port,
            log_level="info",
            access_log=False,  # Reduce noise, we have our own logging
        )
        server = uvicorn.Server(config)

        try:
            # Run server (blocks until shutdown)
            await server.serve()
        except asyncio.CancelledError:
            self.logger.info("API server cancelled, shutting down")
            # Uvicorn handles cleanup automatically
        except Exception as e:
            self.logger.error(f"API server error: {e}", exc_info=True)

        self.logger.info("API server stopped")

    def _register_signal_handlers(self) -> None:
        """
        Register SIGTERM and SIGINT handlers for graceful shutdown.

        This allows the daemon to be stopped cleanly via:
        - Ctrl+C (SIGINT)
        - systemctl stop (SIGTERM)
        - kill <pid> (SIGTERM)
        """
        loop = asyncio.get_event_loop()

        def create_shutdown_task(s: signal.Signals) -> asyncio.Task[None]:
            return asyncio.create_task(self._handle_shutdown(s))

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                create_shutdown_task,
                sig,
            )

        self.logger.info("Signal handlers registered (SIGTERM, SIGINT)")

    async def _handle_shutdown(self, sig: signal.Signals) -> None:
        """
        Handle graceful shutdown.

        Shutdown process:
        1. Stop accepting new pulses (running=False)
        2. Cancel scheduler task and API task
        3. Wait up to 30 seconds for in-flight pulses to complete
        4. Force cancel remaining tasks if timeout exceeded
        5. Close database connection

        Args:
            sig: The signal that triggered shutdown
        """
        self.logger.info(f"Received {sig.name}, shutting down gracefully...")

        # Stop accepting new pulses
        self.running = False

        # Cancel both scheduler and API tasks
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass

        if self.api_task:
            self.api_task.cancel()
            try:
                await self.api_task
            except asyncio.CancelledError:
                pass

        # Wait for in-flight pulses (30-second grace period)
        if self.executing_pulses:
            pulse_count = len(self.executing_pulses)
            self.logger.info(f"Waiting for {pulse_count} in-flight pulses to complete...")

            try:
                # Use gather with return_exceptions=True to wait for all tasks
                await asyncio.wait_for(
                    asyncio.gather(*self.executing_pulses, return_exceptions=True),
                    timeout=30.0,
                )
                self.logger.info("All in-flight pulses completed successfully")
            except asyncio.TimeoutError:
                # Timeout exceeded - force cancel remaining tasks
                self.logger.warning(
                    f"Timeout after 30s, force cancelling {len(self.executing_pulses)} tasks"
                )
                for task in self.executing_pulses:
                    task.cancel()

        # Close database connection
        await self.queue.close()

        # Signal shutdown complete
        self.shutdown_event.set()
        self.logger.info("Shutdown complete")

    async def start(self) -> None:
        """
        Start the daemon (blocks until shutdown).

        This is the main entry point for the daemon. It:
        1. Initializes the database
        2. Registers signal handlers
        3. Starts both the scheduler loop and API server concurrently
        4. Waits for shutdown signal

        Both the scheduler and API server run concurrently, allowing:
        - Scheduler: Polls for due pulses and executes them
        - API: Accepts external pulse triggers via HTTP

        This method blocks until shutdown is triggered.
        """
        self.logger.info("Starting Pulse Daemon...")
        self.running = True

        # Initialize database
        await self.queue.initialize()

        self.logger.info(f"Max concurrent pulses: {self.max_concurrent}")

        # Register signal handlers for graceful shutdown
        self._register_signal_handlers()

        # Start both scheduler loop and API server concurrently
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.api_task = asyncio.create_task(self._run_api_server())

        # Wait for shutdown
        await self.shutdown_event.wait()

        self.logger.info("Pulse Daemon stopped")
