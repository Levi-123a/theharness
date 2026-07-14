"""Tests for CredentialManager with AES-256 encryption."""

import json
from pathlib import Path

import pytest

from the_harness.credentials.manager import CredentialManager


@pytest.fixture
def cred_manager(tmp_path):
    """Create a CredentialManager with a temp file path."""
    cred_file = tmp_path / "credentials.enc"
    return CredentialManager(str(cred_file))


def test_setup_creates_file(cred_manager):
    """setup() should create the encrypted credentials file."""
    cred_manager.setup("my-master-password")
    assert Path(cred_manager._file_path).exists()
    # File should not be empty
    assert Path(cred_manager._file_path).stat().st_size > 0


def test_store_and_get_roundtrip(cred_manager):
    """store() then get() should return the original credentials dict."""
    cred_manager.setup("master123")
    cred_manager.unlock("master123")

    cred_manager.store("openai", "sk-abc123def456")
    retrieved = cred_manager.get("openai")
    assert retrieved is not None
    assert retrieved["api_key"] == "sk-abc123def456"
    assert retrieved["base_url"] == ""
    assert retrieved["model"] == ""


def test_status_no_plaintext(cred_manager):
    """status() should not reveal stored keys in plaintext."""
    cred_manager.setup("master123")
    cred_manager.unlock("master123")
    cred_manager.store("openai", "sk-super-secret-key")

    status = cred_manager.status()
    status_str = str(status)
    assert "sk-super-secret-key" not in status_str
    # Should show that openai provider exists with api_key=True
    assert "openai" in status_str or status.get("openai") is not None
    assert status["openai"]["api_key"] is True


def test_delete_provider(cred_manager):
    """delete() should remove a provider's key."""
    cred_manager.setup("master123")
    cred_manager.unlock("master123")
    cred_manager.store("openai", "sk-key-to-delete")

    cred_manager.delete("openai")
    assert cred_manager.get("openai") is None


def test_wrong_password_fails(cred_manager):
    """unlock() with wrong password should fail."""
    cred_manager.setup("correct-password")
    # Wrong password should not unlock
    result = cred_manager.unlock("wrong-password")
    assert result is False
    # Should not be able to store/get
    with pytest.raises(Exception):
        cred_manager.store("openai", "sk-key")


def test_update_key(cred_manager):
    """Updating an existing provider's key should overwrite the old one."""
    cred_manager.setup("master123")
    cred_manager.unlock("master123")
    cred_manager.store("openai", "sk-old-key")
    cred_manager.store("openai", "sk-new-key")

    assert cred_manager.get("openai")["api_key"] == "sk-new-key"


def test_store_with_base_url_and_model(cred_manager):
    """store() with base_url and model should persist all fields."""
    cred_manager.setup("master123")
    cred_manager.unlock("master123")

    cred_manager.store("deepseek", "sk-ds-key", "https://api.deepseek.com/v1", "deepseek-chat")
    retrieved = cred_manager.get("deepseek")
    assert retrieved is not None
    assert retrieved["api_key"] == "sk-ds-key"
    assert retrieved["base_url"] == "https://api.deepseek.com/v1"
    assert retrieved["model"] == "deepseek-chat"


def test_get_api_key_convenience(cred_manager):
    """get_api_key() should return just the API key string."""
    cred_manager.setup("master123")
    cred_manager.unlock("master123")

    cred_manager.store("openai", "sk-test-key", "https://custom.api/v1", "gpt-4o")
    assert cred_manager.get_api_key("openai") == "sk-test-key"
    assert cred_manager.get_api_key("nonexistent") is None


def test_status_shows_base_url_and_model(cred_manager):
    """status() should include base_url and model info."""
    cred_manager.setup("master123")
    cred_manager.unlock("master123")

    cred_manager.store("openai", "sk-key", "https://custom.api/v1", "gpt-4o")
    status = cred_manager.status()
    assert status["openai"]["base_url"] == "https://custom.api/v1"
    assert status["openai"]["model"] == "gpt-4o"
    # api_key should be True, not the actual key
    assert status["openai"]["api_key"] is True


def test_backward_compat_migration(tmp_path):
    """Old format (str values) should auto-migrate to new dict format on unlock."""
    # Create a credential file with old str format using the encryption directly
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    import os

    cred_file = tmp_path / "old_credentials.enc"
    salt = os.urandom(16)
    nonce = os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100_000)
    key = kdf.derive(b"test-password")

    # Old format: provider -> str
    old_data = {"openai": "sk-old-format-key"}
    plaintext = json.dumps(old_data).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    with open(cred_file, "wb") as f:
        f.write(salt + nonce + ciphertext)

    # Now unlock with CredentialManager - should auto-migrate
    mgr = CredentialManager(str(cred_file))
    assert mgr.unlock("test-password") is True

    # get() should return dict format
    result = mgr.get("openai")
    assert result is not None
    assert result["api_key"] == "sk-old-format-key"
    assert result["base_url"] == ""
    assert result["model"] == ""

    # get_api_key() should also work
    assert mgr.get_api_key("openai") == "sk-old-format-key"
