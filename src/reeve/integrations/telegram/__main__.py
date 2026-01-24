"""
Entry point for Telegram Listener.

Usage:
    python -m reeve.integrations.telegram
    LOG_LEVEL=DEBUG python -m reeve.integrations.telegram
"""

import asyncio
import logging
import sys

from reeve.integrations.telegram.listener import TelegramListener
from reeve.utils.config import get_config
from reeve.utils.logging import setup_logging


async def async_main() -> None:
    """Async entry point."""
    # Load config
    config = get_config()

    # Validate required fields
    if not config.telegram_bot_token:
        print("ERROR: TELEGRAM_BOT_TOKEN environment variable is required", file=sys.stderr)
        print("Please set it in your .env file or export it:", file=sys.stderr)
        print("  export TELEGRAM_BOT_TOKEN=your_bot_token_here", file=sys.stderr)
        sys.exit(1)

    if not config.telegram_chat_id:
        print("ERROR: TELEGRAM_CHAT_ID environment variable is required", file=sys.stderr)
        print("Please set it in your .env file or export it:", file=sys.stderr)
        print("  export TELEGRAM_CHAT_ID=your_chat_id_here", file=sys.stderr)
        sys.exit(1)

    if not config.pulse_api_token:
        print("ERROR: PULSE_API_TOKEN environment variable is required", file=sys.stderr)
        print("Please set it in your .env file or export it:", file=sys.stderr)
        print("  export PULSE_API_TOKEN=your_secret_token", file=sys.stderr)
        sys.exit(1)

    # Setup logging (console + file)
    log_file = f"{config.reeve_home}/logs/telegram_listener.log"
    setup_logging(log_level="INFO", log_file=log_file, console=True)

    # Log startup info
    logger = logging.getLogger("reeve.telegram")
    logger.info("=" * 60)
    logger.info("Starting Telegram Listener")
    logger.info("=" * 60)
    logger.info(f"API URL: {config.pulse_api_url}")
    logger.info(f"Chat ID: {config.telegram_chat_id}")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 60)

    # Create and start listener
    listener = TelegramListener(config)

    try:
        await listener.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Telegram Listener stopped")


def main() -> None:
    """Sync entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass  # Graceful exit (SIGINT handled by listener)


if __name__ == "__main__":
    main()
