#!/bin/bash
#
# Phase 8: Deployment Demo
#
# Demonstrates the deployment artifacts and installation process.
#
# Usage:
#   ./demos/phase8_deployment_demo.sh --mock    # Simulate installation (no sudo required)
#   sudo ./demos/phase8_deployment_demo.sh      # Real installation (requires sudo)
#

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="$REPO_DIR/deploy"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
MOCK_MODE=false
if [[ "$1" == "--mock" ]]; then
    MOCK_MODE=true
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}           Phase 8: Production Deployment Demo${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

if [[ "$MOCK_MODE" == true ]]; then
    echo -e "${YELLOW}Running in MOCK MODE (no system changes)${NC}"
    echo ""

    # Create temp directory for mock filesystem
    MOCK_ROOT=$(mktemp -d)
    trap "rm -rf $MOCK_ROOT" EXIT

    mkdir -p "$MOCK_ROOT/etc/systemd/system"
    mkdir -p "$MOCK_ROOT/etc/logrotate.d"
    mkdir -p "$MOCK_ROOT/usr/local/bin"
    mkdir -p "$MOCK_ROOT/home/mockuser/.reeve"/{logs,backups}

    # Mock configuration
    REEVE_USER="mockuser"
    REEVE_HOME="$MOCK_ROOT/home/mockuser/.reeve"
    REEVE_BOT_PATH="$REPO_DIR"
    UV_PATH="/home/mockuser/.local/bin/uv"

    echo -e "${GREEN}Step 1: Created mock filesystem${NC}"
    echo "  Root: $MOCK_ROOT"
    echo "  Directories:"
    find "$MOCK_ROOT" -type d | sed "s|$MOCK_ROOT|    |"
    echo ""

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

    echo -e "${GREEN}Step 2: Processing templates${NC}"
    echo ""

    # Process daemon service
    echo -e "  ${BLUE}reeve-daemon.service:${NC}"
    substitute_template "$DEPLOY_DIR/systemd/reeve-daemon.service.template" \
        "$MOCK_ROOT/etc/systemd/system/reeve-daemon.service"
    echo "  ─────────────────────────────────────────"
    head -20 "$MOCK_ROOT/etc/systemd/system/reeve-daemon.service"
    echo "  ... (truncated)"
    echo ""

    # Process telegram service
    echo -e "  ${BLUE}reeve-telegram.service:${NC}"
    substitute_template "$DEPLOY_DIR/systemd/reeve-telegram.service.template" \
        "$MOCK_ROOT/etc/systemd/system/reeve-telegram.service"
    echo "  ─────────────────────────────────────────"
    head -15 "$MOCK_ROOT/etc/systemd/system/reeve-telegram.service"
    echo "  ... (truncated)"
    echo ""

    # Process logrotate
    echo -e "  ${BLUE}logrotate.conf:${NC}"
    substitute_template "$DEPLOY_DIR/config/logrotate.conf.template" \
        "$MOCK_ROOT/etc/logrotate.d/reeve"
    echo "  ─────────────────────────────────────────"
    cat "$MOCK_ROOT/etc/logrotate.d/reeve"
    echo ""

    # Process cron
    echo -e "  ${BLUE}cron jobs:${NC}"
    substitute_template "$DEPLOY_DIR/cron/reeve.cron.template" \
        "$MOCK_ROOT/reeve.cron"
    echo "  ─────────────────────────────────────────"
    cat "$MOCK_ROOT/reeve.cron"
    echo ""

    echo -e "${GREEN}Step 3: Copying helper scripts${NC}"
    cp "$DEPLOY_DIR/scripts/reeve-health-check.sh" "$MOCK_ROOT/usr/local/bin/reeve-health-check"
    cp "$DEPLOY_DIR/scripts/reeve-backup.sh" "$MOCK_ROOT/usr/local/bin/reeve-backup"
    echo "  Copied reeve-health-check"
    echo "  Copied reeve-backup"
    echo ""

    echo -e "${GREEN}Step 4: Final mock filesystem structure${NC}"
    echo "  ─────────────────────────────────────────"
    find "$MOCK_ROOT" -type f | sed "s|$MOCK_ROOT||"
    echo ""

    echo -e "${GREEN}Step 5: Simulated systemd commands (not executed)${NC}"
    echo "  systemctl daemon-reload"
    echo "  systemctl enable reeve-daemon"
    echo "  systemctl enable reeve-telegram"
    echo "  systemctl start reeve-daemon"
    echo "  systemctl start reeve-telegram"
    echo ""

    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Mock deployment demo completed successfully!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "To perform a real installation, run:"
    echo "  sudo ./demos/phase8_deployment_demo.sh"
    echo ""
    echo "Or use the install script directly:"
    echo "  sudo ./deploy/scripts/install.sh"

else
    # Real mode - just run the install script
    echo -e "${YELLOW}Running in REAL MODE (requires sudo)${NC}"
    echo ""

    # Check for root
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}ERROR: Real mode requires root privileges${NC}"
        echo ""
        echo "Usage:"
        echo "  ./demos/phase8_deployment_demo.sh --mock    # No sudo required"
        echo "  sudo ./demos/phase8_deployment_demo.sh      # Real installation"
        exit 1
    fi

    # Run the install script
    echo "Running install script..."
    echo ""
    "$DEPLOY_DIR/scripts/install.sh"

    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Real deployment completed!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Verification commands:"
    echo "  sudo systemctl status reeve-daemon"
    echo "  sudo systemctl status reeve-telegram"
    echo "  curl http://localhost:8765/api/health"
    echo "  sudo journalctl -u reeve-daemon -n 20"
    echo ""
    echo "Test auto-restart:"
    echo "  sudo kill -9 \$(pgrep -f 'reeve.pulse')"
    echo "  sleep 5"
    echo "  sudo systemctl status reeve-daemon"
    echo ""
    echo "To uninstall:"
    echo "  sudo ./deploy/scripts/uninstall.sh"
fi
