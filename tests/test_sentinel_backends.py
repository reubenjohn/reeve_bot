"""Tests for sentinel alert backends (Telegram, registry, auto-detection)."""

import json
import urllib.error
from unittest.mock import MagicMock, Mock, patch

import pytest

from reeve.sentinel.backends import get_backend
from reeve.sentinel.backends.telegram import TelegramBackend


class TestTelegramBackend:
    """Tests for the Telegram alert backend."""

    def test_send_posts_correct_payload(self):
        """Test that send() POSTs correct JSON to Telegram API."""
        backend = TelegramBackend(bot_token="test-token", chat_id="12345")

        with patch("reeve.sentinel.backends.telegram.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_response

            result = backend.send("Test alert message")

            assert result is True
            mock_urlopen.assert_called_once()

            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            assert "https://api.telegram.org/bottest-token/sendMessage" == request.full_url
            payload = json.loads(request.data)
            assert payload["chat_id"] == "12345"
            assert payload["text"] == "Test alert message"

    def test_send_truncates_long_messages(self):
        """Test messages are truncated to 4096 chars (Telegram limit)."""
        backend = TelegramBackend(bot_token="t", chat_id="1")
        long_message = "x" * 5000

        with patch("reeve.sentinel.backends.telegram.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_response

            backend.send(long_message)

            request = mock_urlopen.call_args[0][0]
            payload = json.loads(request.data)
            assert len(payload["text"]) == 4096

    def test_send_never_raises_on_network_error(self):
        """Test send() returns False instead of raising on network errors."""
        backend = TelegramBackend(bot_token="t", chat_id="1")

        with patch(
            "reeve.sentinel.backends.telegram.urllib.request.urlopen",
            side_effect=ConnectionError("Network down"),
        ):
            result = backend.send("Test")
            assert result is False

    def test_send_never_raises_on_http_error(self):
        """Test send() returns False on HTTP errors (401, 500, etc.)."""
        backend = TelegramBackend(bot_token="bad-token", chat_id="1")

        with patch(
            "reeve.sentinel.backends.telegram.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="https://api.telegram.org",
                code=401,
                msg="Unauthorized",
                hdrs=None,  # type: ignore[arg-type]
                fp=None,  # type: ignore[arg-type]
            ),
        ):
            result = backend.send("Test")
            assert result is False

    def test_from_env_returns_backend_when_configured(self, monkeypatch):
        """Test from_env() creates backend when env vars are set."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "my-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "99999")

        backend = TelegramBackend.from_env()
        assert backend is not None
        assert backend.bot_token == "my-token"
        assert backend.chat_id == "99999"

    def test_from_env_returns_none_when_missing(self, monkeypatch):
        """Test from_env() returns None when env vars are missing."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

        backend = TelegramBackend.from_env()
        assert backend is None

    def test_from_env_returns_none_when_partial(self, monkeypatch):
        """Test from_env() returns None when only one env var is set."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "my-token")
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

        backend = TelegramBackend.from_env()
        assert backend is None


class TestBackendRegistry:
    """Tests for backend auto-detection."""

    def test_get_backend_auto_detects_telegram(self, monkeypatch):
        """Test auto-detection finds Telegram when env vars are set."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        monkeypatch.delenv("SENTINEL_BACKEND", raising=False)

        backend = get_backend()
        assert backend is not None
        assert isinstance(backend, TelegramBackend)

    def test_get_backend_returns_none_when_unconfigured(self, monkeypatch):
        """Test returns None when no backend env vars are set."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        monkeypatch.delenv("SENTINEL_BACKEND", raising=False)

        backend = get_backend()
        assert backend is None

    def test_get_backend_explicit_name(self, monkeypatch):
        """Test explicit backend selection by name."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        backend = get_backend("telegram")
        assert isinstance(backend, TelegramBackend)

    def test_get_backend_unknown_name(self, monkeypatch):
        """Test unknown backend name returns None."""
        backend = get_backend("nonexistent")
        assert backend is None

    def test_get_backend_env_override(self, monkeypatch):
        """Test SENTINEL_BACKEND env var overrides auto-detection."""
        monkeypatch.setenv("SENTINEL_BACKEND", "telegram")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        backend = get_backend()
        assert isinstance(backend, TelegramBackend)
