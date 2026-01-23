"""
Logging configuration for Reeve daemon.

Provides structured logging with file rotation and optional console output.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_file: str | None = None,
    console: bool = True,
) -> None:
    """
    Setup structured logging with file rotation and console output.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional). If provided, enables file logging
                  with rotation (10MB max, 5 backups)
        console: Whether to output logs to console (default: True)

    Example:
        >>> setup_logging(log_level="INFO", log_file="~/.reeve/logs/daemon.log")
        >>> logger = logging.getLogger("reeve.daemon")
        >>> logger.info("Daemon started")
    """
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Format: "2026-01-20 15:30:45 | INFO     | reeve.daemon | Scheduler started"
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_file:
        # Expand user home and environment variables
        log_path = Path(log_file).expanduser()

        # Create log directory if doesn't exist
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # RotatingFileHandler: 10MB max, 5 backups
        file_handler = RotatingFileHandler(
            log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"  # 10MB
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Log initial setup message
    logger = logging.getLogger("reeve.logging")
    logger.debug(f"Logging configured: level={log_level}, file={log_file}, console={console}")
