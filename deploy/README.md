# Reeve Bot Deployment

Quick-reference guide for deploying Reeve services.

## Directory Structure

```
deploy/
├── README.md                           # This file
├── systemd/
│   ├── reeve-daemon.service.template   # Pulse daemon service
│   └── reeve-telegram.service.template # Telegram listener service
├── config/
│   └── logrotate.conf.template         # Log rotation config
├── cron/
│   └── reeve.cron.template             # Scheduled tasks (heartbeat, health check, backup)
└── scripts/
    ├── install.sh                      # Main installation script
    ├── uninstall.sh                    # Cleanup script
    ├── reeve-heartbeat.sh              # Hourly heartbeat pulse
    ├── reeve-health-check.sh           # Health check helper
    ├── reeve-backup.sh                 # Database backup helper
    ├── reeve-status.sh                 # System health overview
    ├── reeve-logs.sh                   # Unified log viewer
    └── reeve-queue.sh                  # Pulse queue inspector
```

## Quick Install

```bash
# Install services (requires sudo)
sudo ./deploy/scripts/install.sh

# Verify installation
sudo systemctl status reeve-daemon
sudo systemctl status reeve-telegram

# Test API
curl http://localhost:8765/api/health
```

## Quick Uninstall

```bash
# Remove services (preserves data)
sudo ./deploy/scripts/uninstall.sh

# Remove data too
sudo ./deploy/scripts/uninstall.sh --purge
```

## Template Variables

Templates use `{{VAR}}` syntax, replaced during installation:

| Variable | Description | Example |
|----------|-------------|---------|
| `{{USER}}` | Service user | `reuben` |
| `{{REEVE_BOT_PATH}}` | Repo path | `/home/reuben/workspace/reeve-bot` |
| `{{REEVE_HOME}}` | Data directory | `/home/reuben/.reeve` |
| `{{REEVE_DESK_PATH}}` | User's Desk repo | `/home/reuben/reeve_desk` |
| `{{UV_PATH}}` | uv binary path | `/home/reuben/.local/bin/uv` |
| `{{EXTRA_RW_PATHS}}` | Extra writable dirs | `/home/reuben/.google_workspace_mcp` |

## Prerequisites

- Linux with systemd (Ubuntu 20.04+, Debian 11+)
- Python 3.11+
- uv package manager
- `.env` file configured

## File Locations

After installation:

| File | Location |
|------|----------|
| Daemon service | `/etc/systemd/system/reeve-daemon.service` |
| Telegram service | `/etc/systemd/system/reeve-telegram.service` |
| Log rotation | `/etc/logrotate.d/reeve` |
| Heartbeat script | `/usr/local/bin/reeve-heartbeat` |
| Health check | `/usr/local/bin/reeve-health-check` |
| Backup script | `/usr/local/bin/reeve-backup` |
| Status script | `/usr/local/bin/reeve-status` |
| Logs script | `/usr/local/bin/reeve-logs` |
| Queue script | `/usr/local/bin/reeve-queue` |

## Common Commands

```bash
# Start/stop services
sudo systemctl start reeve-daemon
sudo systemctl stop reeve-daemon
sudo systemctl restart reeve-daemon

# View logs
sudo journalctl -u reeve-daemon -f
sudo journalctl -u reeve-telegram -f

# Trigger heartbeat pulse
/usr/local/bin/reeve-heartbeat

# Run health check
/usr/local/bin/reeve-health-check

# Manual backup
/usr/local/bin/reeve-backup

# View cron jobs
crontab -l

# Debug tools
reeve-status              # System health overview
reeve-logs                # Follow daemon logs
reeve-logs telegram       # Follow telegram logs
reeve-queue               # Show pending pulses
reeve-queue failed        # Show failed pulses
```

## Troubleshooting

See [Debugging Guide](../docs/debugging.md) for debug tools and troubleshooting.

See [Deployment Guide](../docs/architecture/deployment.md) for systemd configuration details.
