"""Tests for CredentialManager — OS keychain storage via keyring.

No master password, no plaintext files. Credentials are stored in the
operating system's native credential store (Windows Credential Manager,
macOS Keychain, Linux Secret Service).
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from the_harness.credentials.manager import CredentialManager


@pytest.fixture
def mock_keyring():
    """Mock the keyring module with an in-memory store."""
    store = {}
    mock = MagicMock()
    mock.set_password.side_effect = lambda service, username, password: store.__setitem__(f"{service}:{username}", password)
    mock.get_password.side_effect = lambda service, username: store.get(f"{service}:{username}")
    mock.delete_password.side_effect = lambda service, username: store.pop(f"{service}:{username}", None)
    return mock, store


@pytest.fixture
def cred_manager(mock_keyring, monkeypatch):
    """Create a CredentialManager with mocked keyring.

    The patch stays active for the whole test (yield-style) so that
    subsequent calls on the manager hit the mock store, not the real
    OS keychain.  Env vars are also cleared to isolate status() checks.
    """
    mock, store = mock_keyring
    # Clear env vars that the manager falls back to, so tests are deterministic
    for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
        monkeypatch.delenv(var, raising=False)
    with patch("the_harness.credentials.manager.keyring", mock):
        mgr = CredentialManager("the-harness")
        yield mgr, store


# ── 核心行为：OS 钥匙串存储 ────────────────────────────────


def test_store_uses_keyring(cred_manager):
    """store() should save to OS keyring, not to a file."""
    mgr, store = cred_manager
    mgr.store("openai", "sk-abc123def456")
    # The key should be in the keyring store, not in a file
    assert any("openai" in k for k in store.keys())
    value = store.get("the-harness:provider:openai")
    assert value is not None
    data = json.loads(value)
    assert data["api_key"] == "sk-abc123def456"


def test_get_retrieves_from_keyring(cred_manager):
    """get() should retrieve from OS keyring."""
    mgr, store = cred_manager
    mgr.store("openai", "sk-test-key", "https://api.test.com/v1", "gpt-4o")
    result = mgr.get("openai")
    assert result is not None
    assert result["api_key"] == "sk-test-key"
    assert result["base_url"] == "https://api.test.com/v1"
    assert result["model"] == "gpt-4o"


def test_get_nonexistent_returns_none(cred_manager):
    """get() for a nonexistent provider should return None."""
    mgr, store = cred_manager
    assert mgr.get("nonexistent") is None


def test_status_lists_providers(cred_manager):
    """status() should list all stored providers without revealing keys."""
    mgr, store = cred_manager
    mgr.store("openai", "sk-secret-key")
    mgr.store("deepseek", "sk-ds-key", "https://api.deepseek.com/v1", "deepseek-chat")
    status = mgr.status()
    assert "openai" in status
    assert "deepseek" in status
    assert status["openai"]["api_key"] is True
    assert status["deepseek"]["base_url"] == "https://api.deepseek.com/v1"
    assert status["deepseek"]["model"] == "deepseek-chat"


def test_status_no_plaintext(cred_manager):
    """status() should not reveal stored keys in plaintext."""
    mgr, store = cred_manager
    mgr.store("openai", "sk-super-secret-key")
    status = mgr.status()
    assert "sk-super-secret-key" not in str(status)


def test_delete_provider(cred_manager):
    """delete() should remove a provider from keyring."""
    mgr, store = cred_manager
    mgr.store("openai", "sk-key-to-delete")
    mgr.delete("openai")
    assert mgr.get("openai") is None


def test_update_key(cred_manager):
    """Updating an existing provider's key should overwrite the old one."""
    mgr, store = cred_manager
    mgr.store("openai", "sk-old-key")
    mgr.store("openai", "sk-new-key")
    assert mgr.get("openai")["api_key"] == "sk-new-key"


def test_store_with_base_url_and_model(cred_manager):
    """store() with base_url and model should persist all fields."""
    mgr, store = cred_manager
    mgr.store("deepseek", "sk-ds-key", "https://api.deepseek.com/v1", "deepseek-chat")
    retrieved = mgr.get("deepseek")
    assert retrieved["api_key"] == "sk-ds-key"
    assert retrieved["base_url"] == "https://api.deepseek.com/v1"
    assert retrieved["model"] == "deepseek-chat"


def test_get_api_key_convenience(cred_manager):
    """get_api_key() should return just the API key string."""
    mgr, store = cred_manager
    mgr.store("openai", "sk-test-key", "https://custom.api/v1", "gpt-4o")
    assert mgr.get_api_key("openai") == "sk-test-key"
    assert mgr.get_api_key("nonexistent") is None


def test_empty_status(cred_manager):
    """status() should return empty dict when no keys are stored."""
    mgr, store = cred_manager
    assert mgr.status() == {}


def test_no_file_created(cred_manager, tmp_path):
    """CredentialManager should not create any files on disk."""
    mgr, store = cred_manager
    mgr.store("openai", "sk-test-key")
    # No credential files should exist in the temp directory
    cred_files = list(tmp_path.glob("credentials*"))
    assert len(cred_files) == 0
