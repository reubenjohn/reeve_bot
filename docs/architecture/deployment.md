# Deployment Guide

## Overview

This guide covers production deployment of the Pulse Daemon, including systemd service configuration, monitoring, logging, and troubleshooting.

> **Quick Start**: Use the [automated installer](#automated-installation-recommended) for one-command setup with passwordless service management.

## Prerequisites

- Linux system with systemd (Ubuntu 20.04+, Debian 11+, or similar)
- Python 3.11+ installed
- uv package manager installed
- Non-root user account for running the service

## Installation

### 1. Clone and Setup Repository

```bash
# Clone repository
cd ~
git clone https://github.com/yourusername/reeve-bot.git
cd reeve-bot

# Install dependencies
uv sync

# Create necessary directories
mkdir -p ~/.reeve/{logs,backups}

# Initialize database
uv run alembic upgrade head
```

### 2. Configure Environment

Create `.env` file in the repository root:

```bash
# Copy template
cp .env.example .env

# Edit configuration
nano .env
```

**Environment Variables** (`.env`):

```bash
# Database
PULSE_DB_PATH=~/.reeve/pulse_queue.db

# Hapi
HAPI_COMMAND=hapi
REEVE_DESK_PATH=~/my_reeve

# API
PULSE_API_HOST=127.0.0.1
PULSE_API_PORT=8765
PULSE_API_TOKEN=your_secure_random_token_here

# Executor
PULSE_MAX_CONCURRENT=1                  # Max concurrent pulse execution (default: 1)

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Logging
LOG_LEVEL=INFO
LOG_FILE=~/.reeve/logs/daemon.log
```

**Generate API Token**:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Test Manual Execution

Before setting up systemd, verify the daemon runs correctly:

```bash
# Start daemon
uv run python -m reeve.pulse

# In another terminal, test the API
curl http://localhost:8765/api/health

# Trigger a test pulse
curl -X POST http://localhost:8765/api/pulse/trigger \
  -H "Authorization: Bearer your_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Test pulse from curl",
    "scheduled_at": "now",
    "priority": "normal",
    "source": "manual_test"
  }'

# Check logs
tail -f ~/.reeve/logs/daemon.log
```

Stop the daemon with `Ctrl+C` if it's working correctly.

---

## Automated Installation (Recommended)

### Using the install.sh Script

The recommended way to deploy Reeve is using the automated installer:

```bash
# From the repository root
sudo ./deploy/scripts/install.sh
```

**What it installs**:
- ✅ Systemd service files (`reeve-daemon.service`, `reeve-telegram.service`)
- ✅ Helper scripts (`reeve-status`, `reeve-logs`, `reeve-queue`, etc.)
- ✅ Sudoers configuration for passwordless service management
- ✅ Log rotation configuration
- ✅ Cron jobs (hourly heartbeat, credential keep-alive)

**Passwordless Service Management**:

After installation, all service management commands run **without password prompts**:

```bash
# These work without entering a password:
reeve-status                        # System health overview
reeve-logs                          # View logs
reeve-logs -n 50                    # Last 50 lines
sudo systemctl restart reeve-daemon # Restart service
sudo journalctl -u reeve-daemon -f  # Follow logs
```

The installer creates `/etc/sudoers.d/reeve` with an explicit allowlist for:
- `systemctl status|start|stop|restart reeve-daemon|reeve-telegram`
- `systemctl is-active|show reeve-daemon|reeve-telegram`
- `journalctl -u reeve-daemon|reeve-telegram`

**Security**: Services run as your user (not root), so passwordless sudo doesn't create privilege escalation. See [SECURITY.md](../../SECURITY.md#sudoers-configuration) for details.

**Uninstallation**:
```bash
sudo ./deploy/scripts/uninstall.sh       # Remove services and scripts
sudo ./deploy/scripts/uninstall.sh --purge  # Also remove data directory
```

---

## Manual Systemd Service Setup

### 1. Create Service File

Create `/etc/systemd/system/reeve-daemon.service`:

```ini
[Unit]
Description=Reeve Pulse Daemon
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=reuben
Group=reuben
WorkingDirectory=/home/reuben/workspace/reeve-bot

# Use uv to run the daemon
ExecStart=/home/reuben/.local/bin/uv run python -m reeve.pulse

# Environment
EnvironmentFile=/home/reuben/workspace/reeve-bot/.env

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# Logging (stdout/stderr → journald)
StandardOutput=journal
StandardError=journal
SyslogIdentifier=reeve-daemon

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/reuben/.reeve

# Resource limits
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
```

**Notes**:
- Replace `/home/reuben/` with your actual home directory
- Adjust `User` and `Group` to your username
- `ReadWritePaths` allows daemon to write to `~/.reeve/` (database, logs)

### 2. Install and Enable Service

```bash
# Copy service file (as root)
sudo cp reeve-daemon.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable reeve-daemon

# Start service
sudo systemctl start reeve-daemon

# Check status
sudo systemctl status reeve-daemon
```

### 3. Verify Service is Running

```bash
# Check process
ps aux | grep "reeve.pulse.daemon"

# Check logs (no password prompt if using install.sh)
sudo journalctl -u reeve-daemon -f

# Test API
curl http://localhost:8765/api/health
```

> **Note**: If you used `install.sh`, `sudo` commands for reeve services won't prompt for a password.

---

## Telegram Listener Service

The Telegram listener runs as a separate service that POSTs to the Pulse API.

### 1. Create Service File

Create `/etc/systemd/system/reeve-telegram.service`:

```ini
[Unit]
Description=Reeve Telegram Listener
After=network.target reeve-daemon.service
Wants=network-online.target
Requires=reeve-daemon.service

[Service]
Type=simple
User=reuben
Group=reuben
WorkingDirectory=/home/reuben/workspace/reeve-bot

# Run Telegram listener
ExecStart=/home/reuben/.local/bin/uv run python -m reeve.integrations.telegram

# Environment
EnvironmentFile=/home/reuben/workspace/reeve-bot/.env

# Restart policy
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=reeve-telegram

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### 2. Install and Enable

```bash
sudo cp reeve-telegram.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable reeve-telegram
sudo systemctl start reeve-telegram
sudo systemctl status reeve-telegram
```

---

## Monitoring & Logging

### 1. View Logs

> **Note**: All `sudo journalctl` commands run without password prompt after `install.sh`.

**Daemon logs**:
```bash
# Real-time
sudo journalctl -u reeve-daemon -f

# Last 100 lines
sudo journalctl -u reeve-daemon -n 100

# Since boot
sudo journalctl -u reeve-daemon -b

# Filter by priority (errors only)
sudo journalctl -u reeve-daemon -p err

# Export to file
sudo journalctl -u reeve-daemon --since today > reeve-daemon.log
```

**Telegram listener logs**:
```bash
sudo journalctl -u reeve-telegram -f
```

**Application log file** (`~/.reeve/logs/daemon.log`):
```bash
tail -f ~/.reeve/logs/daemon.log
```

### 2. Log Rotation

Create `/etc/logrotate.d/reeve`:

```
/home/reuben/.reeve/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 reuben reuben
    sharedscripts
    postrotate
        systemctl reload reeve-daemon > /dev/null 2>&1 || true
    endscript
}
```

### 3. Health Monitoring

**Simple health check script** (`/usr/local/bin/reeve-health-check`):

```bash
#!/bin/bash

# Check if daemon is running
if ! systemctl is-active --quiet reeve-daemon; then
    echo "ERROR: reeve-daemon is not running"
    exit 1
fi

# Check API health
if ! curl -s http://localhost:8765/api/health > /dev/null; then
    echo "ERROR: API health check failed"
    exit 1
fi

echo "OK: All services healthy"
exit 0
```

**Add to cron** (check every 5 minutes):

```bash
# Edit crontab
crontab -e

# Add line:
*/5 * * * * /usr/local/bin/reeve-health-check || echo "Reeve health check failed" | mail -s "Reeve Alert" your@email.com
```

### 4. Hourly Heartbeat

The **hourly heartbeat** is the core of Reeve's proactive behavior. Every hour, a cron job schedules a pulse that wakes Reeve to check calendar, tasks, and messages - without waiting to be asked.

**Heartbeat script** (`/usr/local/bin/reeve-heartbeat`):

The script varies the prompt based on time of day:
- **Morning (6-12)**: Focus on daily priorities, calendar review
- **Afternoon (12-18)**: Upcoming meetings, pending tasks
- **Evening (18-22)**: End-of-day wrap-up, remaining tasks
- **Night (22-6)**: Light check, defer non-urgent items

**Add to cron** (every hour on the hour):

```bash
crontab -e

# Add:
0 * * * * /usr/local/bin/reeve-heartbeat >> ~/.reeve/logs/heartbeat.log 2>&1
```

**Manual trigger**:
```bash
/usr/local/bin/reeve-heartbeat
```

### 5. Credential Keep-Alive

The **credential keep-alive** prevents OAuth token expiry for services Reeve depends on. It uses a pluggable provider architecture - each credential type has its own provider script.

**Keep-alive script** (`/usr/local/bin/reeve-credential-keepalive`):

The script discovers provider scripts from `/usr/local/lib/reeve/credential-providers/`, checks each credential's health, and refreshes tokens that are close to expiring.

Current providers:
- **claude-code**: Refreshes Claude Code OAuth tokens from `~/.claude/.credentials.json`. Triggers refresh when the token expires within 6 hours.

**Add to cron** (every 4 hours):

```bash
crontab -e

# Add:
0 */4 * * * /usr/local/bin/reeve-credential-keepalive >> ~/.reeve/logs/credential-keepalive.log 2>&1
```

**Manual trigger**:
```bash
/usr/local/bin/reeve-credential-keepalive
```

### 6. Metrics (Optional)

For production monitoring, consider:

- **Prometheus + Grafana**: Expose metrics endpoint in FastAPI
- **Datadog/New Relic**: APM integration
- **Custom metrics**: Track pulse execution rate, failures, duration

**Example Prometheus metrics**:
```python
# In api/server.py
from prometheus_client import Counter, Histogram, generate_latest

pulses_executed = Counter('reeve_pulses_executed_total', 'Total pulses executed')
pulse_duration = Histogram('reeve_pulse_duration_seconds', 'Pulse execution duration')

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

---

## Database Management

### 1. Backups

**Automated backup script** (`/usr/local/bin/reeve-backup`):

```bash
#!/bin/bash

BACKUP_DIR="/home/reuben/.reeve/backups"
DB_PATH="/home/reuben/.reeve/pulse_queue.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup
sqlite3 "$DB_PATH" ".backup $BACKUP_DIR/pulse_queue_$TIMESTAMP.db"

# Compress
gzip "$BACKUP_DIR/pulse_queue_$TIMESTAMP.db"

# Keep only last 30 days
find "$BACKUP_DIR" -name "pulse_queue_*.db.gz" -mtime +30 -delete

echo "Backup completed: pulse_queue_$TIMESTAMP.db.gz"
```

**Add to cron** (daily at 3 AM):

```bash
crontab -e

# Add:
0 3 * * * /usr/local/bin/reeve-backup
```

### 2. Database Migrations

When upgrading Reeve to a new version with schema changes:

```bash
# Stop daemon
sudo systemctl stop reeve-daemon

# Backup database
/usr/local/bin/reeve-backup

# Run migrations
cd ~/workspace/reeve-bot
uv run alembic upgrade head

# Start daemon
sudo systemctl start reeve-daemon

# Verify
sudo systemctl status reeve-daemon
```

### 3. Database Inspection

```bash
# Open SQLite shell
sqlite3 ~/.reeve/pulse_queue.db

# Useful queries:
.tables
.schema pulses

SELECT COUNT(*) FROM pulses WHERE status = 'pending';
SELECT * FROM pulses ORDER BY scheduled_at DESC LIMIT 10;
SELECT priority, COUNT(*) FROM pulses GROUP BY priority;

# Exit
.quit
```

---

## Troubleshooting

### Problem: Daemon won't start

**Check logs**:
```bash
sudo journalctl -u reeve-daemon -xe
```

**Common issues**:

1. **Database locked**:
   ```
   sqlite3.OperationalError: database is locked
   ```
   - Solution: Kill any processes holding the DB lock
   ```bash
   lsof ~/.reeve/pulse_queue.db
   kill <PID>
   ```

2. **Missing dependencies**:
   ```
   ModuleNotFoundError: No module named 'reeve'
   ```
   - Solution: Reinstall dependencies
   ```bash
   cd ~/workspace/reeve-bot
   uv sync
   ```

3. **Permission denied**:
   ```
   PermissionError: [Errno 13] Permission denied: '/home/reuben/.reeve'
   ```
   - Solution: Fix ownership
   ```bash
   sudo chown -R reuben:reuben ~/.reeve
   chmod 755 ~/.reeve
   ```

### Problem: API not responding

**Check if port is bound**:
```bash
sudo netstat -tlnp | grep 8765
```

**Test locally**:
```bash
curl -v http://localhost:8765/api/health
```

**Check firewall**:
```bash
sudo ufw status
# If blocked, allow:
sudo ufw allow 8765/tcp
```

### Problem: Pulses not executing

**Check scheduler loop**:
```bash
sudo journalctl -u reeve-daemon | grep "Executing pulse"
```

**Query database for stuck pulses**:
```bash
sqlite3 ~/.reeve/pulse_queue.db "SELECT * FROM pulses WHERE status='processing' AND executed_at < datetime('now', '-5 minutes');"
```

**Manually reset stuck pulses**:
```sql
UPDATE pulses SET status='pending' WHERE status='processing' AND executed_at < datetime('now', '-10 minutes');
```

### Problem: Hapi execution fails

**Check Hapi installation**:
```bash
which hapi
hapi --version
```

**Check Desk path**:
```bash
ls -la ~/my_reeve/
```

**Test Hapi manually**:
```bash
cd ~/my_reeve
hapi run --text "Test prompt"
```

---

## Security Hardening

### 1. API Token Security

**Never commit `.env` to git**:
```bash
# Verify .gitignore
grep ".env" .gitignore
```

**Rotate API token regularly**:
```bash
# Generate new token
NEW_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Update .env
sed -i "s/PULSE_API_TOKEN=.*/PULSE_API_TOKEN=$NEW_TOKEN/" .env

# Restart services
sudo systemctl restart reeve-daemon reeve-telegram
```

### 2. Firewall Configuration

**Allow only local connections** (default):
```ini
# In .env
PULSE_API_HOST=127.0.0.1  # Localhost only
```

**If remote access needed**:
```bash
# Bind to all interfaces
PULSE_API_HOST=0.0.0.0

# Configure firewall to allow only specific IPs
sudo ufw allow from 192.168.1.0/24 to any port 8765
```

### 3. TLS/HTTPS (Optional)

For remote access, use a reverse proxy (nginx) with TLS:

```nginx
# /etc/nginx/sites-available/reeve
server {
    listen 443 ssl;
    server_name reeve.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/reeve.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/reeve.yourdomain.com/privkey.pem;

    location /api/ {
        proxy_pass http://127.0.0.1:8765/api/;
        proxy_set_header Authorization $http_authorization;
    }
}
```

---

## Upgrading

### Standard Upgrade Process

```bash
# 1. Stop services
sudo systemctl stop reeve-telegram reeve-daemon

# 2. Backup database
/usr/local/bin/reeve-backup

# 3. Pull latest code
cd ~/workspace/reeve-bot
git pull origin main

# 4. Update dependencies
uv sync

# 5. Run migrations
uv run alembic upgrade head

# 6. Restart services
sudo systemctl start reeve-daemon reeve-telegram

# 7. Verify
sudo systemctl status reeve-daemon
curl http://localhost:8765/api/health
```

### Rollback Procedure

If upgrade fails:

```bash
# 1. Stop services
sudo systemctl stop reeve-telegram reeve-daemon

# 2. Revert code
cd ~/workspace/reeve-bot
git checkout <previous-commit>

# 3. Restore database
cp ~/.reeve/backups/pulse_queue_TIMESTAMP.db.gz /tmp/
gunzip /tmp/pulse_queue_TIMESTAMP.db.gz
cp /tmp/pulse_queue_TIMESTAMP.db ~/.reeve/pulse_queue.db

# 4. Restart
sudo systemctl start reeve-daemon reeve-telegram
```

---

## Performance Tuning

### Database Optimization

**Enable WAL mode** (better concurrency):
```bash
sqlite3 ~/.reeve/pulse_queue.db "PRAGMA journal_mode=WAL;"
```

**Analyze and optimize**:
```bash
sqlite3 ~/.reeve/pulse_queue.db "ANALYZE;"
sqlite3 ~/.reeve/pulse_queue.db "VACUUM;"
```

### Resource Limits

Adjust systemd service limits:

```ini
# In reeve-daemon.service
MemoryMax=1G          # Increase if needed
CPUQuota=100%         # Use full core
LimitNOFILE=4096      # File descriptor limit
```

### Concurrency Tuning

Adjust daemon configuration:

```python
# In daemon.py _scheduler_loop()
pulses = await self.queue.get_due_pulses(limit=50)  # Process more at once
```

```python
# Enable parallel execution
for pulse in pulses:
    asyncio.create_task(self._execute_pulse(pulse))  # Don't await
```

---

## Summary

**Production Checklist**:

- ✅ Daemon running as systemd service
- ✅ Telegram listener as systemd service
- ✅ Daily database backups
- ✅ Log rotation configured
- ✅ Health monitoring in place
- ✅ Credential keep-alive configured
- ✅ API token secured
- ✅ Firewall configured
- ✅ Upgrade/rollback procedure documented

**Monitoring Dashboard** (to build):
- Pulses executed/hour
- Average execution time
- Failure rate
- Queue depth
- API response time

Your Pulse Queue system is now production-ready!
