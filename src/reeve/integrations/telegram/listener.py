"""
Telegram Listener - Async polling-based integration for external pulse triggers.

This listener polls Telegram Bot API for incoming messages and converts them
to pulses via the HTTP API server. It handles:
- Async polling with long timeouts (100s)
- Offset persistence to prevent duplicate processing
- Error recovery with exponential backoff
- Graceful shutdown on SIGTERM/SIGINT
- Chat ID filtering (only processes authorized user's messages)

Environment Variables:
    TELEGRAM_BOT_TOKEN: Bot token from @BotFather (required)
    TELEGRAM_CHAT_ID: User's chat ID (required)
    PULSE_API_URL: API server URL (default: http://127.0.0.1:8765)
    PULSE_API_TOKEN: Bearer token for API authentication (required)

Usage:
    from reeve.integrations.telegram.listener import TelegramListener
    from reeve.utils.config import get_config

    config = get_config()
    listener = TelegramListener(config)
    await listener.start()  # Blocks until shutdown
"""

import asyncio
import json
import logging
import os
import signal
from pathlib import Path
from typing import Any, Callable, Optional

import aiohttp

from reeve.utils.config import ReeveConfig


class TelegramListener:
    """
    Production Telegram listener with async polling.

    This listener continuously polls the Telegram Bot API for incoming messages
    and triggers pulses via the HTTP API server. It maintains offset state on
    disk to prevent duplicate processing across restarts.

    Key features:
    - Long polling (100s timeout) for efficient resource usage
    - Exponential backoff on errors (up to 5 minutes)
    - Atomic offset persistence (write to temp file + rename)
    - Chat ID filtering (only processes authorized user)
    - Graceful shutdown with signal handlers
    """

    def __init__(self, config: ReeveConfig):
        """
        Initialize Telegram listener.

        Args:
            config: ReeveConfig instance with Telegram credentials

        Raises:
            ValueError: If required environment variables are missing
        """
        # Load configuration from environment
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.api_url = os.getenv("PULSE_API_URL", "http://127.0.0.1:8765")
        self.api_token = config.pulse_api_token

        # Validate required config
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID environment variable is required")
        if not self.api_token:
            raise ValueError(
                "PULSE_API_TOKEN environment variable is required for API authentication"
            )

        # HTTP sessions (initialized in start())
        self.telegram_session: Optional[aiohttp.ClientSession] = None
        self.api_session: Optional[aiohttp.ClientSession] = None

        # State
        self.running = False
        self.shutdown_event = asyncio.Event()
        self.last_update_id: Optional[int] = None
        self.offset_file = Path(config.reeve_home) / "telegram_offset.txt"

        # Error handling
        self.error_count = 0
        self.max_consecutive_errors = 10

        # Logging
        self.logger = logging.getLogger("reeve.telegram")

    async def start(self) -> None:
        """
        Start the Telegram listener (blocks until shutdown).

        This is the main entry point. It:
        1. Initializes HTTP sessions
        2. Loads offset from disk
        3. Verifies bot token by calling Telegram getMe
        4. Registers signal handlers for graceful shutdown
        5. Starts polling loop
        6. Blocks until shutdown signal

        This method will run indefinitely until a shutdown signal is received
        (SIGTERM, SIGINT) or a fatal error occurs.
        """
        self.logger.info("Starting Telegram listener...")
        self.running = True

        try:
            # Initialize HTTP sessions
            self.telegram_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)  # 120s for long polling
            )
            self.api_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)  # 30s for API calls
            )

            # Load offset from disk
            self.last_update_id = self._load_offset()
            if self.last_update_id:
                self.logger.info(f"Loaded offset from disk: {self.last_update_id}")
            else:
                self.logger.info("No offset found, starting fresh")

            # Verify bot token by calling getMe
            await self._verify_bot_token()

            # Register signal handlers
            self._register_signal_handlers()

            # Start polling loop (blocks until shutdown)
            await self._polling_loop()

        finally:
            # Cleanup
            if self.telegram_session:
                await self.telegram_session.close()
            if self.api_session:
                await self.api_session.close()

            self.logger.info("Telegram listener stopped")

    async def _verify_bot_token(self) -> None:
        """
        Verify bot token by calling Telegram getMe endpoint.

        Raises:
            RuntimeError: If bot token is invalid or API is unreachable
        """
        url = f"https://api.telegram.org/bot{self.bot_token}/getMe"

        try:
            assert self.telegram_session is not None
            async with self.telegram_session.get(url) as response:
                data = await response.json()

                if not data.get("ok"):
                    error_msg = data.get("description", "Unknown error")
                    raise RuntimeError(f"Bot token verification failed: {error_msg}")

                bot_info = data["result"]
                self.logger.info(
                    f"Bot verified: @{bot_info.get('username')} ({bot_info.get('first_name')})"
                )

        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to connect to Telegram API: {e}")

    async def _polling_loop(self) -> None:
        """
        Main polling loop: continuously fetch updates from Telegram.

        The loop:
        1. Calls getUpdates with long polling (100s timeout)
        2. Processes each update via _process_update()
        3. Saves offset after successful batch
        4. Sleeps 1 second between batches
        5. Handles errors with exponential backoff

        This loop runs until self.running is set to False (via signal handler).
        """
        self.logger.info("Polling loop started")

        while self.running:
            try:
                # Fetch updates with long polling
                updates_data = await self._get_updates()

                if updates_data and updates_data.get("ok"):
                    updates = updates_data.get("result", [])

                    # Process each update
                    for update in updates:
                        try:
                            await self._process_update(update)

                            # Update offset (always move to next update)
                            self.last_update_id = update["update_id"] + 1

                        except Exception as e:
                            self.logger.error(
                                f"Error processing update {update.get('update_id')}: {e}",
                                exc_info=True,
                            )
                            # Continue to next update even if one fails

                    # Save offset after successful batch
                    if updates and self.last_update_id is not None:
                        self._save_offset(self.last_update_id)
                        self.logger.debug(f"Processed {len(updates)} updates")

                    # Reset error count on success
                    self.error_count = 0

                # Sleep 1 second between polling cycles
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                # Shutdown requested
                self.logger.info("Polling loop cancelled, shutting down")
                break

            except Exception as e:
                # Handle error with exponential backoff
                await self._handle_error(e, "polling loop")

        self.logger.info("Polling loop stopped")

    async def _get_updates(self) -> Optional[dict[str, Any]]:
        """
        Poll Telegram Bot API for new updates.

        Uses long polling with 100-second timeout for efficient resource usage.
        The timeout is server-side, so this call will block for up to 100 seconds
        waiting for new messages.

        Returns:
            JSON response from Telegram API, or None on error

        API Response Format:
            {
                "ok": true,
                "result": [
                    {
                        "update_id": 123456,
                        "message": {
                            "message_id": 789,
                            "from": {"id": 12345, "first_name": "Alice"},
                            "chat": {"id": 12345},
                            "text": "Hello Reeve"
                        }
                    }
                ]
            }
        """
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        params = {
            "timeout": 100,  # Long polling: wait up to 100s for new messages
        }

        # Include offset if we have one (to acknowledge processed messages)
        if self.last_update_id is not None:
            params["offset"] = self.last_update_id

        try:
            assert self.telegram_session is not None
            async with self.telegram_session.get(url, params=params) as response:
                # Handle HTTP errors
                if response.status == 401:
                    raise RuntimeError("Invalid bot token (401 Unauthorized)")
                elif response.status == 404:
                    raise RuntimeError("Bot not found (404 Not Found)")
                elif response.status >= 500:
                    self.logger.warning(f"Telegram API error: {response.status}")
                    return None

                # Parse JSON response
                result: dict[str, Any] = await response.json()
                return result

        except aiohttp.ClientError as e:
            self.logger.warning(f"Network error polling Telegram: {e}")
            return None

        except asyncio.TimeoutError:
            # Timeout is expected with long polling - not an error
            self.logger.debug("Polling timeout (no new messages)")
            return None

    async def _process_update(self, update: dict) -> None:
        """
        Process a single Telegram update.

        This method:
        1. Extracts the message from update
        2. Filters by chat ID (only process authorized user)
        3. Skips non-text messages (photos, stickers, etc.)
        4. Builds a prompt from the message text
        5. Triggers a pulse via the HTTP API

        Args:
            update: Single update dict from Telegram API

        Update Format:
            {
                "update_id": 123456,
                "message": {
                    "message_id": 789,
                    "from": {"id": 12345, "first_name": "Alice"},
                    "chat": {"id": 12345, "type": "private"},
                    "date": 1234567890,
                    "text": "Hello Reeve"
                }
            }
        """
        # Extract message
        message = update.get("message")
        if not message:
            self.logger.debug(f"Update {update.get('update_id')} has no message, skipping")
            return

        # Filter by chat ID (only process authorized user's messages)
        chat_id = str(message.get("chat", {}).get("id"))
        if chat_id != self.chat_id:
            self.logger.warning(
                f"Ignoring message from unauthorized chat: {chat_id} (expected: {self.chat_id})"
            )
            return

        # Skip non-text messages
        text = message.get("text")
        if not text:
            self.logger.debug("Skipping non-text message (photo, sticker, etc.)")
            return

        # Extract user info
        user_first_name = message.get("from", {}).get("first_name", "User")
        user_username = message.get("from", {}).get("username")
        user_display = f"{user_first_name}"
        if user_username:
            user_display += f" (@{user_username})"

        # Build prompt
        prompt = f"Telegram message from {user_display}: {text}"

        self.logger.info(f"Received message: {text[:50]}...")

        # Trigger pulse via API
        pulse_id = await self._trigger_pulse(prompt, user_display)

        if pulse_id:
            self.logger.info(f"Triggered pulse {pulse_id} for message from {user_display}")
        else:
            self.logger.error(f"Failed to trigger pulse for message from {user_display}")

    async def _trigger_pulse(self, prompt: str, user: str) -> Optional[int]:
        """
        Trigger a pulse via the HTTP API server.

        This method sends a POST request to the /api/pulse/schedule endpoint
        with the provided prompt and metadata.

        Args:
            prompt: The full prompt to pass to Reeve (includes user attribution)
            user: User display name for logging (e.g., "Alice (@alice123)")

        Returns:
            The pulse ID if successful, None if failed

        API Request:
            POST /api/pulse/schedule
            Headers: Authorization: Bearer <token>
            Body: {
                "prompt": "Telegram message from Alice: hello",
                "scheduled_at": "now",
                "priority": "critical",
                "source": "telegram",
                "tags": ["telegram", "user_message"]
            }

        API Response:
            {
                "pulse_id": 123,
                "scheduled_at": "2026-01-23T12:34:56Z",
                "message": "Pulse scheduled successfully"
            }
        """
        url = f"{self.api_url}/api/pulse/schedule"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": prompt,
            "scheduled_at": "now",
            "priority": "critical",  # User messages are always critical priority
            "source": "telegram",
            "tags": ["telegram", "user_message"],
        }

        try:
            assert self.api_session is not None
            async with self.api_session.post(url, headers=headers, json=payload) as response:
                # Handle authentication errors
                if response.status == 401:
                    self.logger.error("API authentication failed (invalid token)")
                    return None

                # Handle other HTTP errors
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"API error {response.status}: {error_text[:100]}")
                    return None

                # Parse response
                data: dict[str, Any] = await response.json()
                pulse_id = data.get("pulse_id")
                return int(pulse_id) if pulse_id is not None else None

        except aiohttp.ClientError as e:
            self.logger.error(f"Network error triggering pulse: {e}")
            return None

        except Exception as e:
            self.logger.error(f"Unexpected error triggering pulse: {e}", exc_info=True)
            return None

    def _load_offset(self) -> Optional[int]:
        """
        Load last processed update ID from disk.

        The offset file stores a single integer representing the last processed
        update_id. On startup, we read this file to resume where we left off.

        Returns:
            Last processed update ID, or None if file doesn't exist or is invalid

        File Format:
            Plain text file containing a single integer: "123456\\n"
        """
        if not self.offset_file.exists():
            return None

        try:
            content = self.offset_file.read_text().strip()
            if not content:
                return None

            offset = int(content)
            return offset

        except (ValueError, IOError) as e:
            self.logger.warning(f"Failed to load offset from {self.offset_file}: {e}")
            return None

    def _save_offset(self, offset: int) -> None:
        """
        Save current offset to disk (atomic write).

        Uses atomic write pattern (write to temp file + rename) to prevent
        corruption if the process is killed mid-write.

        Args:
            offset: Update ID to save (typically last_update_id)

        File Format:
            Plain text file containing a single integer: "123456\\n"
        """
        try:
            # Atomic write: write to temp file, then rename
            temp_file = self.offset_file.with_suffix(".tmp")
            temp_file.write_text(f"{offset}\n")
            temp_file.replace(self.offset_file)

            self.logger.debug(f"Saved offset: {offset}")

        except IOError as e:
            self.logger.error(f"Failed to save offset to {self.offset_file}: {e}")

    async def _handle_error(self, error: Exception, context: str) -> None:
        """
        Handle errors with exponential backoff and fatal error detection.

        This method:
        1. Increments error count
        2. Checks for fatal errors (auth failure, max retries)
        3. Calculates exponential backoff (up to 5 minutes)
        4. Logs error with full traceback
        5. Sleeps for backoff duration

        Args:
            error: The exception that occurred
            context: Description of where the error occurred (for logging)

        Backoff Calculation:
            backoff = min(2^error_count, 300)
            Examples:
                1st error: 2s
                2nd error: 4s
                3rd error: 8s
                4th error: 16s
                5th error: 32s
                6th error: 64s
                7th error: 128s
                8th error: 256s
                9th+ error: 300s (5 minutes)
        """
        self.error_count += 1

        # Check for fatal errors
        if isinstance(error, RuntimeError) and "token" in str(error).lower():
            # Authentication failure - fatal error
            self.logger.critical(f"Fatal error in {context}: {error}")
            self.logger.critical("Bot token is invalid. Shutting down...")
            self.running = False
            self.shutdown_event.set()
            return

        if self.error_count >= self.max_consecutive_errors:
            # Max retries exceeded - fatal error
            self.logger.critical(
                f"Max consecutive errors ({self.max_consecutive_errors}) exceeded. Shutting down..."
            )
            self.running = False
            self.shutdown_event.set()
            return

        # Calculate exponential backoff (max 5 minutes)
        backoff_seconds = min(2**self.error_count, 300)

        self.logger.error(
            f"Error in {context} (attempt {self.error_count}/{self.max_consecutive_errors}): {error}",
            exc_info=True,
        )
        self.logger.info(f"Backing off for {backoff_seconds}s before retry...")

        # Sleep for backoff duration
        await asyncio.sleep(backoff_seconds)

    def _register_signal_handlers(self) -> None:
        """
        Register SIGTERM and SIGINT handlers for graceful shutdown.

        This allows the listener to be stopped cleanly via:
        - Ctrl+C (SIGINT)
        - systemctl stop (SIGTERM)
        - kill <pid> (SIGTERM)

        The handlers set self.running to False, which causes the polling loop
        to exit gracefully.
        """
        loop = asyncio.get_event_loop()

        def create_handler(s: signal.Signals) -> "Callable[[], None]":
            def handler() -> None:
                asyncio.create_task(self._handle_shutdown(s))

            return handler

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, create_handler(sig))

        self.logger.info("Signal handlers registered (SIGTERM, SIGINT)")

    async def _handle_shutdown(self, sig: signal.Signals) -> None:
        """
        Handle graceful shutdown.

        Shutdown process:
        1. Log shutdown signal
        2. Stop polling loop (self.running = False)
        3. Save current offset to disk
        4. Close HTTP sessions (handled in start() finally block)
        5. Signal shutdown complete

        Args:
            sig: The signal that triggered shutdown (SIGTERM or SIGINT)
        """
        self.logger.info(f"Received {sig.name}, shutting down gracefully...")

        # Stop polling loop
        self.running = False

        # Save offset to disk
        if self.last_update_id is not None:
            self._save_offset(self.last_update_id)
            self.logger.info(f"Saved final offset: {self.last_update_id}")

        # Signal shutdown complete
        self.shutdown_event.set()

        self.logger.info("Shutdown complete")
