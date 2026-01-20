# MCP Server Setup Guide

This guide explains how to configure the Reeve MCP servers for use with Claude Code.

## Prerequisites

1. **Claude Code CLI installed** and configured
2. **Reeve Bot project** set up at `/home/reuben/workspace/reeve_bot`
3. **Database initialized** (run `uv run alembic upgrade head`)
4. **Environment variables** configured (see `.env.example`)

## Step 1: Copy MCP Configuration

Copy the example MCP configuration to your Claude Code config directory:

```bash
# Create the config directory if it doesn't exist
mkdir -p ~/.config/claude-code

# Copy the example configuration
cp mcp_config.json.example ~/.config/claude-code/mcp_config.json
```

## Step 2: Update Configuration Paths

Edit `~/.config/claude-code/mcp_config.json` and update the following:

1. **Project path**: Replace `/home/reuben/workspace/reeve_bot` with your actual project path
2. **Database path**: Replace `/home/reuben/.reeve/pulse_queue.db` with your database path
3. **Telegram credentials**: Replace `your_bot_token_here` and `your_chat_id_here` with actual values

### Example Configuration

```json
{
  "mcpServers": {
    "pulse-queue": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/home/your_username/workspace/reeve_bot",
        "python",
        "-m",
        "reeve.mcp.pulse_server"
      ],
      "env": {
        "PULSE_DB_PATH": "/home/your_username/.reeve/pulse_queue.db"
      }
    },
    "telegram-notifier": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/home/your_username/workspace/reeve_bot",
        "python",
        "-m",
        "reeve.mcp.notification_server"
      ],
      "env": {
        "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        "TELEGRAM_CHAT_ID": "987654321"
      }
    }
  }
}
```

## Step 3: Get Telegram Credentials

### Get Bot Token

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Get Chat ID

1. Start a chat with your bot
2. Send any message to your bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find your `chat.id` in the JSON response (format: `987654321`)

## Step 4: Test the Configuration

### Test Pulse Queue Server

In a Claude Code session:

```
Can you list my upcoming pulses?
```

Claude should call the `list_upcoming_pulses` MCP tool. If no pulses exist, you'll see:

```
No upcoming pulses scheduled. The schedule is clear.
```

### Test Telegram Notifier

In a Claude Code session:

```
Can you send me a test notification?
```

Claude should call the `send_notification` MCP tool, and you should receive a Telegram message.

## Step 5: Verify MCP Servers Are Loaded

You can verify the servers are loaded by checking Claude Code's startup:

```bash
# Run Claude Code in verbose mode
claude-code --verbose
```

You should see logs indicating the MCP servers are starting.

## Troubleshooting

### Server Not Found

**Error**: `MCP server 'pulse-queue' not found`

**Solution**: Check that the configuration file exists at `~/.config/claude-code/mcp_config.json`

### Permission Denied

**Error**: `Permission denied: /home/reuben/workspace/reeve_bot`

**Solution**: Update the `--directory` path in the MCP config to your actual project path

### Import Error

**Error**: `ModuleNotFoundError: No module named 'reeve'`

**Solution**: Ensure you're using `uv run` (which activates the virtual environment automatically)

### Database Error

**Error**: `no such table: pulses`

**Solution**: Run Alembic migrations:

```bash
cd /home/reuben/workspace/reeve_bot
uv run alembic upgrade head
```

### Telegram Error

**Error**: `TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables are required`

**Solution**: Add the environment variables to the MCP config's `env` section

## Manual Testing (Without Claude Code)

You can test the MCP servers manually using stdio:

### Test Pulse Queue Server

```bash
cd /home/reuben/workspace/reeve_bot
uv run python -m reeve.mcp.pulse_server
```

The server will start and wait for JSON-RPC input on stdin.

### Test Telegram Notifier

```bash
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
cd /home/reuben/workspace/reeve_bot
uv run python -m reeve.mcp.notification_server
```

## Security Notes

1. **Bot Token**: Keep your Telegram bot token secret. Don't commit it to git.
2. **Chat ID**: Your chat ID is less sensitive but should still be kept private.
3. **MCP Config**: The `~/.config/claude-code/mcp_config.json` file is user-specific and not in git.

## Next Steps

Once MCP servers are working:

1. **Schedule your first pulse**: Ask Claude to schedule a test pulse
2. **Set up the daemon**: See [03_DAEMON_AND_API.md](03_DAEMON_AND_API.md)
3. **Deploy to production**: See [04_DEPLOYMENT.md](04_DEPLOYMENT.md)

## Available MCP Tools

### Pulse Queue Tools

- `schedule_pulse(scheduled_at, prompt, priority, ...)` - Schedule a new pulse
- `list_upcoming_pulses(limit, include_completed)` - List scheduled pulses
- `cancel_pulse(pulse_id)` - Cancel a pulse
- `reschedule_pulse(pulse_id, new_scheduled_at)` - Reschedule a pulse

### Telegram Notifier Tools

- `send_notification(message, priority, parse_mode, ...)` - Send a push notification
- `send_message_with_link(message, link_url, link_text, ...)` - Send notification with button

See the MCP server source code for complete documentation on each tool.
