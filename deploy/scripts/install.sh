#!/bin/bash
#
# Reeve Installation Script
# Installs systemd services, helper scripts, and configuration
#
# Usage: sudo ./install.sh
#
# Prerequisites:
#   - .env file must exist in repository root
#   - uv must be installed
#   - Dependencies installed (uv sync)
#   - Database migrated (uv run alembic upgrade head)
#

set -e

echo "=== Reeve Installation Script ==="
echo ""

# Check for root
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Get script directory (deploy/scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
REEVE_BOT_PATH="$(dirname "$DEPLOY_DIR")"

# Get the user who ran sudo (not root)
REEVE_USER="${SUDO_USER:-$(whoami)}"
REEVE_HOME="$(getent passwd "$REEVE_USER" | cut -d: -f6)/.reeve"

# Find uv
UV_PATH=$(which uv 2>/dev/null || echo "")
if [[ -z "$UV_PATH" ]]; then
    # Check common locations
    for path in "/home/$REEVE_USER/.local/bin/uv" "/home/$REEVE_USER/.cargo/bin/uv" "/usr/local/bin/uv"; do
        if [[ -x "$path" ]]; then
            UV_PATH="$path"
            break
        fi
    done
fi

# Display configuration
echo "Configuration:"
echo "  User:           $REEVE_USER"
echo "  Repo path:      $REEVE_BOT_PATH"
echo "  Data directory: $REEVE_HOME"
echo "  uv path:        $UV_PATH"
echo ""

# Validate prerequisites
echo "Validating prerequisites..."

if [[ -z "$UV_PATH" || ! -x "$UV_PATH" ]]; then
    echo "ERROR: uv not found. Please install uv first."
    exit 1
fi
echo "  uv: OK"

if [[ ! -f "$REEVE_BOT_PATH/.env" ]]; then
    echo "ERROR: .env file not found at $REEVE_BOT_PATH/.env"
    echo "       Please create it from .env.example"
    exit 1
fi
echo "  .env: OK"

# Create data directories
echo ""
echo "Creating directories..."
mkdir -p "$REEVE_HOME"/{logs,backups}
chown -R "$REEVE_USER:$REEVE_USER" "$REEVE_HOME"
echo "  Created $REEVE_HOME/{logs,backups}"

# Template substitution function
substitute_template() {
    local template="$1"
    local output="$2"

    sed -e "s|{{USER}}|${REEVE_USER}|g" \
        -e "s|{{REEVE_BOT_PATH}}|${REEVE_BOT_PATH}|g" \
        -e "s|{{REEVE_HOME}}|${REEVE_HOME}|g" \
        -e "s|{{UV_PATH}}|${UV_PATH}|g" \
        "$template" > "$output"
}

# Install systemd services
echo ""
echo "Installing systemd services..."

substitute_template "$DEPLOY_DIR/systemd/reeve-daemon.service.template" \
    "/etc/systemd/system/reeve-daemon.service"
echo "  Installed reeve-daemon.service"

substitute_template "$DEPLOY_DIR/systemd/reeve-telegram.service.template" \
    "/etc/systemd/system/reeve-telegram.service"
echo "  Installed reeve-telegram.service"

# Reload systemd
systemctl daemon-reload
echo "  Reloaded systemd daemon"

# Install helper scripts
echo ""
echo "Installing helper scripts..."

cp "$DEPLOY_DIR/scripts/reeve-health-check.sh" /usr/local/bin/reeve-health-check
chmod +x /usr/local/bin/reeve-health-check
echo "  Installed /usr/local/bin/reeve-health-check"

cp "$DEPLOY_DIR/scripts/reeve-backup.sh" /usr/local/bin/reeve-backup
chmod +x /usr/local/bin/reeve-backup
# Set REEVE_HOME in the backup script
sed -i "s|REEVE_HOME=\"\${REEVE_HOME:-\$HOME/.reeve}\"|REEVE_HOME=\"${REEVE_HOME}\"|" /usr/local/bin/reeve-backup
echo "  Installed /usr/local/bin/reeve-backup"

# Install logrotate config
echo ""
echo "Installing logrotate config..."
substitute_template "$DEPLOY_DIR/config/logrotate.conf.template" \
    "/etc/logrotate.d/reeve"
echo "  Installed /etc/logrotate.d/reeve"

# Enable and start services
echo ""
echo "Enabling services..."
systemctl enable reeve-daemon
echo "  Enabled reeve-daemon"
systemctl enable reeve-telegram
echo "  Enabled reeve-telegram"

echo ""
echo "Starting services..."
systemctl start reeve-daemon
echo "  Started reeve-daemon"

# Wait a moment for daemon to be ready before starting telegram
sleep 2
systemctl start reeve-telegram
echo "  Started reeve-telegram"

# Verify services
echo ""
echo "Verifying services..."
sleep 2

if systemctl is-active --quiet reeve-daemon; then
    echo "  reeve-daemon: RUNNING"
else
    echo "  reeve-daemon: FAILED"
    echo "  Check logs: journalctl -u reeve-daemon -n 50"
fi

if systemctl is-active --quiet reeve-telegram; then
    echo "  reeve-telegram: RUNNING"
else
    echo "  reeve-telegram: FAILED"
    echo "  Check logs: journalctl -u reeve-telegram -n 50"
fi

# Test API
echo ""
echo "Testing API..."
if curl -sf http://localhost:8765/api/health > /dev/null 2>&1; then
    echo "  API health check: OK"
else
    echo "  API health check: FAILED"
    echo "  The daemon may still be starting up. Try again in a few seconds."
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Useful commands:"
echo "  systemctl status reeve-daemon       # Check daemon status"
echo "  systemctl status reeve-telegram     # Check telegram status"
echo "  journalctl -u reeve-daemon -f       # Follow daemon logs"
echo "  /usr/local/bin/reeve-health-check   # Run health check"
echo "  /usr/local/bin/reeve-backup         # Run manual backup"
echo ""
echo "To set up cron jobs (optional):"
echo "  crontab -e"
echo "  # Add lines from: $DEPLOY_DIR/cron/reeve.cron.template"
