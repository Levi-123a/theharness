"""Tests for the credential CLI module — keyring-based, no master password."""

import sys
from unittest.mock import patch, MagicMock

import pytest

from the_harness.cli import (
    cmd_status,
    cmd_store,
    cmd_delete,
    main,
)


@pytest.fixture
def mock_keyring(monkeypatch):
    """Mock the keyring module with an in-memory store.

    Also clears env vars so status() is deterministic.
    """
    store = {}
    mock = MagicMock()
    mock.set_password.side_effect = lambda service, username, password: store.__setitem__(f"{service}:{username}", password)
    mock.get_password.side_effect = lambda service, username: store.get(f"{service}:{username}")
    mock.delete_password.side_effect = lambda service, username: store.pop(f"{service}:{username}", None)
    # Clear env vars that the manager falls back to
    for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("the_harness.credentials.manager.keyring", mock)
    return mock, store


class TestCmdStatus:
    """Test status command (shows providers without revealing keys)."""

    def test_status_no_keys(self, mock_keyring):
        """cmd_status should return 0 when no keys are stored."""
        result = cmd_status()
        assert result == 0

    def test_status_shows_provider(self, mock_keyring):
        """cmd_status should return 0 after a provider is stored."""
        with patch("getpass.getpass", side_effect=["sk-test"]), \
             patch("builtins.input", side_effect=["openai", "", ""]):
            cmd_store()
        result = cmd_status()
        assert result == 0


class TestCmdStore:
    """Test store command (add/update API key via keyring)."""

    def test_store_key(self, mock_keyring):
        """cmd_store should store a new API key in the keyring."""
        mock, store = mock_keyring
        with patch("getpass.getpass", side_effect=["sk-new-key"]), \
             patch("builtins.input", side_effect=["openai", "", ""]):
            result = cmd_store()
        assert result == 0
        # Key should be stored in keyring, not in a file
        assert any("openai" in k for k in store.keys())

    def test_store_key_with_base_url_and_model(self, mock_keyring):
        """cmd_store should store base_url and model."""
        mock, store = mock_keyring
        with patch("getpass.getpass", side_effect=["sk-ds-key"]), \
             patch("builtins.input", side_effect=["deepseek", "https://api.deepseek.com/v1", "deepseek-chat"]):
            result = cmd_store()
        assert result == 0
        import json
        value = store.get("the-harness:provider:deepseek")
        assert value is not None
        data = json.loads(value)
        assert data["base_url"] == "https://api.deepseek.com/v1"
        assert data["model"] == "deepseek-chat"

    def test_store_empty_provider(self, mock_keyring):
        """cmd_store should fail if provider name is empty."""
        with patch("builtins.input", side_effect=[""]):
            result = cmd_store()
        assert result == 1

    def test_store_empty_key(self, mock_keyring):
        """cmd_store should fail if API key is empty."""
        with patch("getpass.getpass", side_effect=[""]), \
             patch("builtins.input", side_effect=["openai"]):
            result = cmd_store()
        assert result == 1


class TestCmdDelete:
    """Test delete command."""

    def test_delete_key(self, mock_keyring):
        """cmd_delete should remove a provider's key from keyring."""
        mock, store = mock_keyring
        # Store a key first
        with patch("getpass.getpass", side_effect=["sk-test"]), \
             patch("builtins.input", side_effect=["openai", "", ""]):
            cmd_store()
        assert any("openai" in k for k in store.keys())
        with patch("builtins.input", side_effect=["openai"]):
            result = cmd_delete()
        assert result == 0
        assert not any("provider:openai" in k for k in store.keys())

    def test_delete_no_keys(self, mock_keyring):
        """cmd_delete should return 0 when no keys are stored."""
        result = cmd_delete()
        assert result == 0


class TestMain:
    """Test the main CLI dispatcher."""

    def test_main_no_args_shows_help(self):
        """main() with no args should show help and return 0."""
        with patch.object(sys, "argv", ["cli"]):
            result = main()
        assert result == 0

    def test_main_help_flag(self):
        """main() with --help should show help and return 0."""
        with patch.object(sys, "argv", ["cli", "--help"]):
            result = main()
        assert result == 0

    def test_main_unknown_command(self):
        """main() with unknown command should return 1."""
        with patch.object(sys, "argv", ["cli", "unknown"]):
            result = main()
        assert result == 1
