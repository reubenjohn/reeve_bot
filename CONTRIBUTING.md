# Contributing to Reeve Bot

Thank you for your interest in contributing to Reeve Bot! This guide will help you get started with development and submissions.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

Be respectful and constructive. We welcome contributors of all experience levels. Please:

- Be kind and patient with others
- Provide constructive feedback in reviews
- Focus on technical merits
- Help newcomers learn and grow

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Git
- SQLite 3

### Essential Reading

Before contributing, familiarize yourself with:

1. **[README.md](README.md)** - Project philosophy and vision
2. **[CLAUDE.md](CLAUDE.md)** - Implementation status, architecture, and development guidelines
3. **[docs/00_PROJECT_STRUCTURE.md](docs/00_PROJECT_STRUCTURE.md)** - Directory layout and component overview
4. **[docs/IMPLEMENTATION_ROADMAP.md](docs/IMPLEMENTATION_ROADMAP.md)** - Full implementation plan

## Development Setup

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/reeve-bot.git
cd reeve-bot
uv sync
```

### 2. Configure Environment

Create a `.env` file:

```bash
# Core configuration
REEVE_DESK_PATH=~/my_reeve
PULSE_DB_URL=sqlite+aiosqlite:///~/.reeve/pulse_queue.db

# API configuration
PULSE_API_PORT=8765
PULSE_API_TOKEN=dev-token-123

# Hapi configuration
HAPI_COMMAND=hapi
HAPI_BASE_URL=http://localhost:8080

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Logging
LOG_LEVEL=INFO
LOG_FILE=~/.reeve/logs/reeve.log
```

### 3. Initialize Database

```bash
uv run alembic upgrade head
```

### 4. Verify Setup

```bash
uv run pytest tests/ -v
```

All tests should pass (191/191 as of Phase 7).

## Development Workflow

### Branch Strategy

Create feature branches with descriptive names:

```bash
git checkout -b feature/your-feature-name
```

Branch prefixes:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test improvements

### Making Changes

1. **Read the code first** - Never propose changes to code you haven't read
2. **Follow existing patterns** - Match the style of surrounding code
3. **Write tests** - All new features and fixes need tests
4. **Update docs** - Keep documentation in sync with code changes
5. **Keep it simple** - See [Design Principles in CLAUDE.md](CLAUDE.md#design-principles)

### Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Specific test file
uv run pytest tests/test_pulse_queue.py -v

# With coverage
uv run pytest tests/ --cov=src/reeve --cov-report=html
```

### Interactive Testing

Use demo scripts to test functionality:

```bash
uv run python demos/phase2_queue_demo.py
uv run python demos/phase5_daemon_demo.py --mock
```

See [demos/README.md](demos/README.md) for details.

## Testing

### Testing Philosophy

- **High coverage**: Aim for >90% code coverage
- **Unit tests first**: Test components in isolation
- **Integration tests**: Test component interactions
- **Mock externals**: Mock HTTP APIs, file I/O, etc.
- **Async patterns**: Use pytest-asyncio for async code

### Test Organization

Tests are organized by component:

```
tests/
├── test_pulse_queue.py           # Queue operations
├── test_pulse_executor.py        # Pulse executor
├── test_pulse_daemon.py          # Daemon orchestration
├── test_api_server.py            # REST API
├── test_telegram_listener.py     # Telegram integration
└── test_phase*_validation.py     # Integration tests
```

### Writing Tests

Example test structure:

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_feature_success():
    """Test feature succeeds with valid parameters."""
    # Setup
    component = Component(config)

    # Execute
    result = await component.do_something()

    # Assert
    assert result is not None
    assert result.status == "success"
```

For detailed testing guidelines, see [CLAUDE.md](CLAUDE.md#testing-strategy).

## Code Style

### Formatting and Type Checking

We use industry-standard tools:

```bash
# Format code
uv run black src/ tests/
uv run isort src/ tests/

# Type check
uv run mypy src/
```

**Configuration**: Black (line length: 100), isort (profile: black), mypy (strict)

### Style Requirements

1. **Type hints required** - All functions must have complete type hints
2. **Docstrings required** - All public methods need docstrings
3. **Enums inherit from str** - For JSON serialization
4. **Error handling** - Use specific exceptions with helpful messages

For detailed style guidelines, see [CLAUDE.md](CLAUDE.md#code-style).

## Submitting Changes

### Commit Message Format

```
<type>: <short summary> (max 70 chars)

<detailed description of changes>

- Bullet points for specific changes
- Reference issue numbers (#123)

Co-Authored-By: Your Name <your.email@example.com>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Example**:

```
feat: Add priority-based pulse execution

Implement priority ordering in PulseQueue.get_due_pulses() to ensure
high-priority pulses execute first.

- Add CASE statement for priority ordering in SQL query
- Update tests to verify priority-based execution
- Add documentation for priority system

Fixes #42

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Pull Request Process

1. **Create PR** on GitHub with descriptive title
2. **Fill out template** with changes and context
3. **Link issues** using keywords (Fixes #123, Closes #456)
4. **Wait for review** - maintainers will review your code
5. **Address feedback** - make requested changes promptly
6. **Merge** - maintainer merges once approved

### Pre-submission Checklist

- [ ] All tests pass (`uv run pytest tests/ -v`)
- [ ] Code is formatted (`black` + `isort`)
- [ ] Type hints pass (`mypy src/`)
- [ ] Documentation is updated
- [ ] Commit messages follow format
- [ ] No breaking changes (or clearly documented)

## Reporting Issues

### Bug Reports

Include the following:

1. **Clear description** of the bug
2. **Steps to reproduce** with minimal example
3. **Expected vs actual behavior**
4. **Environment details** (OS, Python version, uv version)
5. **Logs and error messages** (relevant excerpts)
6. **Screenshots** (if applicable)

### Feature Requests

Include the following:

1. **Use case** - Why is this needed?
2. **Proposed solution** - How should it work?
3. **Alternatives considered** - Other approaches
4. **Additional context** - Examples, mockups, etc.

## Additional Resources

- **Architecture Overview**: [docs/00_PROJECT_STRUCTURE.md](docs/00_PROJECT_STRUCTURE.md)
- **Design Principles**: [CLAUDE.md#design-principles](CLAUDE.md#design-principles)
- **Implementation Phases**: [docs/IMPLEMENTATION_ROADMAP.md](docs/IMPLEMENTATION_ROADMAP.md)
- **Database Schema**: [docs/01_PULSE_QUEUE_DESIGN.md](docs/01_PULSE_QUEUE_DESIGN.md)
- **MCP Integration**: [docs/02_MCP_INTEGRATION.md](docs/02_MCP_INTEGRATION.md)

## Questions?

- Check documentation in `docs/`
- Search existing GitHub issues
- Open a new issue with the `question` label

## Recognition

Contributors are recognized through:
- Git commit history (Co-Authored-By tags)
- Release notes
- Contributors list in README.md

Thank you for contributing to Reeve Bot!
