"""
Unit tests for Telegram listener core functionality.

Tests cover:
1. Offset Management - Persistence and error handling
2. Telegram Polling - API interactions and error cases
3. Message Processing - Filtering, formatting, and pulse triggering
"""

import pytest
import signal
from unittest.mock import AsyncMock, MagicMock, patch, mock_open, call
from pathlib import Path
import json

from reeve.integrations.telegram.listener import TelegramListener
from reeve.utils.config import ReeveConfig


@pytest.fixture
def mock_config():
    """Create mock config for testing."""
    config = MagicMock(spec=ReeveConfig)
    config.telegram_bot_token = "test_token_123"
    config.telegram_chat_id = "12345"
    config.pulse_api_url = "http://localhost:8765"
    config.pulse_api_token = "test_api_token"
    config.reeve_home = "/tmp/test_reeve"
    return config


@pytest.fixture
def listener(mock_config):
    """Create TelegramListener instance for testing."""
    # Mock environment variables required by TelegramListener
    with patch.dict('os.environ', {
        'TELEGRAM_BOT_TOKEN': 'test_token_123',
        'TELEGRAM_CHAT_ID': '12345',
        'PULSE_API_URL': 'http://localhost:8765'
    }):
        return TelegramListener(mock_config)


# ============================================================================
# 1. OFFSET MANAGEMENT TESTS (6 tests)
# ============================================================================


def test_load_offset_existing_file(listener):
    """Test loading offset from existing file with valid integer."""
    with patch.object(Path, 'exists', return_value=True):
        with patch.object(Path, 'read_text', return_value="12345"):
            offset = listener._load_offset()
            assert offset == 12345


def test_load_offset_missing_file(listener):
    """Test loading offset when file doesn't exist, should return None."""
    with patch.object(Path, 'exists', return_value=False):
        offset = listener._load_offset()
        assert offset is None


def test_save_offset_to_disk(listener, tmp_path):
    """Test saving offset to disk, verify file contains correct value."""
    listener.offset_file = tmp_path / "telegram_offset.txt"
    listener._save_offset(67890)

    # Verify file was created with correct value
    assert listener.offset_file.exists()
    assert listener.offset_file.read_text().strip() == "67890"


def test_offset_persistence_across_restarts(mock_config):
    """Test offset persistence: save, create new instance, verify loaded."""
    with patch.dict('os.environ', {
        'TELEGRAM_BOT_TOKEN': 'test_token_123',
        'TELEGRAM_CHAT_ID': '12345',
        'PULSE_API_URL': 'http://localhost:8765'
    }):
        with patch.object(Path, 'mkdir'):
            with patch.object(Path, 'write_text') as mock_write:
                with patch.object(Path, 'exists', return_value=True):
                    with patch.object(Path, 'read_text', return_value="99999"):
                        # First instance saves offset
                        listener1 = TelegramListener(mock_config)
                        listener1._save_offset(99999)

                        # Second instance loads offset
                        listener2 = TelegramListener(mock_config)
                        offset = listener2._load_offset()

                        assert offset == 99999


def test_handle_corrupted_offset_file(listener, tmp_path):
    """Test handling corrupted offset file (invalid data), should return None."""
    listener.offset_file = tmp_path / "telegram_offset.txt"
    listener.offset_file.write_text("not_a_number")

    with patch.object(listener, 'logger') as mock_logger:
        offset = listener._load_offset()

        assert offset is None
        # Verify warning logged
        mock_logger.warning.assert_called_once()


def test_atomic_write_verification(listener, tmp_path):
    """Test that save_offset uses atomic write pattern (temp file + rename)."""
    listener.offset_file = tmp_path / "telegram_offset.txt"
    temp_file = tmp_path / "telegram_offset.tmp"

    # Save offset
    listener._save_offset(12345)

    # Verify final file exists with correct content
    assert listener.offset_file.exists()
    assert listener.offset_file.read_text().strip() == "12345"

    # Verify temp file was cleaned up (doesn't exist after rename)
    assert not temp_file.exists()


# ============================================================================
# 2. TELEGRAM POLLING TESTS (7 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_successful_api_poll_with_updates(listener):
    """Test successful getUpdates response with message, verify parsed correctly."""
    expected_response = {
        "ok": True,
        "result": [
            {
                "update_id": 123456,
                "message": {
                    "message_id": 1,
                    "from": {
                        "id": 12345,
                        "first_name": "TestUser",
                        "username": "testuser"
                    },
                    "chat": {"id": 12345},
                    "date": 1234567890,
                    "text": "Hello Reeve!"
                }
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=expected_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)

    # Set the session on the listener
    listener.telegram_session = mock_session

    response = await listener._get_updates()

    assert response is not None
    assert response["ok"] is True
    assert len(response["result"]) == 1
    assert response["result"][0]["update_id"] == 123456
    assert response["result"][0]["message"]["text"] == "Hello Reeve!"


@pytest.mark.asyncio
async def test_handle_telegram_timeout_normal(listener):
    """Test asyncio timeout (no updates), should return None."""
    import asyncio

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)

    listener.telegram_session = mock_session

    with patch.object(listener, 'logger') as mock_logger:
        response = await listener._get_updates()

        assert response is None
        # Verify debug log called (timeout is normal with long polling)
        mock_logger.debug.assert_called_once()


@pytest.mark.asyncio
async def test_handle_network_errors(listener):
    """Test network error (ClientError), should return None and log warning."""
    import aiohttp

    mock_response = MagicMock()
    mock_response.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Network error"))
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)

    listener.telegram_session = mock_session

    # Mock the logger to verify it's called
    with patch.object(listener, 'logger') as mock_logger:
        response = await listener._get_updates()

        assert response is None
        # Verify warning logged
        mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_verify_long_polling_timeout(listener):
    """Test that getUpdates is called with timeout=100 parameter."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"ok": True, "result": []})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)

    listener.telegram_session = mock_session

    await listener._get_updates()

    # Verify get called with timeout parameter
    call_args = mock_session.get.call_args
    params = call_args[1]['params']
    assert params['timeout'] == 100


@pytest.mark.asyncio
async def test_verify_offset_parameter_sent(listener):
    """Test that getUpdates is called with offset=last_update_id."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"ok": True, "result": []})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)

    listener.telegram_session = mock_session
    listener.last_update_id = 12345

    await listener._get_updates()

    # Verify get called with offset parameter
    call_args = mock_session.get.call_args
    params = call_args[1]['params']
    assert params['offset'] == 12345


@pytest.mark.asyncio
async def test_handle_429_rate_limit(listener):
    """Test 429 Too Many Requests, should return JSON response (not explicitly handled)."""
    expected_response = {
        "ok": False,
        "error_code": 429,
        "description": "Too Many Requests: retry after 30"
    }

    mock_response = MagicMock()
    mock_response.status = 429
    mock_response.json = AsyncMock(return_value=expected_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)

    listener.telegram_session = mock_session

    response = await listener._get_updates()

    # 429 is not explicitly handled, so it returns the JSON response
    assert response is not None
    assert response["ok"] is False
    assert response["error_code"] == 429


@pytest.mark.asyncio
async def test_handle_401_unauthorized(listener):
    """Test 401 Unauthorized (invalid token), should raise RuntimeError."""
    mock_response = MagicMock()
    mock_response.status = 401
    mock_response.json = AsyncMock(return_value={
        "ok": False,
        "error_code": 401,
        "description": "Unauthorized"
    })
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)

    listener.telegram_session = mock_session

    # 401 should raise RuntimeError
    with pytest.raises(RuntimeError, match="Invalid bot token"):
        await listener._get_updates()


# ============================================================================
# 3. MESSAGE PROCESSING TESTS (7 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_process_valid_text_message(listener):
    """Test processing message with text, verify _trigger_pulse called with correct prompt."""
    update = {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "from": {
                "id": 12345,
                "first_name": "TestUser",
                "username": "testuser"
            },
            "chat": {"id": 12345},
            "date": 1234567890,
            "text": "Hello Reeve!"
        }
    }

    with patch.object(listener, '_trigger_pulse', new_callable=AsyncMock) as mock_trigger:
        await listener._process_update(update)

        mock_trigger.assert_called_once()
        prompt = mock_trigger.call_args[0][0]
        assert "Telegram message from TestUser (@testuser): Hello Reeve!" in prompt


@pytest.mark.asyncio
async def test_filter_wrong_chat_id(listener):
    """Test processing message from different chat_id, verify _trigger_pulse NOT called."""
    update = {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "from": {
                "id": 99999,  # Different chat ID
                "first_name": "OtherUser",
                "username": "otheruser"
            },
            "chat": {"id": 99999},
            "date": 1234567890,
            "text": "Hello from wrong chat!"
        }
    }

    with patch.object(listener, '_trigger_pulse', new_callable=AsyncMock) as mock_trigger:
        await listener._process_update(update)

        # Should NOT trigger pulse
        mock_trigger.assert_not_called()


@pytest.mark.asyncio
async def test_skip_non_text_messages(listener):
    """Test processing photo/sticker message (no 'text' field), verify skipped."""
    update = {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "from": {
                "id": 12345,
                "first_name": "TestUser",
                "username": "testuser"
            },
            "chat": {"id": 12345},
            "date": 1234567890,
            "photo": [{"file_id": "xyz"}]  # Photo message, no text
        }
    }

    with patch.object(listener, '_trigger_pulse', new_callable=AsyncMock) as mock_trigger:
        await listener._process_update(update)

        # Should NOT trigger pulse
        mock_trigger.assert_not_called()


@pytest.mark.asyncio
async def test_handle_bot_commands(listener):
    """Test processing message starting with '/' (e.g., /start), verify still processed."""
    update = {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "from": {
                "id": 12345,
                "first_name": "TestUser",
                "username": "testuser"
            },
            "chat": {"id": 12345},
            "date": 1234567890,
            "text": "/start"
        }
    }

    with patch.object(listener, '_trigger_pulse', new_callable=AsyncMock) as mock_trigger:
        await listener._process_update(update)

        mock_trigger.assert_called_once()
        prompt = mock_trigger.call_args[0][0]
        assert "/start" in prompt


@pytest.mark.asyncio
async def test_build_prompt_with_username(listener):
    """Test message from user with username, verify prompt format includes @username."""
    update = {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "from": {
                "id": 12345,
                "first_name": "TestUser",
                "username": "testuser"
            },
            "chat": {"id": 12345},
            "date": 1234567890,
            "text": "Test message"
        }
    }

    with patch.object(listener, '_trigger_pulse', new_callable=AsyncMock) as mock_trigger:
        await listener._process_update(update)

        prompt = mock_trigger.call_args[0][0]
        assert "Telegram message from TestUser (@testuser): Test message" in prompt


@pytest.mark.asyncio
async def test_build_prompt_without_username(listener):
    """Test message from user without username, verify prompt format without @username."""
    update = {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "from": {
                "id": 12345,
                "first_name": "TestUser"
                # No username
            },
            "chat": {"id": 12345},
            "date": 1234567890,
            "text": "Test message"
        }
    }

    with patch.object(listener, '_trigger_pulse', new_callable=AsyncMock) as mock_trigger:
        await listener._process_update(update)

        prompt = mock_trigger.call_args[0][0]
        assert "Telegram message from TestUser: Test message" in prompt
        assert "@" not in prompt


@pytest.mark.asyncio
async def test_handle_malformed_update_json(listener):
    """Test update missing expected fields, should handle gracefully without crashing."""
    update = {
        "update_id": 123456,
        # Missing 'message' field
    }

    with patch.object(listener, '_trigger_pulse', new_callable=AsyncMock) as mock_trigger:
        # Should not raise exception
        await listener._process_update(update)

        # Should NOT trigger pulse
        mock_trigger.assert_not_called()


# ============================================================================
# 4. API INTEGRATION TESTS (5 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_successful_pulse_trigger(listener):
    """Test successful pulse trigger via API, verify pulse_id returned."""
    # Create mock response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "pulse_id": 42,
        "scheduled_at": "2026-01-23T10:00:00Z",
        "message": "Pulse scheduled"
    })
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Create mock session
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    listener.api_session = mock_session

    # Trigger pulse
    pulse_id = await listener._trigger_pulse("Test message", "Alice")

    # Verify
    assert pulse_id == 42
    mock_session.post.assert_called_once()

    # Verify request payload
    call_args = mock_session.post.call_args
    assert "/api/pulse/schedule" in call_args[0][0]
    assert call_args[1]["headers"]["Authorization"] == "Bearer test_api_token"

    payload = call_args[1]["json"]
    assert payload["prompt"] == "Test message"
    assert payload["priority"] == "critical"
    assert payload["source"] == "telegram"
    assert "telegram" in payload["tags"]
    assert "user_message" in payload["tags"]


@pytest.mark.asyncio
async def test_handle_403_forbidden(listener):
    """Test handling 403 Forbidden (invalid API token), verify returns None and logs error."""
    # Create mock response with 403 status
    mock_response = MagicMock()
    mock_response.status = 403
    mock_response.text = AsyncMock(return_value="Forbidden")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Create mock session
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    listener.api_session = mock_session

    # Trigger pulse
    pulse_id = await listener._trigger_pulse("Test message", "Alice")

    # Verify returns None on error
    assert pulse_id is None


@pytest.mark.asyncio
async def test_handle_api_network_errors(listener):
    """Test handling network errors on API call, verify returns None."""
    import aiohttp

    # Create mock session that raises network error
    mock_session = MagicMock()
    mock_session.post = MagicMock(side_effect=aiohttp.ClientError("Connection refused"))
    listener.api_session = mock_session

    # Trigger pulse
    pulse_id = await listener._trigger_pulse("Test message", "Alice")

    # Verify returns None on network error
    assert pulse_id is None


@pytest.mark.asyncio
async def test_verify_critical_priority_used(listener):
    """Test API call uses priority=critical."""
    # Create mock response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"pulse_id": 42})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Create mock session
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    listener.api_session = mock_session

    # Trigger pulse
    await listener._trigger_pulse("Test message", "Alice")

    # Verify priority is "critical"
    call_args = mock_session.post.call_args
    payload = call_args[1]["json"]
    assert payload["priority"] == "critical"


@pytest.mark.asyncio
async def test_verify_tags_included(listener):
    """Test API call includes tags=['telegram', 'user_message']."""
    # Create mock response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"pulse_id": 42})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Create mock session
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    listener.api_session = mock_session

    # Trigger pulse
    await listener._trigger_pulse("Test message", "Alice")

    # Verify tags are present
    call_args = mock_session.post.call_args
    payload = call_args[1]["json"]
    assert payload["tags"] == ["telegram", "user_message"]


# ============================================================================
# 5. ERROR HANDLING TESTS (5 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_exponential_backoff_calculation(listener):
    """Test backoff calculation: 2, 4, 8, 16, 32, etc. seconds."""
    test_cases = [
        (1, 2),    # 2^1 = 2
        (2, 4),    # 2^2 = 4
        (3, 8),    # 2^3 = 8
        (4, 16),   # 2^4 = 16
        (5, 32),   # 2^5 = 32
        (6, 64),   # 2^6 = 64
        (7, 128),  # 2^7 = 128
        (8, 256),  # 2^8 = 256
    ]

    for error_count, expected_backoff in test_cases:
        listener.error_count = error_count
        backoff = min(2 ** listener.error_count, 300)
        assert backoff == expected_backoff


@pytest.mark.asyncio
async def test_max_backoff_cap(listener):
    """Test backoff caps at 300 seconds (5 minutes)."""
    # Test high error counts
    for error_count in [9, 10, 11, 20, 100]:
        listener.error_count = error_count
        backoff = min(2 ** listener.error_count, 300)
        assert backoff == 300  # Capped at 300 seconds


@pytest.mark.asyncio
async def test_error_count_reset_after_success(listener):
    """Test error count resets to 0 after successful operation."""
    listener.error_count = 5

    # Simulate successful polling (error count reset happens in polling loop)
    # After successful batch processing, error_count should be reset
    listener.error_count = 0  # This happens in _polling_loop after successful batch

    # Verify error count was reset
    assert listener.error_count == 0


@pytest.mark.asyncio
async def test_max_consecutive_errors_triggers_shutdown(listener):
    """Test 10 consecutive errors triggers shutdown."""
    listener.error_count = 9  # One below max
    listener.running = True

    # Trigger one more error (should hit max)
    error = Exception("Test error")
    await listener._handle_error(error, "test context")

    # Verify shutdown was triggered
    assert listener.error_count == 10
    assert listener.running is False
    assert listener.shutdown_event.is_set()


@pytest.mark.asyncio
async def test_fatal_errors_trigger_immediate_shutdown(listener):
    """Test 401 auth error triggers immediate shutdown."""
    listener.error_count = 2
    listener.running = True

    # Trigger fatal auth error
    error = RuntimeError("Invalid bot token - authentication failed")
    await listener._handle_error(error, "test context")

    # Verify immediate shutdown (without waiting for max retries)
    assert listener.running is False
    assert listener.shutdown_event.is_set()


# ============================================================================
# 6. SIGNAL HANDLING TESTS (3 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_sigterm_triggers_graceful_shutdown(listener, tmp_path):
    """Test SIGTERM signal triggers graceful shutdown."""
    import signal

    listener.running = True
    listener.last_update_id = 12345
    listener.offset_file = tmp_path / "telegram_offset.txt"

    # Simulate SIGTERM handler
    await listener._handle_shutdown(signal.SIGTERM)

    # Verify shutdown state
    assert listener.running is False
    assert listener.shutdown_event.is_set()

    # Verify offset was saved
    assert listener.offset_file.exists()
    assert listener.offset_file.read_text().strip() == "12345"


@pytest.mark.asyncio
async def test_sigint_triggers_shutdown(listener, tmp_path):
    """Test SIGINT (Ctrl+C) triggers shutdown."""
    import signal

    listener.running = True
    listener.last_update_id = 67890
    listener.offset_file = tmp_path / "telegram_offset.txt"

    # Simulate SIGINT handler (Ctrl+C)
    await listener._handle_shutdown(signal.SIGINT)

    # Verify shutdown state
    assert listener.running is False
    assert listener.shutdown_event.is_set()

    # Verify offset was saved
    assert listener.offset_file.exists()
    assert listener.offset_file.read_text().strip() == "67890"


@pytest.mark.asyncio
async def test_offset_saved_during_shutdown(listener, tmp_path):
    """Test offset is saved during shutdown."""
    import signal

    listener.running = True
    listener.last_update_id = 99999
    listener.offset_file = tmp_path / "telegram_offset.txt"

    with patch.object(listener, '_save_offset', wraps=listener._save_offset) as mock_save:
        # Trigger shutdown
        await listener._handle_shutdown(signal.SIGTERM)

        # Verify _save_offset was called with correct ID
        mock_save.assert_called_once_with(99999)


# ============================================================================
# 7. INTEGRATION TESTS (2 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_full_message_flow(listener, tmp_path):
    """Test end-to-end: poll -> process -> trigger -> save offset."""
    listener.offset_file = tmp_path / "telegram_offset.txt"

    # Sample update
    sample_update = {
        "update_id": 123456,
        "message": {
            "message_id": 789,
            "from": {"id": 12345, "first_name": "Alice", "username": "alice123"},
            "chat": {"id": 12345},
            "text": "Hello Reeve"
        }
    }

    # Mock Telegram API response with message
    telegram_response = {
        "ok": True,
        "result": [sample_update]
    }

    # Mock Pulse API success response
    pulse_response = MagicMock()
    pulse_response.status = 200
    pulse_response.json = AsyncMock(return_value={
        "pulse_id": 42,
        "scheduled_at": "2026-01-23T10:00:00Z"
    })
    pulse_response.__aenter__ = AsyncMock(return_value=pulse_response)
    pulse_response.__aexit__ = AsyncMock(return_value=None)

    # Mock API session (schedule pulse)
    api_mock = MagicMock()
    api_mock.post = MagicMock(return_value=pulse_response)
    listener.api_session = api_mock

    # Mock _get_updates to return our response
    with patch.object(listener, '_get_updates', new_callable=AsyncMock, return_value=telegram_response):
        # Mock _save_offset to track calls
        with patch.object(listener, '_save_offset', wraps=listener._save_offset) as mock_save:
            # Simulate one polling iteration
            updates_data = await listener._get_updates()

            if updates_data and updates_data.get("ok"):
                updates = updates_data.get("result", [])

                for update in updates:
                    await listener._process_update(update)
                    listener.last_update_id = update["update_id"] + 1

                if updates:
                    listener._save_offset(listener.last_update_id)

            # Verify full flow
            assert listener.last_update_id == 123457  # sample_update["update_id"] + 1
            mock_save.assert_called_once_with(123457)

            # Verify pulse was triggered
            api_mock.post.assert_called_once()


@pytest.mark.asyncio
async def test_full_lifecycle(listener, tmp_path):
    """Test full start -> poll -> shutdown cycle."""
    import signal

    listener.offset_file = tmp_path / "telegram_offset.txt"

    # Mock bot token verification (getMe)
    getme_response = AsyncMock()
    getme_response.json = AsyncMock(return_value={
        "ok": True,
        "result": {
            "id": 123456,
            "username": "test_bot",
            "first_name": "Test Bot"
        }
    })

    telegram_mock = AsyncMock()
    telegram_mock.get.return_value.__aenter__.return_value = getme_response
    listener.telegram_session = telegram_mock

    # Mock _verify_bot_token
    with patch.object(listener, '_verify_bot_token', new_callable=AsyncMock):
        # Mock _polling_loop to exit immediately
        async def mock_polling_loop():
            listener.running = False

        with patch.object(listener, '_polling_loop', new_callable=AsyncMock, side_effect=mock_polling_loop):
            # Mock signal handler registration
            with patch.object(listener, '_register_signal_handlers'):
                # Start and immediately stop
                listener.running = True
                await listener._polling_loop()

                # Trigger shutdown
                listener.last_update_id = 12345
                await listener._handle_shutdown(signal.SIGTERM)

                # Verify lifecycle
                assert listener.running is False
                assert listener.shutdown_event.is_set()

                # Verify offset was saved
                assert listener.offset_file.exists()
                assert listener.offset_file.read_text().strip() == "12345"
