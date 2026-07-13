"""Tests for CredentialManager with AES-256 encryption."""

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
    """store() then get() should return the original key."""
    cred_manager.setup("master123")
    cred_manager.unlock("master123")

    cred_manager.store("openai", "sk-abc123def456")
    retrieved = cred_manager.get("openai")
    assert retrieved == "sk-abc123def456"


def test_status_no_plaintext(cred_manager):
    """status() should not reveal stored keys in plaintext."""
    cred_manager.setup("master123")
    cred_manager.unlock("master123")
    cred_manager.store("openai", "sk-super-secret-key")

    status = cred_manager.status()
    status_str = str(status)
    assert "sk-super-secret-key" not in status_str
    # Should show that openai provider exists
    assert "openai" in status_str or status.get("openai") is not None


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

    assert cred_manager.get("openai") == "sk-new-key"
