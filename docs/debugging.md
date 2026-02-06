# Debugging and Monitoring Guide

This guide covers the debug and diagnostic tools available for monitoring and troubleshooting the Reeve system.

## Quick Reference

| Command | Description |
|---------|-------------|
| `reeve-status` | System health overview |
| `reeve-logs` | Unified log viewer |
| `reeve-queue` | Pulse queue inspector |
| `uv run python -m reeve.doctor` | Pre-flight configuration check |
| `uv run python -m reeve.debug.trigger_pulse` | Manual pulse trigger |

## Shell Scripts

These scripts are installed to `/usr/local/bin/` during deployment and can be run from anywhere.

### reeve-status - System Overview

Shows overall health of the Reeve system at a glance.

```bash
reeve-status
```

**Output:**
```
=== Reeve Status ===
Services:
  reeve-daemon:   [OK] running (pid 12345, uptime 2d 4h)
  reeve-telegram: [OK] running (pid 12346, uptime 2d 4h)

API: [OK] healthy (http://127.0.0.1:8765)

Pulse Queue:
  Pending: 2 | Overdue: 0 | Failed: 0

Recent Pulses (last 5):
  [122] [OK] 23:12 Hourly heartbeat (morning): Rev... - 45s
  [121] [OK] 23:11 Hourly heartbeat (morning): Rev... - 38s

Last Heartbeat: 23:12 (8 min ago) [OK]
Errors (last hour): 0
```

**What it checks:**
- Service status (reeve-daemon, reeve-telegram) with PID and uptime
- API health endpoint responsiveness
- Pulse queue statistics (pending, overdue, failed)
- Recent pulse execution history
- Last heartbeat timestamp and age
- Error count from journalctl

**Exit Codes:**
- 0: System healthy
- 1: Issues detected (service down, overdue pulses, failed pulses, stale heartbeat, errors in logs)

### reeve-logs - Unified Log Viewer

View logs from multiple sources with a single command.

```bash
reeve-logs              # Follow daemon logs (default)
reeve-logs daemon       # Follow daemon logs
reeve-logs telegram     # Follow telegram listener logs
reeve-logs heartbeat    # Tail heartbeat log file
reeve-logs all          # Interleave all logs
reeve-logs -n 50        # Show last 50 lines (no follow)
reeve-logs -n 100 telegram  # Last 100 telegram lines
```

**Sources:**
| Source | Description |
|--------|-------------|
| `daemon` | Reeve daemon logs via journalctl (default) |
| `telegram` | Telegram listener logs via journalctl |
| `heartbeat` | Heartbeat log file (`~/.reeve/logs/heartbeat.log`) |
| `credential-keepalive` | Credential keepalive log (`~/.reeve/logs/credential-keepalive.log`) |
| `all` | Interleave daemon + telegram + heartbeat |

**Options:**
| Option | Description |
|--------|-------------|
| `-n N` | Show last N lines without following |
| `-h` | Show help message |

### reeve-queue - Pulse Queue Inspector

Inspect and filter the pulse queue directly.

```bash
reeve-queue             # Show pending pulses (default)
reeve-queue pending     # Show pending pulses
reeve-queue failed      # Show failed pulses
reeve-queue completed   # Show recent completed pulses
reeve-queue overdue     # Show overdue pulses (past scheduled time)
reeve-queue all         # Show all recent pulses
reeve-queue 123         # Show details for pulse #123
```

**List View Output:**
```
=== Pending Pulses ===
ID    Priority  Scheduled          Prompt
--------------------------------------------------------------
123   normal    2026-02-04 00:00   Hourly heartbeat (morning): Review...
124   high      2026-02-04 00:05   Telegram message from Alice: Can we...

Total: 2 pending
```

**Detail View Output (reeve-queue 123):**
```
=== Pulse #123 ===

Status:      completed
Priority:    normal
Scheduled:   2026-02-04 00:00:00
Executed:    2026-02-04 00:00:02
Duration:    45s (45123ms)

Prompt:
  Hourly heartbeat (morning): Review calendar and check for updates

Tags: ["heartbeat", "morning"]

Created By:  heartbeat_cron
Created At:  2026-02-04 00:00:00
Session ID:  abc123-def456
Retries:     0 / 3
```

## Python Debug Tools

### reeve.doctor - Configuration Validator

Comprehensive pre-flight check that validates the entire Reeve stack before deployment or after configuration changes.

```bash
uv run python -m reeve.doctor
```

**Output:**
```
=== Reeve Doctor ===

Environment:
  [check] PULSE_API_TOKEN set
  [check] REEVE_DESK_PATH=/home/user/reeve_desk
  [check] PULSE_DB_URL configured
  ! HAPI_COMMAND not set (using default 'hapi')
  ! PULSE_API_PORT not set (using default 8765)

Database:
  [check] Database exists: /home/user/.reeve/pulse_queue.db
  [check] Can connect and query
  [check] Migrations current (07ce7ae63b4a)

MCP Configuration:
  [check] Config file: /home/user/.config/claude-code/mcp_config.json
  [check] pulse-queue server configured
  [check] telegram-notifier server configured

Desk Permissions:
  [check] Settings file: /home/user/reeve_desk/.claude/settings.json
  [check] mcp__pulse-queue__schedule_pulse allowed
  [check] mcp__pulse-queue__list_upcoming_pulses allowed
  [check] mcp__pulse-queue__cancel_pulse allowed
  [check] mcp__pulse-queue__reschedule_pulse allowed
  [check] mcp__telegram-notifier__send_notification allowed

Commands:
  [check] hapi command available (/usr/local/bin/hapi)
  [check] uv command available (/home/user/.local/bin/uv)

Services:
  [check] API responding at http://127.0.0.1:8765

All required checks passed! (2 warnings)
```

**Checks performed:**

| Category | Checks |
|----------|--------|
| Environment | `PULSE_API_TOKEN`, `REEVE_DESK_PATH`, `PULSE_DB_URL`, optional vars |
| Database | File exists, can connect, migrations at head |
| MCP Configuration | Config file exists, pulse-queue and telegram-notifier servers configured |
| Desk Permissions | Required MCP tool permissions in allow list |
| Commands | `hapi` and `uv` available in PATH |
| Services | API health endpoint check |

**Exit Codes:**
- 0: All required checks passed (may have warnings)
- 1: One or more required checks failed

### reeve.debug.trigger_pulse - Manual Pulse Trigger

Manually trigger pulses for testing without going through the daemon scheduler.

```bash
# Basic usage
uv run python -m reeve.debug.trigger_pulse "Test prompt"

# With priority
uv run python -m reeve.debug.trigger_pulse --priority high "Urgent test"

# Dry run (schedule and mark complete without calling Hapi)
uv run python -m reeve.debug.trigger_pulse --dry-run "Check what would happen"

# Schedule only (add to queue, don't execute)
uv run python -m reeve.debug.trigger_pulse --schedule-only "Execute later"

# Verbose output (show full stdout/stderr)
uv run python -m reeve.debug.trigger_pulse -v "Test with output"
```

**Options:**

| Option | Description |
|--------|-------------|
| `--priority` | Set priority: critical, high, normal (default), low, deferred |
| `--dry-run` | Schedule and mark complete without executing Hapi |
| `--schedule-only` | Only schedule to queue, don't execute |
| `-v, --verbose` | Show full stdout/stderr from execution |

**Use cases:**
- Testing pulse execution end-to-end
- Debugging Hapi/Claude Code integration
- Verifying queue operations
- Testing prompt formatting

## API Endpoints

Debug information is also available via the REST API:

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check (returns 200 if API is running) |
| `GET /api/pulse/{id}` | Get details for a specific pulse |
| `GET /api/pulse/list?status=X` | List pulses filtered by status |
| `GET /api/pulse/stats` | Queue statistics summary |
| `GET /api/stats` | Execution statistics |

**Example API calls:**
```bash
# Health check
curl http://localhost:8765/api/health

# Get pulse details
curl -H "Authorization: Bearer $PULSE_API_TOKEN" \
  http://localhost:8765/api/pulse/123

# List failed pulses
curl -H "Authorization: Bearer $PULSE_API_TOKEN" \
  http://localhost:8765/api/pulse/list?status=failed

# Queue statistics
curl -H "Authorization: Bearer $PULSE_API_TOKEN" \
  http://localhost:8765/api/pulse/stats
```

## Troubleshooting

### Common Issues

#### Daemon not starting

1. Run `uv run python -m reeve.doctor` to check configuration
2. Check systemd logs: `journalctl -u reeve-daemon -n 50`
3. Verify database migrations: `uv run alembic current`
4. Check `.env` file exists and is readable

#### Pulses not executing

1. Check for overdue pulses: `reeve-queue overdue`
2. Review daemon logs: `reeve-logs daemon`
3. Verify Hapi command: `which hapi` or check `$HAPI_COMMAND`
4. Test manually: `uv run python -m reeve.debug.trigger_pulse --dry-run "Test"`

#### Permission errors

1. Check Desk permissions: `cat $REEVE_DESK_PATH/.claude/settings.json`
2. Verify MCP config: `cat ~/.config/claude-code/mcp_config.json`
3. Run doctor to check all permissions: `uv run python -m reeve.doctor`

#### Heartbeat missing

1. Check cron is running: `crontab -l | grep reeve`
2. Review heartbeat log: `reeve-logs heartbeat -n 20`
3. Verify heartbeat script: `/usr/local/bin/reeve-heartbeat`
4. Check API is accessible from cron environment

#### Credential refresh failing

1. Check cron is running: `crontab -l | grep credential`
2. Review keepalive log: `cat ~/.reeve/logs/credential-keepalive.log`
3. Run manually: `/usr/local/bin/reeve-credential-keepalive`
4. Check credentials file exists: `ls -la ~/.claude/.credentials.json`
5. Verify python3 is available: `which python3`

#### API not responding

1. Check daemon is running: `systemctl status reeve-daemon`
2. Verify port is correct: `echo $PULSE_API_PORT` (default: 8765)
3. Test locally: `curl http://127.0.0.1:8765/api/health`
4. Check firewall rules if accessing remotely

### Log Locations

| Log | Location | Access |
|-----|----------|--------|
| Daemon logs | systemd journal | `journalctl -u reeve-daemon` |
| Telegram logs | systemd journal | `journalctl -u reeve-telegram` |
| Heartbeat log | `~/.reeve/logs/heartbeat.log` | `cat` or `reeve-logs heartbeat` |
| Health check log | `~/.reeve/logs/health_check.log` | `cat` |
| Credential keepalive log | `~/.reeve/logs/credential-keepalive.log` | `cat` |

### Database Inspection

For advanced debugging, you can query the database directly:

```bash
# Open database
sqlite3 ~/.reeve/pulse_queue.db

# View schema
.schema pulses

# Count pulses by status
SELECT status, COUNT(*) FROM pulses GROUP BY status;

# Find overdue pulses
SELECT id, scheduled_at, prompt FROM pulses
WHERE status='pending' AND scheduled_at < datetime('now');

# View recent failures with errors
SELECT id, executed_at, error_message FROM pulses
WHERE status='failed' ORDER BY executed_at DESC LIMIT 5;
```
