"""Telegram alert backend using stdlib urllib."""

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Optional

from reeve.sentinel.backends.base import AlertBackend

logger = logging.getLogger("reeve.sentinel.telegram")


class TelegramBackend(AlertBackend):
    """Send alerts via Telegram Bot API using stdlib urllib.

    Uses only Python stdlib for maximum reliability — works even when
    third-party packages are broken or the async event loop is dead.
    """

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, message: str) -> bool:
        """Send message via Telegram Bot API. Never raises."""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = json.dumps(
                {
                    "chat_id": self.chat_id,
                    "text": message[:4096],  # Telegram limit
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200

        except Exception as e:
            logger.warning(f"Telegram alert failed: {e}")
            return False

    @classmethod
    def from_env(cls) -> Optional["TelegramBackend"]:
        """Create from TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars."""
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if bot_token and chat_id:
            return cls(bot_token, chat_id)
        return None
