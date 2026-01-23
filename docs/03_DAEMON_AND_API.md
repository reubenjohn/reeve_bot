# Pulse Daemon and HTTP API

## Overview

The Pulse Daemon is the long-running process that powers Reeve's proactive behavior. It runs continuously in the background, managing three concurrent services:

1. **Pulse Scheduler**: Checks for due pulses every second and executes them
2. **HTTP API**: Accepts external pulse triggers (Telegram, Email, etc.)
3. **MCP Servers**: Spawned on-demand when Reeve needs to interact with the queue

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Pulse Daemon Process                   │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  Scheduler  │  │  HTTP API   │  │ MCP Servers │   │
│  │   Loop      │  │  (FastAPI)  │  │  (stdio)    │   │
│  │             │  │             │  │             │   │
│  │  Every 1s:  │  │ POST /pulse │  │ On-demand:  │   │
│  │  - Query DB │  │ GET /status │  │ - Started   │   │
│  │  - Execute  │  │ GET /health │  │   by Reeve  │   │
│  │    pulses   │  │             │  │ - stdio I/O │   │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘   │
│         │                │                            │
│         └────────────────┴───────────┐                │
│                                      ▼                │
│                              ┌───────────────┐        │
│                              │ PulseQueue    │        │
│                              │ (SQLAlchemy)  │        │
│                              └───────┬───────┘        │
└──────────────────────────────────────┼────────────────┘
                                       ▼
                                ┌─────────────┐
                                │  SQLite DB  │
                                └─────────────┘
```

## Daemon Implementation

**Module**: `src/reeve/pulse/daemon.py`

```python
"""
Pulse Daemon - Main entry point for the long-running background process.

This daemon runs three concurrent asyncio tasks:
1. Pulse scheduler (checks queue every 1 second)
2. HTTP API server (FastAPI on port 8765)
3. Signal handlers (graceful shutdown)

Usage:
    # Development
    uv run python -m reeve.pulse

    # Production (via systemd)
    systemctl start reeve-daemon
"""

import asyncio
import signal
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

from reeve.pulse.queue import PulseQueue
from reeve.pulse.executor import PulseExecutor
from reeve.pulse.enums import PulseStatus
from reeve.api.server import create_api_server
from reeve.utils.config import load_config
from reeve.utils.logging import setup_logging


class PulseDaemon:
    """
    Main daemon process that orchestrates pulse execution and API serving.
    """

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger("reeve.daemon")

        # Initialize components
        self.queue = PulseQueue(config["database_url"])
        self.executor = PulseExecutor(config["hapi_command"], config["desk_path"])

        # State
        self.running = False
        self.scheduler_task = None
        self.api_task = None

    async def start(self):
        """Start all daemon services."""
        self.logger.info("Starting Pulse Daemon...")
        self.running = True

        # Setup signal handlers for graceful shutdown
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)

        # Start concurrent tasks
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.api_task = asyncio.create_task(self._run_api_server())

        self.logger.info("Pulse Daemon started successfully")

        # Wait for shutdown signal
        await asyncio.gather(
            self.scheduler_task,
            self.api_task,
            return_exceptions=True
        )

    async def _scheduler_loop(self):
        """
        Main scheduler loop: check for due pulses every second and execute them.
        """
        self.logger.info("Scheduler loop started")

        while self.running:
            try:
                # Get due pulses (up to 10 at a time)
                pulses = await self.queue.get_due_pulses(limit=10)

                # Execute each pulse
                for pulse in pulses:
                    self.logger.info(
                        f"Executing pulse {pulse.id}: {pulse.prompt[:50]}..."
                    )

                    # Mark as processing
                    success = await self.queue.mark_processing(pulse.id)
                    if not success:
                        self.logger.warning(
                            f"Pulse {pulse.id} already processing/completed, skipping"
                        )
                        continue

                    # Execute pulse (async, non-blocking)
                    asyncio.create_task(self._execute_pulse(pulse))

                # Sleep 1 second before next check
                await asyncio.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Back off on error

    async def _execute_pulse(self, pulse):
        """
        Execute a single pulse by launching a Hapi session.

        Args:
            pulse: The Pulse model instance to execute
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Build the full prompt (including sticky notes)
            full_prompt = self._build_prompt(pulse)

            # Execute via PulseExecutor
            result = await self.executor.execute(
                prompt=full_prompt,
                session_id=pulse.session_id,
                working_dir=self.config["desk_path"]
            )

            # Calculate duration
            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )

            # Mark as completed
            await self.queue.mark_completed(pulse.id, duration_ms)

            self.logger.info(
                f"Pulse {pulse.id} completed successfully in {duration_ms}ms"
            )

        except Exception as e:
            self.logger.error(f"Pulse {pulse.id} failed: {e}", exc_info=True)

            # Mark as failed (will auto-retry if retries remaining)
            retry_pulse_id = await self.queue.mark_failed(
                pulse.id,
                error_message=str(e),
                should_retry=True
            )

            if retry_pulse_id:
                self.logger.info(
                    f"Pulse {pulse.id} scheduled for retry as pulse {retry_pulse_id}"
                )

    def _build_prompt(self, pulse) -> str:
        """
        Build the full prompt including sticky notes.

        Args:
            pulse: The Pulse model instance

        Returns:
            Full prompt string with formatted sticky notes
        """
        parts = []

        # Add sticky notes if present
        if pulse.sticky_notes:
            parts.append("📌 Reminders:")
            for note in pulse.sticky_notes:
                parts.append(f"  - {note}")
            parts.append("")  # Blank line separator

        # Add main prompt
        parts.append(pulse.prompt)

        return "\n".join(parts)

    async def _run_api_server(self):
        """Run the HTTP API server."""
        app = create_api_server(self.queue, self.config)

        import uvicorn

        config = uvicorn.Config(
            app,
            host=self.config.get("api_host", "127.0.0.1"),
            port=self.config.get("api_port", 8765),
            log_level="info"
        )

        server = uvicorn.Server(config)
        await server.serve()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

        # Cancel tasks
        if self.scheduler_task:
            self.scheduler_task.cancel()
        if self.api_task:
            self.api_task.cancel()


async def main():
    """Entry point for the daemon."""
    # Load configuration
    config = load_config()

    # Setup logging
    setup_logging(config.get("log_level", "INFO"), config.get("log_file"))

    # Start daemon
    daemon = PulseDaemon(config)
    await daemon.start()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Pulse Executor

**Module**: `src/reeve/pulse/executor.py`

```python
"""
Pulse Executor - Launches Hapi sessions to execute pulses.

This module handles the actual execution of pulses by spawning Hapi/Claude Code
sessions with the pulse's prompt as the initial context.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional


class PulseExecutor:
    """
    Executes pulses by launching Hapi sessions.
    """

    def __init__(self, hapi_command: str, desk_path: str):
        """
        Initialize the executor.

        Args:
            hapi_command: Path to Hapi executable (e.g., "hapi", "/usr/local/bin/hapi")
            desk_path: Path to the user's Desk directory (working directory for Hapi)
        """
        self.hapi_command = hapi_command
        self.desk_path = Path(desk_path).expanduser()
        self.logger = logging.getLogger("reeve.executor")

    async def execute(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        working_dir: Optional[str] = None
    ) -> dict:
        """
        Execute a pulse by launching a Hapi session.

        Args:
            prompt: The instruction/context for Reeve
            session_id: Optional session ID to resume
            working_dir: Override working directory (defaults to desk_path)

        Returns:
            Execution result dict with stdout, stderr, return_code

        Raises:
            RuntimeError: If Hapi execution fails
        """
        cwd = Path(working_dir).expanduser() if working_dir else self.desk_path

        # Build Hapi command
        cmd = [self.hapi_command, "run"]

        # Add session resume flag if provided
        if session_id:
            cmd.extend(["--resume", session_id])

        # Add prompt
        cmd.extend(["--text", prompt])

        self.logger.debug(f"Executing: {' '.join(cmd)} (cwd: {cwd})")

        # Execute Hapi as subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait for completion
        stdout, stderr = await process.communicate()

        result = {
            "stdout": stdout.decode("utf-8"),
            "stderr": stderr.decode("utf-8"),
            "return_code": process.returncode
        }

        # Check for errors
        if process.returncode != 0:
            raise RuntimeError(
                f"Hapi execution failed (exit code {process.returncode}): {result['stderr']}"
            )

        return result
```

---

## HTTP API Server

**Module**: `src/reeve/api/server.py`

```python
"""
HTTP API Server - REST endpoints for external pulse triggers.

This API allows external systems (Telegram listeners, webhooks, etc.) to
trigger pulses without using the MCP protocol.

Endpoints:
    POST /api/pulse/trigger - Create a new pulse
    GET  /api/pulse/upcoming - List upcoming pulses
    GET  /api/health - Health check
    GET  /api/status - Daemon status
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone, timedelta
import os

from reeve.pulse.queue import PulseQueue
from reeve.pulse.enums import PulsePriority


def create_api_server(queue: PulseQueue, config: dict) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        queue: The PulseQueue instance
        config: Daemon configuration

    Returns:
        FastAPI app instance
    """
    app = FastAPI(
        title="Reeve Pulse API",
        description="HTTP API for triggering pulses from external systems",
        version="0.1.0"
    )

    # API Token authentication
    API_TOKEN = config.get("api_token", os.getenv("PULSE_API_TOKEN"))

    async def verify_token(authorization: str = Header(None)):
        """Verify API token from Authorization header."""
        if not API_TOKEN:
            return True  # No token configured, allow all (dev mode)

        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Missing or invalid Authorization header")

        token = authorization.replace("Bearer ", "")
        if token != API_TOKEN:
            raise HTTPException(403, "Invalid API token")

        return True

    # ========================================================================
    # Request/Response Models
    # ========================================================================

    class TriggerPulseRequest(BaseModel):
        """Request body for triggering a pulse."""

        prompt: str = Field(
            ...,
            description="The instruction/context for Reeve",
            min_length=10,
            max_length=2000
        )

        scheduled_at: str = Field(
            default="now",
            description="When to execute: 'now', ISO timestamp, or 'in X minutes/hours'",
            examples=["now", "2026-01-20T09:00:00Z", "in 5 minutes"]
        )

        priority: Literal["critical", "high", "normal", "low", "deferred"] = Field(
            default="high",
            description="Priority level (external events default to 'high')"
        )

        source: str = Field(
            default="external",
            description="Source identifier (e.g., 'telegram', 'email', 'webhook')"
        )

        tags: Optional[list[str]] = Field(
            default=None,
            description="Optional tags for categorization"
        )

    class TriggerPulseResponse(BaseModel):
        """Response after triggering a pulse."""

        pulse_id: int
        scheduled_at: str
        message: str

    # ========================================================================
    # Endpoints
    # ========================================================================

    @app.post("/api/pulse/trigger", response_model=TriggerPulseResponse)
    async def trigger_pulse(
        request: TriggerPulseRequest,
        authorized: bool = Depends(verify_token)
    ):
        """
        Trigger a new pulse (create and schedule).

        This is the primary endpoint for external systems to inject events
        into Reeve's attention queue.

        Example:
            curl -X POST http://localhost:8765/api/pulse/trigger \\
                 -H "Authorization: Bearer your_token_here" \\
                 -H "Content-Type: application/json" \\
                 -d '{
                   "prompt": "Telegram message from Alice: Can we meet tomorrow?",
                   "scheduled_at": "now",
                   "priority": "high",
                   "source": "telegram"
                 }'
        """
        # Parse scheduled_at
        if request.scheduled_at == "now":
            scheduled_at = datetime.now(timezone.utc)
        elif request.scheduled_at.startswith("in "):
            # Simple relative time parsing
            parts = request.scheduled_at[3:].split()
            amount = int(parts[0])
            unit = parts[1].rstrip("s")

            if unit == "minute":
                scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=amount)
            elif unit == "hour":
                scheduled_at = datetime.now(timezone.utc) + timedelta(hours=amount)
            else:
                raise HTTPException(400, f"Unsupported time unit: {unit}")
        else:
            # Assume ISO 8601
            scheduled_at = datetime.fromisoformat(request.scheduled_at.replace("Z", "+00:00"))

        # Create pulse
        pulse_id = await queue.schedule_pulse(
            scheduled_at=scheduled_at,
            prompt=request.prompt,
            priority=PulsePriority(request.priority),
            tags=request.tags,
            created_by=request.source
        )

        return TriggerPulseResponse(
            pulse_id=pulse_id,
            scheduled_at=scheduled_at.isoformat(),
            message=f"Pulse {pulse_id} scheduled successfully"
        )

    @app.get("/api/pulse/upcoming")
    async def list_upcoming(
        limit: int = 20,
        authorized: bool = Depends(verify_token)
    ):
        """List upcoming pulses."""
        pulses = await queue.get_upcoming_pulses(limit=limit)

        return {
            "count": len(pulses),
            "pulses": [
                {
                    "id": p.id,
                    "scheduled_at": p.scheduled_at.isoformat(),
                    "priority": p.priority.value,
                    "prompt": p.prompt[:100] + "..." if len(p.prompt) > 100 else p.prompt,
                    "status": p.status.value,
                }
                for p in pulses
            ]
        }

    @app.get("/api/health")
    async def health_check():
        """Health check endpoint (no auth required)."""
        return {"status": "healthy", "service": "reeve-pulse-daemon"}

    @app.get("/api/status")
    async def daemon_status(authorized: bool = Depends(verify_token)):
        """Daemon status and statistics."""
        # TODO: Add metrics (pulses executed, failures, avg duration)
        return {
            "status": "running",
            "uptime_seconds": 0,  # TODO: Track start time
            "database": config["database_url"],
        }

    return app
```

---

## Configuration Management

**Module**: `src/reeve/utils/config.py`

```python
"""
Configuration management for Pulse Daemon.

Loads configuration from:
1. Environment variables
2. .env file
3. Default values
"""

import os
from pathlib import Path
from typing import Optional


def load_config() -> dict:
    """
    Load daemon configuration.

    Returns:
        Configuration dictionary
    """
    # Load .env file if present
    _load_dotenv()

    return {
        # Database
        "database_url": _get_db_url(),

        # Hapi
        "hapi_command": os.getenv("HAPI_COMMAND", "hapi"),
        "desk_path": os.getenv("REEVE_DESK_PATH", "~/my_reeve"),

        # API
        "api_host": os.getenv("PULSE_API_HOST", "127.0.0.1"),
        "api_port": int(os.getenv("PULSE_API_PORT", "8765")),
        "api_token": os.getenv("PULSE_API_TOKEN"),

        # Logging
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "log_file": os.getenv("LOG_FILE", "~/.reeve/logs/daemon.log"),
    }


def _get_db_url() -> str:
    """Get database URL."""
    db_path = os.getenv("PULSE_DB_PATH", "~/.reeve/pulse_queue.db")
    db_path = Path(db_path).expanduser()

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return f"sqlite+aiosqlite:///{db_path}"


def _load_dotenv():
    """Load .env file from project root."""
    env_file = Path(__file__).parent.parent.parent / ".env"

    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
```

---

## External Integration Example: Telegram Listener

**Updated**: `src/reeve/integrations/telegram.py`

```python
"""
Telegram Integration - Listens for messages and triggers pulses.

This replaces the prototype telegram_prototype/goose_telegram_listener.py
with a production-ready integration that POSTs to the Pulse API.
"""

import time
import requests
import os
from pathlib import Path


class TelegramListener:
    """Polls Telegram for messages and triggers pulses via HTTP API."""

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.api_url = os.getenv("PULSE_API_URL", "http://localhost:8765")
        self.api_token = os.getenv("PULSE_API_TOKEN")

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN required")

    def run(self):
        """Main polling loop."""
        print(f"🤖 Telegram listener started, posting to {self.api_url}")
        last_update_id = None

        while True:
            updates = self._get_updates(last_update_id)

            if updates and "result" in updates:
                for update in updates["result"]:
                    last_update_id = update["update_id"] + 1

                    if "message" in update and "text" in update["message"]:
                        self._handle_message(update["message"])

            time.sleep(1)

    def _get_updates(self, offset=None):
        """Poll Telegram API for updates."""
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        try:
            response = requests.get(url, params={"timeout": 100, "offset": offset})
            return response.json()
        except Exception as e:
            print(f"Error polling Telegram: {e}")
            return None

    def _handle_message(self, message):
        """Trigger a pulse for this message."""
        user = message["from"].get("first_name", "User")
        text = message["text"]

        prompt = f"📩 Telegram message from {user}: {text}"
        print(f"\n{prompt}")

        # POST to Pulse API
        try:
            response = requests.post(
                f"{self.api_url}/api/pulse/trigger",
                headers={"Authorization": f"Bearer {self.api_token}"},
                json={
                    "prompt": prompt,
                    "scheduled_at": "now",
                    "priority": "high",
                    "source": "telegram",
                    "tags": ["telegram", "user_message"]
                },
                timeout=5
            )

            if response.ok:
                result = response.json()
                print(f"✓ Pulse {result['pulse_id']} triggered")
            else:
                print(f"✗ API error: {response.status_code} {response.text}")

        except Exception as e:
            print(f"✗ Failed to trigger pulse: {e}")


if __name__ == "__main__":
    listener = TelegramListener()
    listener.run()
```

---

## Summary

**Daemon** (`daemon.py`):
- Orchestrates scheduler + HTTP API
- Handles graceful shutdown
- Manages pulse execution lifecycle

**Executor** (`executor.py`):
- Launches Hapi sessions
- Injects prompts + sticky notes
- Reports success/failure

**HTTP API** (`server.py`):
- FastAPI endpoints for external triggers
- Token-based authentication
- JSON request/response

**Integration** (`telegram.py`):
- Polls Telegram API
- POSTs to Pulse API
- Simple, stateless design

## Next Steps

See **[04_DEPLOYMENT.md](04_DEPLOYMENT.md)** for systemd setup, monitoring, and production deployment.
