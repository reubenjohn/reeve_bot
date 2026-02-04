#!/bin/bash
#
# Reeve Queue Script
# Pulse queue inspector for viewing and filtering pulses
#
# Usage:
#   reeve-queue             # Show pending pulses (default)
#   reeve-queue pending     # Show pending pulses
#   reeve-queue failed      # Show failed pulses
#   reeve-queue completed   # Show recent completed pulses
#   reeve-queue overdue     # Show overdue pulses
#   reeve-queue all         # Show all recent pulses
#   reeve-queue 123         # Show details for pulse ID 123
#   reeve-queue -h          # Show help
#

set -e

# Source environment for database path
if [ -f "$HOME/workspace/reeve_bot/.env" ]; then
    source "$HOME/workspace/reeve_bot/.env"
elif [ -f "/opt/reeve/.env" ]; then
    source "/opt/reeve/.env"
elif [ -f "$HOME/.reeve/.env" ]; then
    source "$HOME/.reeve/.env"
fi

DB_PATH="${PULSE_DB_PATH:-$HOME/.reeve/pulse_queue.db}"
LIMIT=20

# Print usage
usage() {
    echo "Usage: reeve-queue [FILTER|ID]"
    echo ""
    echo "Filters:"
    echo "  pending     Show pending pulses (default)"
    echo "  failed      Show failed pulses"
    echo "  completed   Show recent completed pulses"
    echo "  overdue     Show overdue pulses (pending + past scheduled time)"
    echo "  all         Show all recent pulses"
    echo ""
    echo "Options:"
    echo "  ID          Show details for a specific pulse ID (numeric)"
    echo "  -h, --help  Show this help message"
    echo ""
    echo "Examples:"
    echo "  reeve-queue              # Show pending pulses"
    echo "  reeve-queue failed       # Show failed pulses"
    echo "  reeve-queue 123          # Show details for pulse 123"
}

# Check database exists
check_db() {
    if [ ! -f "$DB_PATH" ]; then
        echo "Error: Database not found: $DB_PATH"
        exit 1
    fi
}

# Truncate string to max length, adding ... if needed
truncate_str() {
    local str="$1"
    local max_len="$2"
    if [ ${#str} -gt $max_len ]; then
        echo "${str:0:$((max_len-3))}..."
    else
        echo "$str"
    fi
}

# Format a list of pulses
format_pulse_list() {
    local filter="$1"
    local title="$2"

    echo "=== $title ==="
    echo "ID    Priority  Scheduled          Prompt"
    echo "--------------------------------------------------------------"

    local count=0

    while IFS='|' read -r id priority scheduled_at prompt; do
        if [ -z "$id" ]; then
            continue
        fi

        # Truncate prompt to ~50 chars
        prompt_short=$(truncate_str "$prompt" 50)

        # Format priority with fixed width
        printf "%-5s %-9s %-18s %s\n" "$id" "$priority" "$scheduled_at" "$prompt_short"
        count=$((count + 1))
    done

    echo ""
    echo "Total: $count $filter"
}

# Show details for a single pulse
show_pulse_details() {
    local pulse_id="$1"

    echo "=== Pulse #$pulse_id ==="

    # Get pulse details
    local result=$(sqlite3 -separator '|' "$DB_PATH" "
        SELECT id, status, priority, scheduled_at, executed_at,
               prompt, session_id, sticky_notes, tags,
               created_by, created_at, execution_duration_ms, error_message,
               retry_count, max_retries
        FROM pulses
        WHERE id = $pulse_id;
    " 2>/dev/null)

    if [ -z "$result" ]; then
        echo "Error: Pulse not found: $pulse_id"
        exit 1
    fi

    IFS='|' read -r id status priority scheduled_at executed_at \
                    prompt session_id sticky_notes tags \
                    created_by created_at execution_duration_ms error_message \
                    retry_count max_retries <<< "$result"

    echo ""
    echo "Status:      $status"
    echo "Priority:    $priority"
    echo "Scheduled:   $scheduled_at"

    if [ -n "$executed_at" ] && [ "$executed_at" != "" ]; then
        echo "Executed:    $executed_at"
    fi

    if [ -n "$execution_duration_ms" ] && [ "$execution_duration_ms" != "" ]; then
        local duration_sec=$((execution_duration_ms / 1000))
        echo "Duration:    ${duration_sec}s (${execution_duration_ms}ms)"
    fi

    echo ""
    echo "Prompt:"
    echo "  $prompt"

    if [ -n "$sticky_notes" ] && [ "$sticky_notes" != "" ]; then
        echo ""
        echo "Sticky Notes: $sticky_notes"
    fi

    if [ -n "$tags" ] && [ "$tags" != "" ]; then
        echo ""
        echo "Tags: $tags"
    fi

    if [ -n "$error_message" ] && [ "$error_message" != "" ]; then
        echo ""
        echo "Error:"
        echo "  $error_message"
    fi

    echo ""
    echo "Created By:  $created_by"
    echo "Created At:  $created_at"

    if [ -n "$session_id" ] && [ "$session_id" != "" ]; then
        echo "Session ID:  $session_id"
    fi

    echo "Retries:     $retry_count / $max_retries"
}

# Main logic
main() {
    # Default filter
    local filter="pending"

    # Parse arguments
    if [ $# -gt 0 ]; then
        case "$1" in
            -h|--help)
                usage
                exit 0
                ;;
            pending|failed|completed|overdue|all)
                filter="$1"
                ;;
            *)
                # Check if it's a numeric ID
                if [[ "$1" =~ ^[0-9]+$ ]]; then
                    check_db
                    show_pulse_details "$1"
                    exit 0
                else
                    echo "Error: Unknown argument: $1"
                    usage
                    exit 1
                fi
                ;;
        esac
    fi

    check_db

    # Build query based on filter
    case "$filter" in
        pending)
            sqlite3 -separator '|' "$DB_PATH" "
                SELECT id, priority, strftime('%Y-%m-%d %H:%M', scheduled_at, 'localtime'), prompt
                FROM pulses
                WHERE status = 'pending'
                ORDER BY scheduled_at ASC
                LIMIT $LIMIT;
            " | format_pulse_list "pending" "Pending Pulses"
            ;;

        failed)
            sqlite3 -separator '|' "$DB_PATH" "
                SELECT id, priority, strftime('%Y-%m-%d %H:%M', scheduled_at, 'localtime'), prompt
                FROM pulses
                WHERE status = 'failed'
                ORDER BY executed_at DESC
                LIMIT $LIMIT;
            " | format_pulse_list "failed" "Failed Pulses"
            ;;

        completed)
            sqlite3 -separator '|' "$DB_PATH" "
                SELECT id, priority, strftime('%Y-%m-%d %H:%M', executed_at, 'localtime'), prompt
                FROM pulses
                WHERE status = 'completed'
                ORDER BY executed_at DESC
                LIMIT $LIMIT;
            " | format_pulse_list "completed" "Completed Pulses"
            ;;

        overdue)
            sqlite3 -separator '|' "$DB_PATH" "
                SELECT id, priority, strftime('%Y-%m-%d %H:%M', scheduled_at, 'localtime'), prompt
                FROM pulses
                WHERE status = 'pending' AND scheduled_at < datetime('now')
                ORDER BY scheduled_at ASC
                LIMIT $LIMIT;
            " | format_pulse_list "overdue" "Overdue Pulses"
            ;;

        all)
            sqlite3 -separator '|' "$DB_PATH" "
                SELECT id, priority, strftime('%Y-%m-%d %H:%M', scheduled_at, 'localtime'), prompt
                FROM pulses
                ORDER BY scheduled_at DESC
                LIMIT $LIMIT;
            " | format_pulse_list "recent" "All Recent Pulses"
            ;;
    esac
}

main "$@"
