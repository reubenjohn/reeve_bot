"""Sentinel alert backend registry."""

import logging
import os
from typing import Optional

from reeve.sentinel.backends.base import AlertBackend
from reeve.sentinel.backends.telegram import TelegramBackend

logger = logging.getLogger("reeve.sentinel.backends")

# Registry of available backends (checked in order for auto-detection)
_BACKENDS: list[tuple[str, type[AlertBackend]]] = [
    ("telegram", TelegramBackend),
]


def get_backend(name: str | None = None) -> AlertBackend | None:
    """Get an alert backend by name, or auto-detect from environment.

    Args:
        name: Backend name (e.g., "telegram"). If None, auto-detect
              from SENTINEL_BACKEND env var or by probing each backend.

    Returns:
        Configured AlertBackend instance, or None if no backend available.
    """
    # Explicit override
    name = name or os.environ.get("SENTINEL_BACKEND")

    if name:
        for backend_name, backend_cls in _BACKENDS:
            if backend_name == name:
                return backend_cls.from_env()
        logger.warning(f"Unknown sentinel backend: {name}")
        return None

    # Auto-detect: try each backend in order
    for backend_name, backend_cls in _BACKENDS:
        backend = backend_cls.from_env()
        if backend is not None:
            logger.debug(f"Auto-detected sentinel backend: {backend_name}")
            return backend

    return None
