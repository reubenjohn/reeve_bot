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

# Resolve claude binary (cron has minimal PATH)
_find_claude() {
    local candidates=(
        "$HOME/.local/bin/claude"
        "/usr/local/bin/claude"
        "$(which claude 2>/dev/null)"
    )
    for c in "${candidates[@]}"; do
        if [[ -n "$c" && -x "$c" ]]; then
            echo "$c"
            return 0
        fi
    done
    return 1
}

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
    # Resolve claude binary
    local claude_bin
    claude_bin=$(_find_claude) || {
        echo "claude binary not found in PATH or common locations"
        return 1
    }

    # Capture expiresAt before refresh attempt
    local before_expires
    before_expires=$(python3 -c "
import json
with open('$CREDENTIALS_FILE') as f:
    data = json.load(f)
print(data['claudeAiOauth']['expiresAt'])
" 2>/dev/null) || before_expires="0"

    # Emulate a real interactive session using a PTY.
    #
    # Why: Claude Code detects non-interactive usage (piped stdin, --print flag)
    # and skips token refresh. The old approach (printf '/exit\n' | claude) failed
    # because piped stdin = no TTY = non-interactive detection.
    #
    # Solution: Use pexpect to spawn claude in a real pseudo-terminal, making it
    # behave as if a human launched it interactively. The auth/token refresh
    # happens during startup, then we send double Ctrl-C to cleanly shut down.
    /usr/bin/python3 -c "
import pexpect, sys, time

CLAUDE = '$claude_bin'

try:
    # Spawn claude in a real PTY (no --print, no piped stdin)
    child = pexpect.spawn(CLAUDE, timeout=60, encoding='utf-8')

    # Wait for Claude to finish startup (auth refresh happens here)
    time.sleep(5)

    # Double Ctrl-C to cleanly exit
    child.sendintr()
    time.sleep(0.3)
    child.sendintr()

    # Wait for process to exit
    time.sleep(2)
    if child.isalive():
        child.close(force=True)
        print('Process did not exit cleanly, force killed')
    else:
        child.close()

    sys.exit(0)
except Exception as e:
    print(f'PTY refresh failed: {e}', file=sys.stderr)
    try:
        child.close(force=True)
    except:
        pass
    sys.exit(1)
" 2>&1 || {
        echo "Claude PTY session failed"
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
        echo "Token unchanged after refresh attempt (expiry still valid)"
        return 0
    else
        echo "Token expiry went backwards - unexpected state"
        return 1
    fi
}
