"""
Reeve Doctor - Comprehensive system health check.

Usage:
    uv run python -m reeve.doctor

Validates the entire Reeve stack:
- Environment variables
- Database connectivity and migrations
- MCP server configuration
- Desk Claude Code permissions
- Required commands availability
- Service health
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

# Try to load .env file
try:
    from dotenv import load_dotenv

    _project_root = Path(__file__).parent.parent.parent
    _env_path = _project_root / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    # python-dotenv not available, try manual parsing
    _project_root = Path(__file__).parent.parent.parent
    _env_path = _project_root / ".env"
    if _env_path.exists():
        with open(_env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


# Constants
PASS = "\u2713"  # checkmark
FAIL = "\u2717"  # X
WARN = "!"

EXPECTED_MIGRATION = "07ce7ae63b4a"

REQUIRED_PERMISSIONS = [
    "mcp__pulse-queue__schedule_pulse",
    "mcp__pulse-queue__list_upcoming_pulses",
    "mcp__pulse-queue__cancel_pulse",
    "mcp__pulse-queue__reschedule_pulse",
    "mcp__telegram-notifier__send_notification",
]


def expand_path(path: str) -> str:
    """Expand ~ and environment variables in path."""
    return str(Path(os.path.expandvars(os.path.expanduser(path))).resolve())


def extract_db_path(db_url: str) -> Optional[str]:
    """Extract file path from sqlite URL."""
    # Handle sqlite+aiosqlite:///path or sqlite:///path
    if ":///" in db_url:
        _, _, path = db_url.partition(":///")
        return expand_path(path) if path else None
    return None


class Doctor:
    """Comprehensive system health checker for Reeve."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def check(self, condition: bool, message: str, required: bool = True) -> bool:
        """Record a check result."""
        if condition:
            print(f"  {PASS} {message}")
            self.passed += 1
            return True
        elif required:
            print(f"  {FAIL} {message}")
            self.failed += 1
            return False
        else:
            print(f"  {WARN} {message}")
            self.warnings += 1
            return False

    def section(self, title: str) -> None:
        """Print a section header."""
        print(f"\n{title}:")

    def check_environment(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Check environment variables."""
        self.section("Environment")

        # Required variables
        api_token = os.getenv("PULSE_API_TOKEN")
        desk_path = os.getenv("REEVE_DESK_PATH")
        db_url = os.getenv("PULSE_DB_URL")

        self.check(bool(api_token), "PULSE_API_TOKEN set")

        if desk_path:
            expanded_desk = expand_path(desk_path)
            self.check(True, f"REEVE_DESK_PATH={expanded_desk}")
        else:
            self.check(False, "REEVE_DESK_PATH not set")
            expanded_desk = None

        if db_url:
            self.check(True, "PULSE_DB_URL configured")
        else:
            self.check(False, "PULSE_DB_URL not set")

        # Optional variables (warnings only)
        hapi_cmd = os.getenv("HAPI_COMMAND")
        if not hapi_cmd:
            self.check(False, "HAPI_COMMAND not set (using default 'hapi')", required=False)

        api_port = os.getenv("PULSE_API_PORT")
        if not api_port:
            self.check(False, "PULSE_API_PORT not set (using default 8765)", required=False)

        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not telegram_token:
            self.check(False, "TELEGRAM_BOT_TOKEN not set (Telegram disabled)", required=False)

        return api_token, expanded_desk, db_url

    def check_database(self, db_url: Optional[str]) -> None:
        """Check database existence and migrations."""
        self.section("Database")

        if not db_url:
            self.check(False, "Cannot check database - PULSE_DB_URL not set")
            return

        db_path = extract_db_path(db_url)
        if not db_path:
            self.check(False, f"Cannot extract path from: {db_url}")
            return

        # Check file exists
        db_file = Path(db_path)
        if not self.check(db_file.exists(), f"Database exists: {db_path}"):
            return

        # Try to connect and query
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            cursor.fetchone()
            conn.close()
            self.check(True, "Can connect and query")
        except Exception as e:
            self.check(False, f"Cannot connect to database: {e}")
            return

        # Check migrations
        try:
            # Alembic needs a sync URL with an expanded path
            sync_url = f"sqlite:///{db_path}"
            env = os.environ.copy()
            env["PULSE_DB_URL"] = sync_url

            result = subprocess.run(
                ["uv", "run", "alembic", "current"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
                env=env,
                timeout=30,
            )
            output = result.stdout + result.stderr
            if EXPECTED_MIGRATION in output and "(head)" in output:
                self.check(True, f"Migrations current ({EXPECTED_MIGRATION})")
            elif EXPECTED_MIGRATION in output:
                self.check(False, f"Migration found but not at head: {output.strip()}")
            else:
                self.check(False, f"Unexpected migration state: {output.strip()}")
        except Exception as e:
            self.check(False, f"Cannot check migrations: {e}")

    def check_mcp_config(self) -> None:
        """Check MCP server configuration."""
        self.section("MCP Configuration")

        config_path = Path.home() / ".config" / "claude-code" / "mcp_config.json"

        if not self.check(config_path.exists(), f"Config file: {config_path}"):
            return

        try:
            with open(config_path) as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            self.check(False, f"Invalid JSON in config: {e}")
            return
        except Exception as e:
            self.check(False, f"Cannot read config: {e}")
            return

        servers = config.get("mcpServers", {})

        # Check pulse-queue server
        if self.check("pulse-queue" in servers, "pulse-queue server configured"):
            # Validate command exists
            pulse_config = servers["pulse-queue"]
            cmd = pulse_config.get("command", "")
            if cmd and shutil.which(cmd):
                pass  # Command exists, good
            elif cmd:
                self.check(False, f"pulse-queue command not found: {cmd}", required=False)

        # Check telegram-notifier server
        if self.check("telegram-notifier" in servers, "telegram-notifier server configured"):
            telegram_config = servers["telegram-notifier"]
            cmd = telegram_config.get("command", "")
            if cmd and shutil.which(cmd):
                pass  # Command exists, good
            elif cmd:
                self.check(False, f"telegram-notifier command not found: {cmd}", required=False)

    def check_desk_permissions(self, desk_path: Optional[str]) -> None:
        """Check Desk Claude Code permissions."""
        self.section("Desk Permissions")

        if not desk_path:
            self.check(False, "Cannot check - REEVE_DESK_PATH not set")
            return

        settings_path = Path(desk_path) / ".claude" / "settings.json"

        if not self.check(settings_path.exists(), f"Settings file: {settings_path}"):
            return

        try:
            with open(settings_path) as f:
                settings = json.load(f)
        except json.JSONDecodeError as e:
            self.check(False, f"Invalid JSON in settings: {e}")
            return
        except Exception as e:
            self.check(False, f"Cannot read settings: {e}")
            return

        # Get allowed permissions
        permissions = settings.get("permissions", {})
        allowed = permissions.get("allow", [])

        # Check each required permission
        for perm in REQUIRED_PERMISSIONS:
            self.check(perm in allowed, f"{perm} allowed")

    def check_commands(self) -> None:
        """Check required commands are available."""
        self.section("Commands")

        # Check hapi command
        hapi_cmd = os.getenv("HAPI_COMMAND", "hapi")
        hapi_path = shutil.which(hapi_cmd)
        if hapi_path:
            self.check(True, f"hapi command available ({hapi_path})")
        else:
            self.check(False, f"hapi command not found: {hapi_cmd}")

        # Check uv command
        uv_path = shutil.which("uv")
        if uv_path:
            self.check(True, f"uv command available ({uv_path})")
        else:
            self.check(False, "uv command not found")

    def check_services(self) -> None:
        """Check if API service is running."""
        self.section("Services")

        api_port = int(os.getenv("PULSE_API_PORT", "8765"))
        api_url = f"http://127.0.0.1:{api_port}/api/health"

        try:
            import urllib.request

            req = urllib.request.Request(api_url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    self.check(True, f"API responding at http://127.0.0.1:{api_port}")
                else:
                    self.check(
                        False,
                        f"API returned status {response.status}",
                        required=False,
                    )
        except urllib.error.URLError:
            self.check(False, f"API not running at http://127.0.0.1:{api_port}", required=False)
        except Exception as e:
            self.check(False, f"Cannot connect to API: {e}", required=False)

    def run(self) -> int:
        """Run all health checks and return exit code."""
        print("=== Reeve Doctor ===")

        # Run all checks
        api_token, desk_path, db_url = self.check_environment()
        self.check_database(db_url)
        self.check_mcp_config()
        self.check_desk_permissions(desk_path)
        self.check_commands()
        self.check_services()

        # Summary
        print()
        if self.failed == 0:
            if self.warnings > 0:
                print(f"All required checks passed! ({self.warnings} warnings)")
            else:
                print("All checks passed!")
            return 0
        else:
            print(f"Failed: {self.failed}, Passed: {self.passed}, Warnings: {self.warnings}")
            return 1


def main() -> int:
    """Entry point for the doctor command."""
    doctor = Doctor()
    return doctor.run()


if __name__ == "__main__":
    sys.exit(main())
