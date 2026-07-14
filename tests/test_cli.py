"""Tests for the interactive credential CLI module."""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from the_harness.cli import (
    cmd_setup,
    cmd_status,
    cmd_store,
    cmd_delete,
    cmd_unlock,
    main,
)


@pytest.fixture
def tmp_creds_path(tmp_path, monkeypatch):
    """Redirect credential file to a temp path."""
    creds_file = str(tmp_path / "credentials.enc")
    monkeypatch.setattr("the_harness.cli._DEFAULT_PATH", creds_file)
    return creds_file


class TestCmdSetup:
    """Test first-run guided credential setup."""

    def test_setup_creates_store(self, tmp_creds_path):
        """cmd_setup should create an encrypted credential store."""
        # getpass: set password, confirm password, enter API key
        # input: base_url, model
        with patch("getpass.getpass", side_effect=["password123", "password123", "sk-test-key"]), \
             patch("builtins.input", side_effect=["", ""]):
            result = cmd_setup()
        assert result == 0
        assert Path(tmp_creds_path).exists()

    def test_setup_password_mismatch(self, tmp_creds_path):
        """cmd_setup should fail if passwords don't match."""
        with patch("getpass.getpass", side_effect=["password123", "different1"]):
            result = cmd_setup()
        assert result == 1
        assert not Path(tmp_creds_path).exists()

    def test_setup_short_password(self, tmp_creds_path):
        """cmd_setup should reject passwords shorter than 8 characters."""
        with patch("getpass.getpass", side_effect=["short", "short"]):
            result = cmd_setup()
        assert result == 1

    def test_setup_skip_api_key(self, tmp_creds_path):
        """cmd_setup should allow skipping API key entry."""
        with patch("getpass.getpass", side_effect=["password123", "password123", ""]):
            result = cmd_setup()
        assert result == 0
        assert Path(tmp_creds_path).exists()

    def test_setup_already_exists(self, tmp_creds_path):
        """cmd_setup should fail if credential store already exists."""
        # First setup
        with patch("getpass.getpass", side_effect=["password123", "password123", ""]):
            cmd_setup()
        # Second setup should fail
        with patch("getpass.getpass", side_effect=["password123", "password123", ""]):
            result = cmd_setup()
        assert result == 1

    def test_setup_with_base_url_and_model(self, tmp_creds_path):
        """cmd_setup should store base_url and model when provided."""
        with patch("getpass.getpass", side_effect=["password123", "password123", "sk-key"]), \
             patch("builtins.input", side_effect=["https://api.deepseek.com/v1", "deepseek-chat"]):
            result = cmd_setup()
        assert result == 0


class TestCmdStatus:
    """Test status command (shows providers without revealing keys)."""

    def test_status_no_store(self, tmp_creds_path):
        """cmd_status should fail if no credential store exists."""
        result = cmd_status()
        assert result == 1

    def test_status_wrong_password(self, tmp_creds_path):
        """cmd_status should fail with wrong master password."""
        with patch("getpass.getpass", side_effect=["password123", "password123", ""]):
            cmd_setup()
        with patch("getpass.getpass", side_effect=["wrongpass1"]):
            result = cmd_status()
        assert result == 1

    def test_status_shows_provider(self, tmp_creds_path):
        """cmd_status should show configured provider without revealing key."""
        with patch("getpass.getpass", side_effect=["password123", "password123", "sk-test"]), \
             patch("builtins.input", side_effect=["", ""]):
            cmd_setup()
        with patch("getpass.getpass", side_effect=["password123"]):
            result = cmd_status()
        assert result == 0


class TestCmdStore:
    """Test store command (add/update API key)."""

    def test_store_key(self, tmp_creds_path):
        """cmd_store should store a new API key."""
        with patch("getpass.getpass", side_effect=["password123", "password123", ""]):
            cmd_setup()
        # getpass: unlock password, API key; input: provider, base_url, model
        with patch("getpass.getpass", side_effect=["password123", "sk-new-key"]), \
             patch("builtins.input", side_effect=["openai", "", ""]):
            result = cmd_store()
        assert result == 0

    def test_store_key_with_base_url_and_model(self, tmp_creds_path):
        """cmd_store should store base_url and model."""
        with patch("getpass.getpass", side_effect=["password123", "password123", ""]):
            cmd_setup()
        with patch("getpass.getpass", side_effect=["password123", "sk-ds-key"]), \
             patch("builtins.input", side_effect=["deepseek", "https://api.deepseek.com/v1", "deepseek-chat"]):
            result = cmd_store()
        assert result == 0

    def test_store_no_store(self, tmp_creds_path):
        """cmd_store should fail if no credential store exists."""
        result = cmd_store()
        assert result == 1


class TestCmdDelete:
    """Test delete command."""

    def test_delete_key(self, tmp_creds_path):
        """cmd_delete should remove a provider's key."""
        with patch("getpass.getpass", side_effect=["password123", "password123", "sk-test"]), \
             patch("builtins.input", side_effect=["", ""]):
            cmd_setup()
        with patch("getpass.getpass", side_effect=["password123"]), \
             patch("builtins.input", side_effect=["openai"]):
            result = cmd_delete()
        assert result == 0


class TestCmdUnlock:
    """Test unlock command."""

    def test_unlock_no_store(self, tmp_creds_path):
        """cmd_unlock should fail if no credential store exists."""
        result = cmd_unlock()
        assert result == 1

    def test_unlock_success(self, tmp_creds_path):
        """cmd_unlock should succeed with correct password."""
        with patch("getpass.getpass", side_effect=["password123", "password123", ""]):
            cmd_setup()
        with patch("getpass.getpass", side_effect=["password123"]):
            result = cmd_unlock()
        assert result == 0

    def test_unlock_wrong_password(self, tmp_creds_path):
        """cmd_unlock should fail with wrong password."""
        with patch("getpass.getpass", side_effect=["password123", "password123", ""]):
            cmd_setup()
        with patch("getpass.getpass", side_effect=["wrongpass1"]):
            result = cmd_unlock()
        assert result == 1


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
