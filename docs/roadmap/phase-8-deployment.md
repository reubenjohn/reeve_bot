← [Back to Roadmap Index](index.md)

# Phase 8: Deployment ✅ COMPLETED

**Goal**: Production deployment with systemd.

**Status**: ✅ Completed

## Deliverables

- ✅ Daemon running as systemd service
- ✅ Telegram listener as systemd service
- ✅ Monitoring and backups configured
- ✅ Complete deployment documentation

## Implementation Summary

### Deploy Directory Structure

```
deploy/
├── README.md                           # Quick-reference guide
├── systemd/
│   ├── reeve-daemon.service.template   # Pulse daemon service
│   └── reeve-telegram.service.template # Telegram listener service
├── config/
│   └── logrotate.conf.template         # Log rotation config
├── cron/
│   └── reeve.cron.template             # Health check + backup cron jobs
└── scripts/
    ├── install.sh                      # Main installation script
    ├── uninstall.sh                    # Cleanup script
    ├── reeve-health-check.sh           # Health check helper
    └── reeve-backup.sh                 # Database backup helper
```

### Template Variables

Templates use `{{VAR}}` syntax, replaced during installation:

| Variable | Description |
|----------|-------------|
| `{{USER}}` | Service user |
| `{{REEVE_BOT_PATH}}` | Repo path |
| `{{REEVE_HOME}}` | Data directory |
| `{{UV_PATH}}` | uv binary path |

### Quick Install

```bash
sudo ./deploy/scripts/install.sh
```

### Quick Uninstall

```bash
sudo ./deploy/scripts/uninstall.sh
```

## Validation

```bash
# Check services
sudo systemctl status reeve-daemon
sudo systemctl status reeve-telegram

# Test end-to-end
# Send Telegram message → Reeve responds

# Check logs
sudo journalctl -u reeve-daemon -f
```

## Demo

### Step 1: Install as systemd services

```bash
# Run the deployment script
sudo bash demos/phase8_deployment_demo.sh

# Expected output:
# ✓ Created systemd service: reeve-daemon.service
# ✓ Created systemd service: reeve-telegram.service
# ✓ Reloaded systemd daemon
# ✓ Enabled reeve-daemon.service
# ✓ Enabled reeve-telegram.service
# ✓ Started reeve-daemon.service
# ✓ Started reeve-telegram.service
# ✓ Services are running
```

### Step 2: Verify services are running

```bash
sudo systemctl status reeve-daemon

# Expected output:
# ● reeve-daemon.service - Reeve Pulse Queue Daemon
#    Loaded: loaded (/etc/systemd/system/reeve-daemon.service; enabled)
#    Active: active (running) since Sun 2026-01-19 10:30:00 UTC; 5min ago
#    Main PID: 12345 (python)
#    Tasks: 3 (limit: 4915)
#    Memory: 45.2M
#    CGroup: /system.slice/reeve-daemon.service
#            └─12345 /usr/bin/python -m reeve.pulse
#
# Jan 19 10:30:00 hostname systemd[1]: Started Reeve Pulse Queue Daemon
# Jan 19 10:30:00 hostname python[12345]: INFO | Starting Pulse Daemon...
# Jan 19 10:30:00 hostname python[12345]: INFO | Scheduler loop started
```

### Step 3: Test end-to-end functionality

```bash
# Send a Telegram message
# Expected: Bot responds within a few seconds

# Check daemon logs
sudo journalctl -u reeve-daemon -n 50

# Expected to see pulse execution logs
```

### Step 4: Test automatic restart

```bash
# Simulate a crash
sudo kill -9 $(pgrep -f "reeve.pulse.daemon")

# Wait a few seconds, then check status
sleep 5
sudo systemctl status reeve-daemon

# Expected: Service should auto-restart
# Active: active (running) since Sun 2026-01-19 10:35:15 UTC; 2s ago
```

### Step 5: Verify monitoring and backups

```bash
# Check log rotation
ls -lh /var/log/reeve/

# Check database backup
ls -lh ~/.reeve/backups/

# Check health check cron
crontab -l | grep reeve

# Expected:
# */5 * * * * /usr/local/bin/reeve-health-check.sh
# 0 3 * * * /usr/local/bin/reeve-backup.sh
```

### Step 6: Graceful shutdown test

```bash
# Stop services
sudo systemctl stop reeve-daemon
sudo systemctl stop reeve-telegram

# Verify they stopped cleanly
sudo journalctl -u reeve-daemon -n 10

# Expected to see graceful shutdown logs:
# Jan 19 10:40:00 hostname python[12345]: INFO | Received shutdown signal
# Jan 19 10:40:00 hostname python[12345]: INFO | Waiting for running pulses...
# Jan 19 10:40:02 hostname python[12345]: INFO | Daemon shut down gracefully
```

---

**Previous**: [Phase 7: Telegram Integration](phase-7-telegram.md)

**Next**: [Phase 9: Integration Testing & Polish](phase-9-testing.md)
