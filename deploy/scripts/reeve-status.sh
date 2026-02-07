#!/bin/bash
#
# Reeve Status Script
# Comprehensive system overview showing services, API, queue, and recent activity
#
# Usage: reeve-status
# Returns: 0 if healthy, 1 if issues detected
#

set -e

# Track issues for exit code
ISSUES=0

# Source environment for API token
# Try multiple locations for flexibility
if [ -f "$HOME/workspace/reeve_bot/.env" ]; then
    source "$HOME/workspace/reeve_bot/.env"
elif [ -f "/opt/reeve/.env" ]; then
    source "/opt/reeve/.env"
elif [ -f "$HOME/.reeve/.env" ]; then
    source "$HOME/.reeve/.env"
fi

API_URL="${PULSE_API_URL:-http://127.0.0.1:8765}"
DB_PATH="${PULSE_DB_PATH:-$HOME/.reeve/pulse_queue.db}"
HEARTBEAT_LOG="$HOME/.reeve/logs/heartbeat.log"

# Helper function to format uptime
format_uptime() {
    local seconds=$1
    local days=$((seconds / 86400))
    local hours=$(((seconds % 86400) / 3600))
    local minutes=$(((seconds % 3600) / 60))

    if [ $days -gt 0 ]; then
        echo "${days}d ${hours}h"
    elif [ $hours -gt 0 ]; then
        echo "${hours}h ${minutes}m"
    else
        echo "${minutes}m"
    fi
}

# Helper function to format duration in ms to human readable
format_duration_ms() {
    local ms=$1
    if [ -z "$ms" ] || [ "$ms" = "null" ]; then
        echo "-"
        return
    fi
    local seconds=$((ms / 1000))
    if [ $seconds -lt 60 ]; then
        echo "${seconds}s"
    else
        local minutes=$((seconds / 60))
        local remaining_seconds=$((seconds % 60))
        echo "${minutes}m ${remaining_seconds}s"
    fi
}

echo "=== Reeve Status ==="

# --- Services Section ---
echo "Services:"

for service in reeve-daemon reeve-telegram; do
    # Get service status
    if sudo systemctl is-active --quiet "$service" 2>/dev/null; then
        # Get PID and uptime
        pid=$(sudo systemctl show "$service" --property=MainPID --value 2>/dev/null)

        # Get active enter timestamp (when service started)
        active_timestamp=$(sudo systemctl show "$service" --property=ActiveEnterTimestamp --value 2>/dev/null)
        if [ -n "$active_timestamp" ] && [ "$active_timestamp" != "n/a" ]; then
            # Convert timestamp to epoch seconds
            start_epoch=$(date -d "$active_timestamp" +%s 2>/dev/null || echo "0")
            now_epoch=$(date +%s)
            uptime_seconds=$((now_epoch - start_epoch))
            uptime_str=$(format_uptime $uptime_seconds)
            echo "  $service:   [OK] running (pid $pid, uptime $uptime_str)"
        else
            echo "  $service:   [OK] running (pid $pid)"
        fi
    else
        echo "  $service:   [FAIL] not running"
        ISSUES=$((ISSUES + 1))
    fi
done

echo ""

# --- API Section ---
echo -n "API: "
if curl -sf "${API_URL}/api/health" > /dev/null 2>&1; then
    echo "[OK] healthy (${API_URL})"
else
    echo "[FAIL] not responding (${API_URL})"
    ISSUES=$((ISSUES + 1))
fi

echo ""

# --- Pulse Queue Section ---
echo "Pulse Queue:"

if [ -f "$DB_PATH" ]; then
    # Get queue stats directly from database
    pending=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM pulses WHERE status='pending';" 2>/dev/null || echo "?")
    overdue=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM pulses WHERE status='pending' AND scheduled_at < datetime('now');" 2>/dev/null || echo "?")
    failed=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM pulses WHERE status='failed';" 2>/dev/null || echo "?")

    echo "  Pending: $pending | Overdue: $overdue | Failed: $failed"

    if [ "$overdue" != "?" ] && [ "$overdue" -gt 0 ]; then
        ISSUES=$((ISSUES + 1))
    fi
    if [ "$failed" != "?" ] && [ "$failed" -gt 0 ]; then
        ISSUES=$((ISSUES + 1))
    fi
else
    echo "  Database not found: $DB_PATH"
    ISSUES=$((ISSUES + 1))
fi

echo ""

# --- Recent Pulses Section ---
echo "Recent Pulses (last 5):"

if [ -f "$DB_PATH" ]; then
    # Get last 5 completed pulses with their details
    sqlite3 -separator '|' "$DB_PATH" "
        SELECT id, status, strftime('%H:%M', executed_at, 'localtime'),
               substr(prompt, 1, 30), execution_duration_ms
        FROM pulses
        WHERE status IN ('completed', 'failed')
        ORDER BY executed_at DESC
        LIMIT 5;
    " 2>/dev/null | while IFS='|' read -r id status time prompt duration; do
        if [ "$status" = "completed" ]; then
            status_mark="[OK]"
        else
            status_mark="[FAIL]"
        fi
        duration_str=$(format_duration_ms "$duration")
        # Truncate prompt if needed
        if [ ${#prompt} -ge 30 ]; then
            prompt="${prompt}..."
        fi
        echo "  [$id] $status_mark $time $prompt - $duration_str"
    done

    # Check if there were any results
    count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM pulses WHERE status IN ('completed', 'failed');" 2>/dev/null || echo "0")
    if [ "$count" = "0" ]; then
        echo "  (no completed pulses yet)"
    fi
else
    echo "  (database not available)"
fi

echo ""

# --- Heartbeat Section ---
echo -n "Last Heartbeat: "

if [ -f "$HEARTBEAT_LOG" ]; then
    # Get the last OK line from heartbeat log
    last_heartbeat=$(grep "OK: Heartbeat pulse scheduled" "$HEARTBEAT_LOG" 2>/dev/null | tail -1)

    if [ -n "$last_heartbeat" ]; then
        # Extract timestamp from log line (format: [YYYY-MM-DD HH:MM:SS])
        timestamp=$(echo "$last_heartbeat" | grep -o '\[[0-9-]* [0-9:]*\]' | tr -d '[]')

        if [ -n "$timestamp" ]; then
            # Parse timestamp and calculate age
            hb_epoch=$(date -d "$timestamp" +%s 2>/dev/null || echo "0")
            now_epoch=$(date +%s)
            age_seconds=$((now_epoch - hb_epoch))
            age_minutes=$((age_seconds / 60))

            # Extract just the time portion
            hb_time=$(echo "$timestamp" | cut -d' ' -f2)

            if [ $age_minutes -lt 90 ]; then
                echo "$hb_time ($age_minutes min ago) [OK]"
            else
                echo "$hb_time ($age_minutes min ago) [WARN] stale"
                ISSUES=$((ISSUES + 1))
            fi
        else
            echo "(unable to parse timestamp)"
        fi
    else
        echo "(no heartbeat recorded)"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo "(log not found: $HEARTBEAT_LOG)"
fi

# --- Error Count Section ---
echo -n "Errors (last hour): "

error_count=$(sudo journalctl -u reeve-daemon --since "1 hour ago" -p err --no-pager -q 2>/dev/null | wc -l || echo "?")
echo "$error_count"

if [ "$error_count" != "?" ] && [ "$error_count" -gt 0 ]; then
    ISSUES=$((ISSUES + 1))
fi

# Exit with appropriate code
if [ $ISSUES -gt 0 ]; then
    exit 1
else
    exit 0
fi
