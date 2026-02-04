# Project Reeve: The "Chief of Staff" Protocol

[![CI](https://github.com/reubenjohn/reeve-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/reubenjohn/reeve-bot/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/reubenjohn/reeve-bot/graph/badge.svg)](https://codecov.io/gh/reubenjohn/reeve-bot)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://reubenjohn.github.io/reeve-bot/)

> A proactive AI assistant that operates on a "Push" paradigm - anticipating needs and taking action rather than waiting for prompts.

**[Full Documentation](https://reubenjohn.github.io/reeve-bot/)** | [Architecture](https://reubenjohn.github.io/reeve-bot/01_PULSE_QUEUE_DESIGN/) | [MCP Setup](https://reubenjohn.github.io/reeve-bot/MCP_SETUP/) | [Contributing](CONTRIBUTING.md)

---

## Why Reeve?

Modern AI assistants are **passive** - they wait for prompts. Reeve is different:

- **Proactivity First**: Reeve anticipates needs based on time, context, and history. It initiates conversations.
- **Cognitive Offloading**: If you have to remember to ask the assistant, the assistant has failed.
- **The "Living" System**: Reeve runs continuously, organizing your digital life while you sleep.

## Key Concepts

### The Push Paradigm
Instead of waiting for commands, Reeve operates on a **Pulse** - scheduled wake-ups that let it check on your world and take action. [Learn more](https://reubenjohn.github.io/reeve-bot/#2-the-pulse-a-rhythm-of-existence)

### Proxy & Gatekeeper
Reeve acts as a **high-fidelity proxy** between you and the world:
- **Input Filter**: Reads the noise (group chats, emails) so you don't have to
- **Output Delegate**: Drafts replies, coordinates logistics, manages vendors
- **Gatekeeper**: Knows what deserves your attention vs. what can wait

[Learn more](https://reubenjohn.github.io/reeve-bot/#2-the-identity-proxy-gatekeeper)

### The Glass Box Principle
Unlike "black box" agents with hidden state, Reeve's entire mind is visible in **plain Markdown files**. You can literally open its brain, read it, and edit it. [Learn more](https://reubenjohn.github.io/reeve-bot/#4-transparent-personalization-the-glass-box-principle)

### The Desk
A Git-versioned repository of your Goals, Responsibilities, and Preferences - the shared workspace between you and Reeve. [Learn more](https://reubenjohn.github.io/reeve-bot/#1-the-desk-a-collaborative-workspace-the-library)

## Use Cases

### The Snowboarding Trip (Social Secretary)

**Scenario**: Weather agent detects 18" of powder at Mammoth.

**Reeve's Action**: Sends you a Telegram alert: *"Powder Alert: 18 inches forecast for Mammoth this weekend. Shall I check if the Shred Crew is free?"*

**Outcome**: Upon approval, messages the WhatsApp group, parses replies, summarizes headcount, offers to draft Airbnb booking. **Zero mental load.**

**Also see:**
- **Deep Work Defender** - Proactively blocks focus time, silences group chat noise, but breaks through for real emergencies
- **Adaptive Coach** - Detects burnout patterns and shifts from taskmaster to supporter

[Full use case details](https://reubenjohn.github.io/reeve-bot/#iii-use-cases-proxy-coach-gatekeeper-in-action)

## Architecture at a Glance

| Component | Purpose |
|-----------|---------|
| **Pulse Queue** | SQLite-backed scheduler for proactive wake-ups |
| **MCP Servers** | Tools for Reeve to schedule pulses and send notifications |
| **Telegram Integration** | User messages trigger immediate high-priority pulses |
| **The Desk** | Git repo of Goals/, Responsibilities/, Preferences/ |

Reeve wraps specialized CLIs ([Claude Code](https://claude.com/claude-code), [Hapi](https://github.com/tiann/hapi)) rather than implementing its own agent loop - letting billion-dollar companies compete on that while we focus on **orchestration** and **context hygiene**.

[Full architecture docs](https://reubenjohn.github.io/reeve-bot/01_PULSE_QUEUE_DESIGN/)

## Quick Start

```bash
# Clone and install
git clone https://github.com/reubenjohn/reeve-bot.git
cd reeve-bot
uv sync

# Run migrations
uv run alembic upgrade head

# Run tests
uv run pytest tests/ -v

# Start the daemon (requires configuration)
export PULSE_API_TOKEN=your-secret-token
uv run python -m reeve.pulse
```

[Full installation guide](https://reubenjohn.github.io/reeve-bot/IMPLEMENTATION_ROADMAP/#quick-start)

## Reeve vs. OpenClaw

[OpenClaw](https://github.com/openclaw/openclaw) (157k+ stars) is an excellent all-in-one runtime. Reeve takes a different architectural bet:

| | OpenClaw | Reeve |
|---|---------|-------|
| **Paradigm** | Custom runtime | Orchestrator wrapping CLIs |
| **Session** | Continuous context | Isolated per wake-up |
| **Observability** | Debug via logs | **Glass Box**: inspect & edit in real-time |
| **Rollback** | Filesystem writes | Git-versioned Desk = Undo button |

[Full comparison](https://reubenjohn.github.io/reeve-bot/OpenClaw_COMPARISON/)

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Before diving in, consider the [strategic questions](https://reubenjohn.github.io/reeve-bot/OpenClaw_COMPARISON/) facing the project - feedback on architectural trade-offs is especially valuable.

## License

AGPL-3.0 License - see [LICENSE](LICENSE) for details.
