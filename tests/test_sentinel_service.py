"""Tests for SentinelService (cooldown logic), send_alert() API, and CLI."""

import sys
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from reeve.sentinel import send_alert
from reeve.sentinel.backends.base import AlertBackend
from reeve.sentinel.service import SentinelService


class TestSentinelService:
    """Tests for the sentinel service with cooldown logic."""

    def test_alert_sends_via_backend(self, tmp_path):
        """Test alert() delegates to backend.send()."""
        mock_backend = MagicMock(spec=AlertBackend)
        mock_backend.send.return_value = True

        service = SentinelService(mock_backend, state_dir=tmp_path)
        result = service.alert("Test message")

        assert result is True
        mock_backend.send.assert_called_once_with("Test message")

    def test_alert_returns_false_on_send_failure(self, tmp_path):
        """Test alert() returns False when backend.send() fails."""
        mock_backend = MagicMock(spec=AlertBackend)
        mock_backend.send.return_value = False

        service = SentinelService(mock_backend, state_dir=tmp_path)
        result = service.alert("Test message")

        assert result is False

    def test_cooldown_prevents_duplicate_alerts(self, tmp_path):
        """Test that alerts with the same cooldown key are suppressed."""
        mock_backend = MagicMock(spec=AlertBackend)
        mock_backend.send.return_value = True

        service = SentinelService(mock_backend, state_dir=tmp_path)

        result1 = service.alert("First", cooldown_key="test_key", cooldown_seconds=3600)
        assert result1 is True

        result2 = service.alert("Second", cooldown_key="test_key", cooldown_seconds=3600)
        assert result2 is False

        assert mock_backend.send.call_count == 1

    def test_cooldown_allows_different_keys(self, tmp_path):
        """Test that different cooldown keys are independent."""
        mock_backend = MagicMock(spec=AlertBackend)
        mock_backend.send.return_value = True

        service = SentinelService(mock_backend, state_dir=tmp_path)

        result1 = service.alert("First", cooldown_key="key_a", cooldown_seconds=3600)
        result2 = service.alert("Second", cooldown_key="key_b", cooldown_seconds=3600)

        assert result1 is True
        assert result2 is True
        assert mock_backend.send.call_count == 2

    def test_cooldown_expires(self, tmp_path):
        """Test that cooldown expires and allows re-alerting."""
        mock_backend = MagicMock(spec=AlertBackend)
        mock_backend.send.return_value = True

        service = SentinelService(mock_backend, state_dir=tmp_path)

        service.alert("First", cooldown_key="test_key", cooldown_seconds=1)
        time.sleep(1.1)

        result = service.alert("Second", cooldown_key="test_key", cooldown_seconds=1)
        assert result is True
        assert mock_backend.send.call_count == 2

    def test_no_cooldown_always_sends(self, tmp_path):
        """Test that alerts without cooldown_key always send."""
        mock_backend = MagicMock(spec=AlertBackend)
        mock_backend.send.return_value = True

        service = SentinelService(mock_backend, state_dir=tmp_path)

        for i in range(3):
            result = service.alert(f"Message {i}")
            assert result is True

        assert mock_backend.send.call_count == 3

    def test_cooldown_with_unreadable_file(self, tmp_path):
        """Test alert sends when cooldown file triggers an OSError."""
        mock_backend = MagicMock(spec=AlertBackend)
        mock_backend.send.return_value = True

        service = SentinelService(mock_backend, state_dir=tmp_path)

        cooldown_path = tmp_path / ".cooldown_test_key"
        cooldown_path.symlink_to("/nonexistent/path/that/does/not/exist")

        result = service.alert("Test", cooldown_key="test_key", cooldown_seconds=3600)
        assert result is True

    def test_creates_state_dir_if_missing(self, tmp_path):
        """Test that state directory is created automatically."""
        state_dir = tmp_path / "nested" / "sentinel"
        mock_backend = MagicMock(spec=AlertBackend)
        mock_backend.send.return_value = True

        service = SentinelService(mock_backend, state_dir=state_dir)
        service.alert("Test", cooldown_key="test")

        assert state_dir.exists()

    def test_cooldown_key_sanitized(self, tmp_path):
        """Test that cooldown keys with special chars are sanitized."""
        mock_backend = MagicMock(spec=AlertBackend)
        mock_backend.send.return_value = True

        service = SentinelService(mock_backend, state_dir=tmp_path)
        service.alert("Test", cooldown_key="pulse/failed#42!")

        files = list(tmp_path.glob(".cooldown_*"))
        assert len(files) == 1
        assert "/" not in files[0].name
        assert "#" not in files[0].name


class TestSendAlert:
    """Tests for the top-level send_alert() function."""

    def test_send_alert_never_raises(self, monkeypatch):
        """Test send_alert() returns False instead of raising."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        monkeypatch.delenv("SENTINEL_BACKEND", raising=False)

        result = send_alert("Test message")
        assert result is False

    def test_send_alert_with_backend(self, monkeypatch):
        """Test send_alert() sends via detected backend."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        with patch("reeve.sentinel.backends.telegram.urllib.request.urlopen") as mock:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = Mock(return_value=mock_resp)
            mock_resp.__exit__ = Mock(return_value=False)
            mock.return_value = mock_resp

            result = send_alert("Test message")
            assert result is True

    def test_send_alert_survives_backend_exception(self, monkeypatch):
        """Test send_alert() catches exceptions from broken backends."""
        with patch("reeve.sentinel.get_backend", side_effect=RuntimeError("Broken")):
            result = send_alert("Test")
            assert result is False


class TestCLI:
    """Tests for the __main__.py CLI."""

    def test_cli_sends_alert(self):
        """Test CLI sends alert with provided message."""
        with patch("reeve.sentinel.__main__.send_alert", return_value=True) as mock:
            from reeve.sentinel.__main__ import main

            with patch.object(sys, "argv", ["sentinel", "Test message"]):
                exit_code = main()

            assert exit_code == 0
            mock.assert_called_once_with(
                "Test message",
                cooldown_key=None,
                cooldown_seconds=1800,
            )

    def test_cli_with_cooldown_args(self):
        """Test CLI passes cooldown arguments."""
        with patch("reeve.sentinel.__main__.send_alert", return_value=True) as mock:
            from reeve.sentinel.__main__ import main

            with patch.object(
                sys,
                "argv",
                ["sentinel", "--cooldown-key", "my_key", "--cooldown", "3600", "Message"],
            ):
                exit_code = main()

            assert exit_code == 0
            mock.assert_called_once_with(
                "Message",
                cooldown_key="my_key",
                cooldown_seconds=3600,
            )

    def test_cli_returns_1_on_failure(self):
        """Test CLI returns exit code 1 when alert fails."""
        with patch("reeve.sentinel.__main__.send_alert", return_value=False):
            from reeve.sentinel.__main__ import main

            with patch.object(sys, "argv", ["sentinel", "Test"]):
                exit_code = main()

            assert exit_code == 1
