#!/bin/bash
#
# Reeve Uninstall Script
# Removes systemd services and helper scripts
#
# Usage: sudo ./uninstall.sh [--purge]
#   --purge: Also remove data directory (~/.reeve)
#

set -e

PURGE=false
if [[ "$1" == "--purge" ]]; then
    PURGE=true
fi

echo "=== Reeve Uninstall Script ==="
echo ""

# Check for root
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Stop services
echo "Stopping services..."
systemctl stop reeve-telegram 2>/dev/null || true
systemctl stop reeve-daemon 2>/dev/null || true

# Disable services
echo "Disabling services..."
systemctl disable reeve-telegram 2>/dev/null || true
systemctl disable reeve-daemon 2>/dev/null || true

# Remove service files
echo "Removing service files..."
rm -f /etc/systemd/system/reeve-daemon.service
rm -f /etc/systemd/system/reeve-telegram.service

# Reload systemd
systemctl daemon-reload

# Remove helper scripts
echo "Removing helper scripts..."
rm -f /usr/local/bin/reeve-health-check
rm -f /usr/local/bin/reeve-backup
rm -f /usr/local/bin/reeve-heartbeat
rm -f /usr/local/bin/reeve-credential-keepalive

# Remove credential providers
rm -rf /usr/local/lib/reeve/credential-providers
rmdir /usr/local/lib/reeve 2>/dev/null || true

# Remove debug helper scripts
rm -f /usr/local/bin/reeve-status
rm -f /usr/local/bin/reeve-logs
rm -f /usr/local/bin/reeve-queue

# Remove logrotate config
echo "Removing logrotate config..."
rm -f /etc/logrotate.d/reeve

# Remove sudoers configuration
echo "Removing sudoers configuration..."
rm -f /etc/sudoers.d/reeve

echo ""
echo "Services and scripts removed."

if [[ "$PURGE" == true ]]; then
    echo ""
    echo "Purging data directory..."
    # Get the user who ran sudo (not root)
    SUDO_USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    if [[ -d "$SUDO_USER_HOME/.reeve" ]]; then
        rm -rf "$SUDO_USER_HOME/.reeve"
        echo "Removed $SUDO_USER_HOME/.reeve"
    fi
fi

echo ""
echo "Uninstall complete."
echo ""
echo "Note: Repository and .env file were not removed."
echo "To fully remove Reeve, delete the repository directory manually."
