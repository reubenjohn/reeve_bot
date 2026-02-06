#!/bin/bash
#
# Credential Provider: Claude Code OAuth
# Checks and refreshes Claude Code OAuth tokens in ~/.claude/.credentials.json
#
# Credential Provider Contract:
# Each provider script must define these functions:
#   provider_name()    - Echo the provider name (e.g., "claude-code")
#   provider_check()   - Check credential health
#                        Return 0: healthy (no action needed)
#                        Return 1: needs refresh (will expire soon)
#                        Return 2: critical (already expired or missing)
#   provider_refresh() - Refresh the credentials
#                        Return 0: success
#                        Return 1: failure
#

CREDENTIALS_FILE="$HOME/.claude/.credentials.json"

# Threshold: refresh if token expires within 6 hours (21600 seconds)
REFRESH_THRESHOLD_SECONDS=21600

provider_name() {
    echo "claude-code"
}

provider_check() {
    # Verify file exists
    if [[ ! -f "$CREDENTIALS_FILE" ]]; then
        echo "Credentials file not found: $CREDENTIALS_FILE"
        return 2
    fi

    # Parse expiresAt (milliseconds epoch) using python3
    local expires_at_ms
    expires_at_ms=$(python3 -c "
import json, sys
try:
    with open('$CREDENTIALS_FILE') as f:
        data = json.load(f)
    print(data['claudeAiOauth']['expiresAt'])
except (KeyError, json.JSONDecodeError, FileNotFoundError) as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1) || {
        echo "Failed to parse credentials: $expires_at_ms"
        return 2
    }

    # Convert ms to seconds and compare
    local now_seconds
    now_seconds=$(date +%s)
    local expires_at_seconds=$((expires_at_ms / 1000))
    local remaining=$((expires_at_seconds - now_seconds))

    if [[ $remaining -le 0 ]]; then
        echo "Token EXPIRED ($((remaining * -1)) seconds ago)"
        return 2
    elif [[ $remaining -le $REFRESH_THRESHOLD_SECONDS ]]; then
        local hours_remaining=$((remaining / 3600))
        echo "Token expires in ${hours_remaining}h (threshold: $((REFRESH_THRESHOLD_SECONDS / 3600))h)"
        return 1
    else
        local hours_remaining=$((remaining / 3600))
        echo "Token healthy (expires in ${hours_remaining}h)"
        return 0
    fi
}

provider_refresh() {
    # Capture expiresAt before refresh attempt
    local before_expires
    before_expires=$(python3 -c "
import json
with open('$CREDENTIALS_FILE') as f:
    data = json.load(f)
print(data['claudeAiOauth']['expiresAt'])
" 2>/dev/null) || before_expires="0"

    # Launch claude interactively - the auth/token refresh triggers on startup
    # Send /exit via printf so it exits cleanly after the auth handshake
    printf '/exit\n' | timeout 30 claude >/dev/null 2>&1 || {
        echo "claude command failed or timed out"
        return 1
    }

    # Verify token was actually refreshed
    local after_expires
    after_expires=$(python3 -c "
import json
with open('$CREDENTIALS_FILE') as f:
    data = json.load(f)
print(data['claudeAiOauth']['expiresAt'])
" 2>/dev/null) || {
        echo "Failed to read credentials after refresh"
        return 1
    }

    if [[ "$after_expires" -gt "$before_expires" ]]; then
        echo "Token refreshed (new expiry: $(date -d @$((after_expires / 1000)) '+%Y-%m-%d %H:%M:%S %Z'))"
        return 0
    elif [[ "$after_expires" -eq "$before_expires" ]]; then
        # Token unchanged - claude may have determined refresh wasn't needed yet
        echo "Token unchanged after refresh attempt (expiry still valid)"
        return 0
    fi
}
