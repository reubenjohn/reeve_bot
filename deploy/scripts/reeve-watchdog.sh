#!/bin/bash
#
# Reeve Watchdog - External failsafe that detects system-wide failures
# Runs via cron every 30 minutes. Alerts via reeve-alert if system is unhealthy.
#
# This is Layer 3 of the Sentinel system — catches failures that Layers 1 and 2 miss,
# including daemon crashes, stuck processes, and complete system outages.
#
# Usage: reeve-watchdog
# Returns: 0 if healthy, 1 if unhealthy (alert sent)
#

set -e

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')

# Configuration
MAX_SILENCE_HOURS=3
STATE_DIR="${HOME}/.reeve/sentinel"
UNHEALTHY_MARKER="${STATE_DIR}/.watchdog_unhealthy"
DB_PATH="${PULSE_DB_PATH:-${HOME}/.reeve/pulse_queue.db}"

# Source .env
REEVE_BOT_PATH="${REEVE_BOT_PATH:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
if [[ -f "$REEVE_BOT_PATH/.env" ]]; then
    set -a
    source "$REEVE_BOT_PATH/.env"
    set +a
fi

# Ensure state directory exists
mkdir -p "$STATE_DIR"

# ---- Alert helper (calls reeve-alert CLI) ----
_alert() {
    local message="$1"
    local cooldown_key="${2:-watchdog}"
    local cooldown="${3:-1800}"

    # Try reeve-alert from PATH first, then from repo
    local alert_cmd=""
    if command -v reeve-alert &>/dev/null; then
        alert_cmd="reeve-alert"
    elif [[ -x "$REEVE_BOT_PATH/deploy/scripts/reeve-alert.sh" ]]; then
        alert_cmd="$REEVE_BOT_PATH/deploy/scripts/reeve-alert.sh"
    else
        echo "[$TIMESTAMP] WATCHDOG: Cannot find reeve-alert command" >&2
        return 1
    fi

    "$alert_cmd" --cooldown-key "$cooldown_key" --cooldown "$cooldown" "$message" 2>/dev/null || true
}

# ---- Health checks ----
ISSUES=""

# Check 1: Daemon service running
if command -v systemctl &>/dev/null; then
    if ! sudo systemctl is-active --quiet reeve-daemon 2>/dev/null; then
        ISSUES="${ISSUES}- reeve-daemon service is NOT running\n"
    fi
fi

# Check 2: API responding
if ! curl -sf --max-time 5 http://localhost:${PULSE_API_PORT:-8765}/api/health > /dev/null 2>&1; then
    ISSUES="${ISSUES}- API health check failed (not responding)\n"
fi

# Check 3: Recent successful pulse execution
if [[ -f "$DB_PATH" ]]; then
    last_completed=$(sqlite3 "$DB_PATH" "
        SELECT COALESCE(MAX(executed_at), '') FROM pulses WHERE status='completed';
    " 2>/dev/null || echo "")

    if [[ -n "$last_completed" && "$last_completed" != "" ]]; then
        # SQLite stores UTC timestamps, convert to epoch
        last_epoch=$(date -d "$last_completed" +%s 2>/dev/null || echo "0")
        now_epoch=$(date -u +%s)
        hours_since=$(( (now_epoch - last_epoch) / 3600 ))

        if [[ "$hours_since" -ge "$MAX_SILENCE_HOURS" ]]; then
            ISSUES="${ISSUES}- No successful pulse in ${hours_since} hours (threshold: ${MAX_SILENCE_HOURS}h)\n"
        fi
    fi

    # Check 4: Permanently failed pulses in last 24h
    recent_failures=$(sqlite3 "$DB_PATH" "
        SELECT COUNT(*) FROM pulses
        WHERE status='failed'
          AND retry_count >= max_retries
          AND executed_at > datetime('now', '-24 hours');
    " 2>/dev/null || echo "0")

    if [[ "$recent_failures" -gt 0 ]]; then
        ISSUES="${ISSUES}- ${recent_failures} permanently failed pulse(s) in last 24 hours\n"
    fi
else
    ISSUES="${ISSUES}- Database not found: $DB_PATH\n"
fi

# ---- Evaluate results ----
if [[ -n "$ISSUES" ]]; then
    # System is unhealthy
    echo "[$TIMESTAMP] WATCHDOG: UNHEALTHY"
    echo -e "$ISSUES"

    _alert "Reeve health check FAILED

$(echo -e "$ISSUES")
Time: $TIMESTAMP

Troubleshoot:
  reeve-status         # Overview
  reeve-logs           # Daemon logs
  reeve-queue failed   # Failed pulses" "watchdog" 1800

    # Mark unhealthy for recovery detection
    touch "$UNHEALTHY_MARKER"
    exit 1
else
    echo "[$TIMESTAMP] WATCHDOG: All checks passed"

    # Recovery detection: were we previously unhealthy?
    if [[ -f "$UNHEALTHY_MARKER" ]]; then
        echo "[$TIMESTAMP] WATCHDOG: Recovered from unhealthy state"
        _alert "Reeve recovered

System healthy again after previous failure.
Time: $TIMESTAMP" "watchdog_recovery" 300
        rm -f "$UNHEALTHY_MARKER"
    fi

    exit 0
fi
