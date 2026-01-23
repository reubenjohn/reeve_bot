"""
Entry point for running the Pulse Daemon as a module.

Usage:
    # Development
    python -m reeve.pulse

    # With custom log level
    LOG_LEVEL=DEBUG python -m reeve.pulse
"""

import asyncio
import logging
import sys

from reeve.pulse.daemon import PulseDaemon
from reeve.utils.config import get_config
from reeve.utils.logging import setup_logging


async def async_main() -> None:
    """Async entry point for the daemon."""
    # Load configuration
    config = get_config()

    # Setup logging (console + file)
    log_file = f"{config.reeve_home}/logs/daemon.log"
    setup_logging(log_level="INFO", log_file=log_file, console=True)

    # Log startup information
    logger = logging.getLogger("reeve.main")
    logger.info("=" * 60)
    logger.info("Starting Reeve Pulse Daemon")
    logger.info("=" * 60)
    logger.info(f"Database: {config.pulse_db_url}")
    logger.info(f"Desk: {config.reeve_desk_path}")
    logger.info(f"Hapi: {config.hapi_command}")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 60)

    # Create and start daemon
    daemon = PulseDaemon(config)

    try:
        await daemon.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Reeve Pulse Daemon stopped")


def main() -> None:
    """Synchronous entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        # Graceful exit on Ctrl+C (SIGINT is already handled by daemon)
        pass


if __name__ == "__main__":
    main()
