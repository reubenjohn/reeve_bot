#!/bin/bash
#
# Reeve Hourly Heartbeat Script
# Schedules an hourly heartbeat pulse to wake Reeve for periodic checks
#
# Usage: reeve-heartbeat
# Returns: 0 if pulse scheduled, 1 if failed
#
# This implements the "Periodic Pulse (The Heartbeat)" from the design spec:
# "An hourly cron job wakes Reeve up. It checks the time, reviews the Desk,
# and asks: 'Does anything need to be done right now?'"
#

set -e

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
HOUR=$(date '+%H')

# Source environment for API token
# Try multiple locations for flexibility
if [ -f "$HOME/workspace/reeve_bot/.env" ]; then
    source "$HOME/workspace/reeve_bot/.env"
elif [ -f "/opt/reeve/.env" ]; then
    source "/opt/reeve/.env"
elif [ -f "$HOME/.reeve/.env" ]; then
    source "$HOME/.reeve/.env"
fi

# Validate token is available
if [ -z "$PULSE_API_TOKEN" ]; then
    echo "[$TIMESTAMP] ERROR: PULSE_API_TOKEN not set"
    exit 1
fi

API_URL="${PULSE_API_URL:-http://127.0.0.1:8765}"

# Construct the heartbeat prompt
# The prompt varies slightly based on time of day for context
if [ "$HOUR" -ge 6 ] && [ "$HOUR" -lt 12 ]; then
    TIME_CONTEXT="morning"
    PROMPT="Hourly heartbeat (${TIME_CONTEXT}): Review today's calendar, check for urgent emails or messages, identify top priorities for the day."
elif [ "$HOUR" -ge 12 ] && [ "$HOUR" -lt 18 ]; then
    TIME_CONTEXT="afternoon"
    PROMPT="Hourly heartbeat (${TIME_CONTEXT}): Check calendar for upcoming meetings, review any pending tasks, process waiting messages."
elif [ "$HOUR" -ge 18 ] && [ "$HOUR" -lt 22 ]; then
    TIME_CONTEXT="evening"
    PROMPT="Hourly heartbeat (${TIME_CONTEXT}): Review remaining tasks for today, check for any urgent items, prepare end-of-day summary if needed."
else
    TIME_CONTEXT="night"
    PROMPT="Hourly heartbeat (${TIME_CONTEXT}): Light check - only process critical items, defer non-urgent tasks to morning."
fi

# Schedule the pulse via API
RESPONSE=$(curl -sf -X POST "${API_URL}/api/pulse/schedule" \
    -H "Authorization: Bearer ${PULSE_API_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"prompt\": \"${PROMPT}\",
        \"scheduled_at\": \"now\",
        \"priority\": \"normal\",
        \"source\": \"heartbeat_cron\",
        \"tags\": [\"hourly\", \"heartbeat\", \"${TIME_CONTEXT}\"]
    }" 2>&1) || {
    echo "[$TIMESTAMP] ERROR: Failed to schedule heartbeat pulse"
    echo "[$TIMESTAMP] Response: $RESPONSE"
    exit 1
}

# Extract pulse ID from response
PULSE_ID=$(echo "$RESPONSE" | grep -o '"pulse_id":[0-9]*' | cut -d':' -f2)

echo "[$TIMESTAMP] OK: Heartbeat pulse scheduled (ID: ${PULSE_ID}, context: ${TIME_CONTEXT})"
exit 0
