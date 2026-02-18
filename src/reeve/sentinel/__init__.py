"""
Sentinel: Failsafe alert system for Reeve.

Sends notifications that bypass the pulse/Hapi system entirely.
Channel-agnostic — auto-detects backend from environment.

Usage from Python:
    from reeve.sentinel import send_alert
    send_alert("Something went wrong")

Usage from CLI:
    python -m reeve.sentinel "Something went wrong"
    python -m reeve.sentinel --cooldown-key pulse_42 "Pulse failed"
"""

import logging

from reeve.sentinel.backends import get_backend
from reeve.sentinel.service import SentinelService

logger = logging.getLogger("reeve.sentinel")


def send_alert(
    message: str,
    *,
    cooldown_key: str | None = None,
    cooldown_seconds: int = 1800,
) -> bool:
    """Send a sentinel alert. Auto-detects backend from environment.

    This is the primary API for sending failsafe alerts. It:
    - Auto-detects the configured backend (Telegram, etc.)
    - Applies cooldown deduplication if cooldown_key is provided
    - Never raises exceptions — returns False on any failure

    Args:
        message: Alert message to send.
        cooldown_key: Optional deduplication key.
        cooldown_seconds: Cooldown period in seconds (default 1800 = 30 min).

    Returns:
        True if alert was sent successfully, False otherwise.
    """
    try:
        backend = get_backend()
        if backend is None:
            logger.warning("No sentinel backend configured — alert not sent")
            return False

        service = SentinelService(backend)
        return service.alert(
            message,
            cooldown_key=cooldown_key,
            cooldown_seconds=cooldown_seconds,
        )
    except Exception as e:
        logger.warning(f"Sentinel alert failed: {e}")
        return False
