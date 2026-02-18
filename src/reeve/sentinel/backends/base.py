"""Base class for sentinel alert backends."""

from abc import ABC, abstractmethod
from typing import Optional


class AlertBackend(ABC):
    """Abstract base class for alert delivery backends.

    Implementations must:
    - Never raise exceptions from send() — return False on failure
    - Be constructable from environment variables via from_env()
    """

    @abstractmethod
    def send(self, message: str) -> bool:
        """Send an alert message. Returns True on success. Must never raise."""
        ...

    @classmethod
    @abstractmethod
    def from_env(cls) -> Optional["AlertBackend"]:
        """Create backend from environment variables.

        Returns None if required env vars are not configured.
        """
        ...
