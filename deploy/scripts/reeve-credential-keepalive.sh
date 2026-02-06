#!/bin/bash
#
# Reeve Credential Keep-Alive
# Periodically refreshes authentication credentials for services Reeve depends on.
# Uses pluggable provider scripts from deploy/credential-providers/
#
# Usage: reeve-credential-keepalive
# Returns: 0 if all credentials healthy/refreshed, 1 if any failed
#

set -e

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')

# Provider directory - relative to this script by default
# install.sh patches this to /usr/local/lib/reeve/credential-providers at install time
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROVIDERS_DIR="${PROVIDERS_DIR:-$(dirname "$SCRIPT_DIR")/credential-providers}"

# Track overall status
OVERALL_FAILURES=0

# Unset provider functions to avoid bleed between providers
_unset_provider_functions() {
    unset -f provider_name provider_check provider_refresh 2>/dev/null || true
}

# Check providers directory exists
if [[ ! -d "$PROVIDERS_DIR" ]]; then
    echo "[$TIMESTAMP] ERROR: Providers directory not found: $PROVIDERS_DIR"
    exit 1
fi

# Discover and process providers
provider_count=0
for provider_file in "$PROVIDERS_DIR"/*.sh; do
    # Handle case where glob matches nothing
    [[ -f "$provider_file" ]] || continue

    # Clean slate for each provider
    _unset_provider_functions

    # Source the provider
    source "$provider_file"

    # Validate provider implements the contract
    if ! declare -f provider_name > /dev/null || \
       ! declare -f provider_check > /dev/null || \
       ! declare -f provider_refresh > /dev/null; then
        echo "[$TIMESTAMP] ERROR: Provider $provider_file missing required functions (provider_name, provider_check, provider_refresh)"
        OVERALL_FAILURES=$((OVERALL_FAILURES + 1))
        continue
    fi

    provider_count=$((provider_count + 1))
    name=$(provider_name)
    echo "[$TIMESTAMP] INFO: Checking provider: $name"

    # Check credential health (capture output AND exit code)
    check_output=$(provider_check 2>&1) && check_rc=0 || check_rc=$?

    case $check_rc in
        0)
            echo "[$TIMESTAMP] OK: $name: $check_output"
            ;;
        1|2)
            echo "[$TIMESTAMP] INFO: $name: $check_output (refreshing...)"

            # Attempt refresh (capture output AND exit code)
            refresh_output=$(provider_refresh 2>&1) && refresh_rc=0 || refresh_rc=$?

            if [[ $refresh_rc -eq 0 ]]; then
                echo "[$TIMESTAMP] OK: $name: $refresh_output"
            else
                echo "[$TIMESTAMP] ERROR: $name: Refresh failed - $refresh_output"
                OVERALL_FAILURES=$((OVERALL_FAILURES + 1))
            fi
            ;;
        *)
            echo "[$TIMESTAMP] ERROR: $name: Unexpected check return code $check_rc"
            OVERALL_FAILURES=$((OVERALL_FAILURES + 1))
            ;;
    esac
done

# Clean up
_unset_provider_functions

if [[ $provider_count -eq 0 ]]; then
    echo "[$TIMESTAMP] ERROR: No providers found in $PROVIDERS_DIR"
    exit 1
fi

if [[ $OVERALL_FAILURES -gt 0 ]]; then
    echo "[$TIMESTAMP] ERROR: $OVERALL_FAILURES provider(s) failed"
    exit 1
fi

echo "[$TIMESTAMP] OK: All $provider_count provider(s) healthy"
exit 0
