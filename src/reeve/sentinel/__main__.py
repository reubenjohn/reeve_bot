"""CLI entry point for sentinel alerts.

Usage:
    python -m reeve.sentinel "Alert message"
    python -m reeve.sentinel --cooldown-key my_key --cooldown 3600 "Message"
"""

import argparse
import sys

from reeve.sentinel import send_alert


def main() -> int:
    """Parse arguments and send a sentinel alert."""
    parser = argparse.ArgumentParser(
        prog="reeve-sentinel",
        description="Send a failsafe alert via the configured backend.",
    )
    parser.add_argument("message", help="Alert message to send")
    parser.add_argument(
        "--cooldown-key",
        default=None,
        help="Deduplication key (alerts with same key are rate-limited)",
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=1800,
        help="Cooldown period in seconds (default: 1800)",
    )

    args = parser.parse_args()

    success = send_alert(
        args.message,
        cooldown_key=args.cooldown_key,
        cooldown_seconds=args.cooldown,
    )

    if success:
        print("Alert sent.", file=sys.stderr)
        return 0
    else:
        print("Alert not sent (no backend, cooldown, or error).", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
