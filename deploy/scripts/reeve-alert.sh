#!/bin/bash
#
# Reeve Alert - Send a failsafe sentinel alert via the configured backend
# Thin wrapper around: python -m reeve.sentinel
#
# Usage: reeve-alert "message"
#        reeve-alert --cooldown-key my_key --cooldown 3600 "message"
#
# Environment:
#   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID - for Telegram backend
#   SENTINEL_BACKEND - explicit backend override (default: auto-detect)
#

# Determine repo path
# install.sh patches this to the installed path
REEVE_BOT_PATH="${REEVE_BOT_PATH:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# Source .env for credentials if not already in environment
if [[ -z "$TELEGRAM_BOT_TOKEN" ]] && [[ -f "$REEVE_BOT_PATH/.env" ]]; then
    set -a
    source "$REEVE_BOT_PATH/.env"
    set +a
fi

# Find uv
UV_PATH="${UV_PATH:-$(which uv 2>/dev/null)}"
if [[ -z "$UV_PATH" ]]; then
    for path in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" "/usr/local/bin/uv"; do
        [[ -x "$path" ]] && UV_PATH="$path" && break
    done
fi

if [[ -z "$UV_PATH" ]]; then
    echo "ERROR: uv not found" >&2
    exit 1
fi

exec "$UV_PATH" run --directory "$REEVE_BOT_PATH" python -m reeve.sentinel "$@"
