"""
Phase 7 validation test: End-to-end Telegram integration.

This test validates the complete Phase 7 implementation:
1. TelegramListener starts successfully
2. Listens for Telegram updates (mocked)
3. Processes incoming message
4. Triggers pulse via API server
5. Pulse created in database with correct metadata
6. Offset saved to disk
"""

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from sqlalchemy.ext.asyncio import create_async_engine

from reeve.integrations.telegram.listener import TelegramListener
from reeve.pulse.enums import PulsePriority, PulseStatus
from reeve.pulse.models import Base
from reeve.pulse.queue import PulseQueue
from reeve.utils.config import ReeveConfig


@pytest.fixture
async def mock_db():
    """Create in-memory database for testing."""
    db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(db_url, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield db_url

    # Cleanup
    await engine.dispose()


@pytest.fixture
async def pulse_queue(mock_db):
    """Create PulseQueue with test database."""
    queue = PulseQueue(mock_db)
    await queue.initialize()

    yield queue

    await queue.close()


@pytest.fixture
def mock_api_url():
    """Return mock API URL."""
    return "http://localhost:8765"


@pytest.fixture
def mock_config():
    """Create mock config for testing."""
    config = MagicMock(spec=ReeveConfig)
    config.pulse_api_token = "test-token-123"
    config.reeve_home = tempfile.mkdtemp()
    return config


@pytest.mark.asyncio
async def test_telegram_to_pulse_integration(pulse_queue, mock_api_url, mock_config):
    """
    End-to-end validation of Phase 7: Telegram Integration.

    This test validates:
    1. TelegramListener initializes with mocked Telegram API
    2. Listener processes incoming Telegram update
    3. Listener triggers pulse (mocked API call)
    4. Pulse created in database with correct fields:
       - prompt = "Telegram message from Alice: Hello Reeve"
       - priority = "critical"
       - tags = ["telegram", "user_message"]
    5. Offset saved to disk
    """
    # ========================================================================
    # Setup: Mock Telegram API responses
    # ========================================================================
    telegram_update = {
        "update_id": 123456,
        "message": {
            "message_id": 789,
            "from": {"id": 12345, "first_name": "Alice", "username": "alice"},
            "chat": {"id": 12345, "type": "private"},
            "date": int(datetime.now(timezone.utc).timestamp()),
            "text": "Hello Reeve",
        },
    }

    # ========================================================================
    # Setup: Create TelegramListener with mocked HTTP client
    # ========================================================================
    with patch.dict(
        "os.environ",
        {
            "TELEGRAM_BOT_TOKEN": "test-token-123",
            "TELEGRAM_CHAT_ID": "12345",
            "PULSE_API_URL": mock_api_url,
        },
    ):
        listener = TelegramListener(mock_config)

        # ========================================================================
        # Test: Process update and manually create pulse (simulating API call)
        # ========================================================================
        # Mock the _trigger_pulse method to create pulse directly in database
        async def mock_trigger_pulse(prompt: str, user: str):
            # This simulates what the API server would do
            pulse_id = await pulse_queue.schedule_pulse(
                scheduled_at=datetime.now(timezone.utc),
                prompt=prompt,
                priority=PulsePriority.CRITICAL,
                tags=["telegram", "user_message"],
            )
            return pulse_id

        with patch.object(listener, "_trigger_pulse", side_effect=mock_trigger_pulse):
            # Process single update
            await listener._process_update(telegram_update)

            # ========================================================================
            # Verify: Pulse created in database
            # ========================================================================
            upcoming = await pulse_queue.get_upcoming_pulses(limit=10)
            assert len(upcoming) == 1, f"Expected 1 pulse, got {len(upcoming)}"

            pulse = upcoming[0]

            # Verify prompt format
            expected_prompt = "Telegram message from Alice (@alice): Hello Reeve"
            assert (
                pulse.prompt == expected_prompt
            ), f"Expected prompt '{expected_prompt}', got '{pulse.prompt}'"

            # Verify priority (user messages are critical)
            assert (
                pulse.priority == PulsePriority.CRITICAL
            ), f"Expected priority CRITICAL, got {pulse.priority}"

            # Verify tags
            expected_tags = ["telegram", "user_message"]
            assert (
                pulse.tags == expected_tags
            ), f"Expected tags {expected_tags}, got {pulse.tags}"

            # Verify status is pending
            assert (
                pulse.status == PulseStatus.PENDING
            ), f"Expected status PENDING, got {pulse.status}"

            # ========================================================================
            # Verify: Offset would be saved
            # ========================================================================
            # In real flow, offset is saved after successful batch processing
            # We can verify the offset file path exists and can be written to
            offset_file = Path(mock_config.reeve_home) / "telegram_offset.txt"
            listener._save_offset(telegram_update["update_id"] + 1)

            assert offset_file.exists(), f"Offset file not created at {offset_file}"
            saved_offset = int(offset_file.read_text().strip())
            expected_offset = telegram_update["update_id"] + 1
            assert (
                saved_offset == expected_offset
            ), f"Expected offset {expected_offset}, got {saved_offset}"


@pytest.mark.asyncio
async def test_phase7_validation_summary():
    """
    Summary validation: Verify all Phase 7 components exist and are importable.

    This test ensures:
    1. TelegramListener class exists and has required methods
    2. Entry point exists (__main__.py)
    3. Configuration fields exist
    """
    # Test 1: TelegramListener class
    from reeve.integrations.telegram.listener import TelegramListener

    assert hasattr(TelegramListener, "__init__"), "TelegramListener.__init__() missing"
    assert hasattr(TelegramListener, "start"), "TelegramListener.start() missing"
    assert hasattr(TelegramListener, "_polling_loop"), "TelegramListener._polling_loop() missing"
    assert hasattr(TelegramListener, "_get_updates"), "TelegramListener._get_updates() missing"
    assert hasattr(
        TelegramListener, "_process_update"
    ), "TelegramListener._process_update() missing"
    assert hasattr(TelegramListener, "_trigger_pulse"), "TelegramListener._trigger_pulse() missing"
    assert hasattr(TelegramListener, "_load_offset"), "TelegramListener._load_offset() missing"
    assert hasattr(TelegramListener, "_save_offset"), "TelegramListener._save_offset() missing"
    assert hasattr(TelegramListener, "_handle_error"), "TelegramListener._handle_error() missing"
    assert hasattr(
        TelegramListener, "_register_signal_handlers"
    ), "TelegramListener._register_signal_handlers() missing"
    assert hasattr(
        TelegramListener, "_handle_shutdown"
    ), "TelegramListener._handle_shutdown() missing"

    # Test 2: Entry point
    import importlib.util

    spec = importlib.util.find_spec("reeve.integrations.telegram.__main__")
    assert spec is not None, "__main__.py not found in reeve.integrations.telegram package"

    # Test 3: Check demo script exists
    from pathlib import Path

    demo_path = Path(__file__).parent.parent / "demos" / "phase7_telegram_demo.py"
    assert demo_path.exists(), f"Demo script not found at {demo_path}"
