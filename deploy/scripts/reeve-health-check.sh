#!/bin/bash
#
# Reeve Health Check Script
# Checks if daemon is running and API is responding
#
# Usage: reeve-health-check
# Returns: 0 if healthy, 1 if unhealthy
#

set -e

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Check if daemon is running
if ! systemctl is-active --quiet reeve-daemon; then
    echo "[$TIMESTAMP] ERROR: reeve-daemon is not running"
    exit 1
fi

# Check API health
if ! curl -sf http://localhost:8765/api/health > /dev/null 2>&1; then
    echo "[$TIMESTAMP] ERROR: API health check failed"
    exit 1
fi

echo "[$TIMESTAMP] OK: All services healthy"
exit 0
