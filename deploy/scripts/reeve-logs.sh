#!/bin/bash
#
# Reeve Logs Script
# Unified log viewer for daemon, telegram, and heartbeat logs
#
# Usage:
#   reeve-logs              # Follow daemon logs (default)
#   reeve-logs daemon       # Follow daemon logs
#   reeve-logs telegram     # Follow telegram listener logs
#   reeve-logs heartbeat    # Tail heartbeat log file
#   reeve-logs all          # Interleave all logs
#   reeve-logs -n 50        # Show last 50 lines (no follow)
#   reeve-logs -h           # Show help
#

set -e

HEARTBEAT_LOG="$HOME/.reeve/logs/heartbeat.log"

# Default values
SOURCE="daemon"
FOLLOW=true
LINES=50

# Print usage
usage() {
    echo "Usage: reeve-logs [OPTIONS] [SOURCE]"
    echo ""
    echo "Sources:"
    echo "  daemon      Reeve daemon logs (default)"
    echo "  telegram    Telegram listener logs"
    echo "  heartbeat   Heartbeat log file"
    echo "  all         Interleave all logs"
    echo ""
    echo "Options:"
    echo "  -n N        Show last N lines (no follow)"
    echo "  -h, --help  Show this help message"
    echo ""
    echo "Examples:"
    echo "  reeve-logs                  # Follow daemon logs"
    echo "  reeve-logs telegram         # Follow telegram logs"
    echo "  reeve-logs -n 100           # Show last 100 daemon lines"
    echo "  reeve-logs -n 50 heartbeat  # Show last 50 heartbeat lines"
    echo "  reeve-logs all              # Follow all logs"
}

# Parse arguments
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        -n)
            if [ -z "$2" ] || [ "${2:0:1}" = "-" ]; then
                echo "Error: -n requires a number argument"
                exit 1
            fi
            LINES="$2"
            FOLLOW=false
            shift 2
            ;;
        daemon|telegram|heartbeat|all)
            SOURCE="$1"
            shift
            ;;
        *)
            echo "Error: Unknown argument: $1"
            usage
            exit 1
            ;;
    esac
done

# Show logs based on source
case "$SOURCE" in
    daemon)
        if [ "$FOLLOW" = true ]; then
            echo "=== Following reeve-daemon logs (Ctrl+C to exit) ==="
            sudo journalctl -u reeve-daemon -f --no-pager
        else
            echo "=== Last $LINES lines from reeve-daemon ==="
            sudo journalctl -u reeve-daemon -n "$LINES" --no-pager
        fi
        ;;

    telegram)
        if [ "$FOLLOW" = true ]; then
            echo "=== Following reeve-telegram logs (Ctrl+C to exit) ==="
            sudo journalctl -u reeve-telegram -f --no-pager
        else
            echo "=== Last $LINES lines from reeve-telegram ==="
            sudo journalctl -u reeve-telegram -n "$LINES" --no-pager
        fi
        ;;

    heartbeat)
        if [ ! -f "$HEARTBEAT_LOG" ]; then
            echo "Error: Heartbeat log not found: $HEARTBEAT_LOG"
            exit 1
        fi

        if [ "$FOLLOW" = true ]; then
            echo "=== Following heartbeat log (Ctrl+C to exit) ==="
            tail -f "$HEARTBEAT_LOG"
        else
            echo "=== Last $LINES lines from heartbeat log ==="
            tail -n "$LINES" "$HEARTBEAT_LOG"
        fi
        ;;

    all)
        if [ "$FOLLOW" = true ]; then
            echo "=== Following all logs (Ctrl+C to exit) ==="
            echo ""

            # Use background processes and wait
            # Clean up on exit
            cleanup() {
                kill $(jobs -p) 2>/dev/null
                exit 0
            }
            trap cleanup INT TERM

            # Start journalctl for both services
            sudo journalctl -u reeve-daemon -u reeve-telegram -f --no-pager &
            JOURNAL_PID=$!

            # Also tail heartbeat log if it exists
            if [ -f "$HEARTBEAT_LOG" ]; then
                tail -f "$HEARTBEAT_LOG" 2>/dev/null &
                TAIL_PID=$!
            fi

            # Wait for any child to exit
            wait
        else
            # Show each source with headers
            echo "=== Last $LINES lines from reeve-daemon ==="
            sudo journalctl -u reeve-daemon -n "$LINES" --no-pager 2>/dev/null || echo "(no logs)"
            echo ""

            echo "=== Last $LINES lines from reeve-telegram ==="
            sudo journalctl -u reeve-telegram -n "$LINES" --no-pager 2>/dev/null || echo "(no logs)"
            echo ""

            echo "=== Last $LINES lines from heartbeat log ==="
            if [ -f "$HEARTBEAT_LOG" ]; then
                tail -n "$LINES" "$HEARTBEAT_LOG"
            else
                echo "(log not found: $HEARTBEAT_LOG)"
            fi
        fi
        ;;
esac
