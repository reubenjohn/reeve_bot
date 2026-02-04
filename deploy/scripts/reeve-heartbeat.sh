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

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')

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
# Generic prompt - the Desk governs what Reeve should do at different times
PROMPT="Hourly heartbeat [${TIMESTAMP}]: Review your Responsibilities and Goals in the context of the current time. Take appropriate action, respecting Preferences."

# Schedule the pulse via API
RESPONSE=$(curl -sf -X POST "${API_URL}/api/pulse/schedule" \
    -H "Authorization: Bearer ${PULSE_API_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"prompt\": \"${PROMPT}\",
        \"scheduled_at\": \"now\",
        \"priority\": \"normal\",
        \"source\": \"heartbeat_cron\",
        \"tags\": [\"hourly\", \"heartbeat\"]
    }" 2>&1) || {
    echo "[$TIMESTAMP] ERROR: Failed to schedule heartbeat pulse"
    echo "[$TIMESTAMP] Response: $RESPONSE"
    exit 1
}

# Extract pulse ID from response
PULSE_ID=$(echo "$RESPONSE" | grep -o '"pulse_id":[0-9]*' | cut -d':' -f2)

echo "[$TIMESTAMP] OK: Heartbeat pulse scheduled (ID: ${PULSE_ID})"
exit 0
