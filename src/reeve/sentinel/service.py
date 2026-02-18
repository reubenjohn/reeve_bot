"""Sentinel alert service with deduplication."""

import logging
import os
import re
import time
from pathlib import Path

from reeve.sentinel.backends.base import AlertBackend

logger = logging.getLogger("reeve.sentinel")

# Default state directory for cooldown files
_DEFAULT_STATE_DIR = Path(os.environ.get("REEVE_HOME", Path.home() / ".reeve")) / "sentinel"


class SentinelService:
    """Alert service with cooldown-based deduplication.

    Wraps an AlertBackend with optional cooldown logic to prevent
    spamming the user with repeated alerts for the same issue.

    Cooldown uses touch files — file mtime is the last alert timestamp.
    """

    def __init__(self, backend: AlertBackend, state_dir: Path | None = None):
        self.backend = backend
        self.state_dir = state_dir or _DEFAULT_STATE_DIR

    def alert(
        self,
        message: str,
        *,
        cooldown_key: str | None = None,
        cooldown_seconds: int = 1800,
    ) -> bool:
        """Send an alert with optional deduplication.

        Args:
            message: The alert message to send.
            cooldown_key: If provided, deduplicate alerts with this key.
                Alerts with the same key are suppressed within cooldown_seconds.
            cooldown_seconds: Minimum seconds between alerts with the same key.
                Default: 1800 (30 minutes).

        Returns:
            True if alert was sent, False if suppressed by cooldown or failed.
        """
        if cooldown_key and not self._cooldown_expired(cooldown_key, cooldown_seconds):
            logger.debug(f"Alert suppressed by cooldown: {cooldown_key}")
            return False

        success = self.backend.send(message)

        if success and cooldown_key:
            self._touch_cooldown(cooldown_key)

        return success

    def _cooldown_path(self, key: str) -> Path:
        """Get the cooldown touch file path for a key."""
        # Sanitize key for filesystem safety
        safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
        return self.state_dir / f".cooldown_{safe_key}"

    def _cooldown_expired(self, key: str, cooldown_seconds: int) -> bool:
        """Check if enough time has elapsed since last alert with this key."""
        path = self._cooldown_path(key)
        try:
            if not path.exists():
                return True
            age = time.time() - path.stat().st_mtime
            return age >= cooldown_seconds
        except OSError:
            # If we can't read the file, allow the alert
            return True

    def _touch_cooldown(self, key: str) -> None:
        """Update the cooldown timestamp for a key."""
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            path = self._cooldown_path(key)
            path.touch()
        except OSError as e:
            logger.warning(f"Failed to update cooldown for {key}: {e}")
