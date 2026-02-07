# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.x.x   | :white_check_mark: |

As this project is in active development, security updates are provided for the latest version only.

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### Private Disclosure

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please use one of the following methods:

1. **GitHub Security Advisories** (Preferred): Use the "Report a vulnerability" button in the Security tab of this repository to privately report the issue.

2. **Email**: Contact the maintainers directly at the email address listed in the repository.

### What to Include

When reporting a vulnerability, please include:

- A description of the vulnerability
- Steps to reproduce the issue
- Potential impact assessment
- Any suggested fixes (if applicable)

### Response Timeline

- **Acknowledgment**: Within 48 hours of report
- **Initial Assessment**: Within 7 days
- **Fix Timeline**: Depends on severity (critical: ASAP, high: 14 days, medium: 30 days)

## Security Considerations

### Token Handling

- **API Tokens**: The `PULSE_API_TOKEN` should be a strong, randomly generated string. Never commit tokens to version control.
- **Telegram Bot Token**: Keep your `TELEGRAM_BOT_TOKEN` secret. Regenerate it via @BotFather if compromised.
- **Environment Variables**: Use `.env` files (gitignored) or secure secret management for all sensitive configuration.

### Network Security

- **Localhost Binding**: By default, the HTTP API binds to `127.0.0.1` (localhost only). This prevents external network access.
- **Production Deployment**: If exposing the API externally, use a reverse proxy (nginx, Caddy) with TLS termination.
- **Firewall**: Ensure appropriate firewall rules are in place for production deployments.

### Database Security

- **SQLite File Permissions**: The pulse queue database (`~/.reeve/pulse_queue.db`) contains scheduled tasks. Ensure appropriate file permissions (600 recommended).
- **No Sensitive Data in Prompts**: Avoid storing passwords or secrets in pulse prompts, as these are stored in plain text.

### MCP Server Security

- **Local Execution**: MCP servers run locally and communicate via stdio. They inherit the permissions of the parent process.
- **Tool Validation**: All MCP tool inputs are validated via Pydantic schemas before processing.

### Systemd Service Security

The Reeve services (`reeve-daemon`, `reeve-telegram`) run with security hardening:

- **Non-root execution**: Services run as the configured user, not root
- **Filesystem protection**: `ProtectSystem=strict`, `ProtectHome=read-only`
- **Privilege escalation prevention**: `NoNewPrivileges=true`
- **Limited write access**: Only specific paths in `ReadWritePaths` are writable

### Sudoers Configuration

The installer creates `/etc/sudoers.d/reeve` to allow passwordless service management. This is **safe** because:

1. **Services run as your user, not root**: Even with `sudo systemctl restart`, the service executes code as your regular user. There's no privilege escalation.

2. **Explicit command allowlist**: Only specific commands are permitted:
   - `systemctl status|start|stop|restart reeve-daemon|reeve-telegram`
   - `systemctl is-active|show reeve-daemon|reeve-telegram`
   - `journalctl -u reeve-daemon|reeve-telegram`

3. **Installed scripts are root-owned**: Helper scripts in `/usr/local/bin/` cannot be modified by the user, preventing injection attacks.

4. **No arbitrary command execution**: The sudoers rules don't allow wildcards for dangerous operations.

**Threat model**: If an attacker compromises your user account:
- They can restart the service (but it runs as your user anyway)
- They can modify code in the repo (but would need to restart service to execute it)
- They **cannot** escalate to root via the sudoers rules

## Security Best Practices for Users

1. **Keep Dependencies Updated**: Regularly run `uv sync` to get the latest security patches.
2. **Review Pulse Prompts**: Be cautious about what actions you schedule Reeve to perform.
3. **Limit Telegram Access**: Only configure your personal `TELEGRAM_CHAT_ID` to prevent unauthorized message processing.
4. **Monitor Logs**: Review logs at `~/.reeve/logs/` for unexpected activity.
