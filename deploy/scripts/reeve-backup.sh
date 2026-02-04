#!/bin/bash
#
# Reeve Database Backup Script
# Creates compressed backups and removes old ones
#
# Usage: reeve-backup
# Creates: ~/.reeve/backups/pulse_queue_YYYYMMDD_HHMMSS.db.gz
#

set -e

# Configuration (can be overridden via environment)
REEVE_HOME="${REEVE_HOME:-$HOME/.reeve}"
BACKUP_DIR="${BACKUP_DIR:-$REEVE_HOME/backups}"
DB_PATH="${DB_PATH:-$REEVE_HOME/pulse_queue.db}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="pulse_queue_${TIMESTAMP}.db"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Check if database exists
if [[ ! -f "$DB_PATH" ]]; then
    echo "ERROR: Database not found at $DB_PATH"
    exit 1
fi

# Create backup using SQLite's backup command (safe for concurrent access)
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/$BACKUP_FILE'"

# Compress the backup
gzip "$BACKUP_DIR/$BACKUP_FILE"

# Remove old backups
find "$BACKUP_DIR" -name "pulse_queue_*.db.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_FILE.gz"
echo "Retained backups from last $RETENTION_DAYS days"
