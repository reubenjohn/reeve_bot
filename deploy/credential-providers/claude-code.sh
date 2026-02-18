#!/bin/bash
#
# Credential Provider: Claude Code OAuth
# Checks and refreshes Claude Code OAuth tokens in ~/.claude/.credentials.json
#
# Refreshes by calling the OAuth token endpoint directly (no need to spawn
# the claude CLI). This is reliable regardless of token state.
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

# Threshold: refresh if token expires within 2 hours (7200 seconds).
# Tokens last 8h; checking hourly at :50 means we always refresh with 1-2h to spare.
REFRESH_THRESHOLD_SECONDS=7200

# Claude Code OAuth constants (extracted from the CLI binary)
OAUTH_TOKEN_URL="https://platform.claude.com/v1/oauth/token"
OAUTH_CLIENT_ID="9d1c250a-e61b-44d9-88ed-5944d1962f5e"
OAUTH_SCOPES="user:profile user:inference user:sessions:claude_code user:mcp_servers"

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
    # Call the OAuth token endpoint directly with the refresh token.
    # This is reliable regardless of whether the token is expired or not.
    local result
    result=$(python3 -c "
import json, sys, os, stat
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CREDENTIALS_FILE = '$CREDENTIALS_FILE'
TOKEN_URL = '$OAUTH_TOKEN_URL'
CLIENT_ID = '$OAUTH_CLIENT_ID'
SCOPES = '$OAUTH_SCOPES'

# Read current credentials
try:
    with open(CREDENTIALS_FILE) as f:
        creds = json.load(f)
    oauth = creds['claudeAiOauth']
    refresh_token = oauth['refreshToken']
except (KeyError, json.JSONDecodeError, FileNotFoundError) as e:
    print(f'ERROR: Failed to read credentials: {e}', file=sys.stderr)
    sys.exit(1)

if not refresh_token:
    print('ERROR: No refresh token found', file=sys.stderr)
    sys.exit(1)

# Call the token endpoint
payload = json.dumps({
    'grant_type': 'refresh_token',
    'refresh_token': refresh_token,
    'client_id': CLIENT_ID,
    'scope': SCOPES,
}).encode()

req = Request(TOKEN_URL, data=payload, method='POST')
req.add_header('Content-Type', 'application/json')
req.add_header('User-Agent', 'claude-code/2.1.45')

try:
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
except HTTPError as e:
    body = e.read().decode('utf-8', errors='replace')[:200]
    print(f'ERROR: Token endpoint returned {e.code}: {body}', file=sys.stderr)
    sys.exit(1)
except URLError as e:
    print(f'ERROR: Network error: {e.reason}', file=sys.stderr)
    sys.exit(1)

access_token = data.get('access_token')
new_refresh_token = data.get('refresh_token', refresh_token)
expires_in = data.get('expires_in')

if not access_token or not expires_in:
    print(f'ERROR: Unexpected response: {json.dumps(data)[:200]}', file=sys.stderr)
    sys.exit(1)

import time
new_expires_at = int(time.time() * 1000) + expires_in * 1000

# Update credentials file (preserve other fields like organizationUuid, mcpOAuth)
oauth['accessToken'] = access_token
oauth['refreshToken'] = new_refresh_token
oauth['expiresAt'] = new_expires_at
if 'scope' in data:
    oauth['scopes'] = data['scope'].split(' ')

with open(CREDENTIALS_FILE, 'w') as f:
    json.dump(creds, f, indent=2)
os.chmod(CREDENTIALS_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0600

from datetime import datetime
expiry_str = datetime.fromtimestamp(new_expires_at / 1000).strftime('%Y-%m-%d %H:%M:%S %Z')
print(f'Token refreshed (new expiry: {expiry_str}, expires_in: {expires_in}s)')
" 2>&1) || {
        echo "Refresh failed: $result"
        return 1
    }

    echo "$result"
    return 0
}
