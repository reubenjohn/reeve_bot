"""
Configuration Management for Reeve Bot

Loads configuration from environment variables with sensible defaults.
Handles path expansion and database URL construction.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file from project root (if it exists)
# This should run once when the module is imported
_project_root = Path(
    __file__
).parent.parent.parent.parent  # reeve/utils -> src/reeve/utils -> src -> project root
_env_path = _project_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


def expand_path(path: str) -> str:
    """
    Expand user home directory (~) and environment variables in a path.

    Args:
        path: Path string potentially containing ~ or $VAR

    Returns:
        Fully expanded absolute path
    """
    return str(Path(os.path.expandvars(os.path.expanduser(path))).resolve())


class ReeveConfig:
    """
    Central configuration for Reeve Bot.

    Loads settings from environment variables with fallback defaults.
    All paths are automatically expanded (~ and environment variables).
    """

    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        # Core paths
        self.reeve_desk_path: str = expand_path(os.getenv("REEVE_DESK_PATH", "~/reeve_desk"))
        self.reeve_home: str = expand_path(os.getenv("REEVE_HOME", "~/.reeve"))

        # Database configuration
        default_db_path = os.path.join(self.reeve_home, "pulse_queue.db")
        db_url_env = os.getenv("PULSE_DB_URL")

        if db_url_env:
            # If user provided PULSE_DB_URL, use it (may contain ~ or $VAR)
            if ":///" in db_url_env:
                # Extract path from URL and expand it
                parts = db_url_env.split(":///")
                if len(parts) == 2:
                    prefix, path_part = parts
                    expanded_path = expand_path(path_part)
                    self.pulse_db_url = f"{prefix}:///{expanded_path}"
                else:
                    self.pulse_db_url = db_url_env
            else:
                self.pulse_db_url = db_url_env
        else:
            # Default: async SQLite in ~/.reeve/pulse_queue.db
            self.pulse_db_url = f"sqlite+aiosqlite:///{default_db_path}"

        # API configuration
        self.pulse_api_port: int = int(os.getenv("PULSE_API_PORT", "8765"))
        self.pulse_api_token: Optional[str] = os.getenv("PULSE_API_TOKEN")

        # Telegram configuration (Phase 7)
        self.telegram_bot_token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")
        self.pulse_api_url: str = os.getenv("PULSE_API_URL", "http://localhost:8765")

        # Hapi/Claude Code command
        self.hapi_command: str = os.getenv("HAPI_COMMAND", "hapi")

        # Ensure reeve_home directory exists
        Path(self.reeve_home).mkdir(parents=True, exist_ok=True)

    @property
    def sync_db_url(self) -> str:
        """
        Get synchronous database URL (for Alembic migrations).

        Converts async URL (sqlite+aiosqlite:///) to sync (sqlite:///)

        Returns:
            Synchronous SQLAlchemy database URL
        """
        return self.pulse_db_url.replace("sqlite+aiosqlite:///", "sqlite:///")

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<ReeveConfig(\n"
            f"  reeve_desk_path={self.reeve_desk_path},\n"
            f"  reeve_home={self.reeve_home},\n"
            f"  pulse_db_url={self.pulse_db_url},\n"
            f"  pulse_api_port={self.pulse_api_port},\n"
            f"  hapi_command={self.hapi_command}\n"
            f")>"
        )


# Global configuration instance
_config: Optional[ReeveConfig] = None


def get_config() -> ReeveConfig:
    """
    Get the global configuration instance (singleton pattern).

    Returns:
        The global ReeveConfig instance

    Example:
        >>> from reeve.utils.config import get_config
        >>> config = get_config()
        >>> print(config.pulse_db_url)
        sqlite+aiosqlite:///~/.reeve/pulse_queue.db
    """
    global _config
    if _config is None:
        _config = ReeveConfig()
    return _config


def reload_config() -> ReeveConfig:
    """
    Force reload of configuration from environment variables.

    Useful for testing or when environment changes at runtime.

    Returns:
        Newly created ReeveConfig instance
    """
    global _config
    _config = ReeveConfig()
    return _config
