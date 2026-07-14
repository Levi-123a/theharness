"""AES-256 encrypted credential manager with PBKDF2 key derivation."""

import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# Constants
_SALT_SIZE = 16  # bytes
_NONCE_SIZE = 12  # bytes
_KDF_ITERATIONS = 100_000
_KEY_SIZE = 32  # 256 bits for AES-256


class CredentialManager:
    """Manages encrypted API keys with a master password.

    Uses AES-256-GCM for encryption and PBKDF2 for key derivation.
    The credentials file format is: salt(16) + nonce(12) + ciphertext.

    Attributes:
        _file_path: Path to the encrypted credentials file.
        _unlocked: Whether the manager is currently unlocked.
        _key: The derived encryption key (only set when unlocked).
        _data: Decrypted credential store (only set when unlocked).
            Format: {"provider_name": {"api_key": "...", "base_url": "...", "model": "..."}}
    """

    def __init__(self, file_path: str) -> None:
        """Initialize the credential manager with a file path.

        Args:
            file_path: Path to the encrypted credentials file.
        """
        self._file_path = file_path
        self._unlocked = False
        self._key: bytes | None = None
        self._data: dict[str, dict[str, str]] = {}

    def setup(self, master_password: str) -> None:
        """Create a new encrypted credential store.

        Args:
            master_password: The master password for encryption.
        """
        salt = os.urandom(_SALT_SIZE)
        key = self._derive_key(master_password, salt)
        # Start with empty credentials
        self._data = {}
        self._write_file(salt, key, self._data)
        self._key = key
        self._unlocked = True
        self._set_file_permissions()

    def unlock(self, master_password: str) -> bool:
        """Unlock the credential store with the master password.

        Args:
            master_password: The master password.

        Returns:
            True if unlock succeeded, False if the password was wrong.
        """
        if not Path(self._file_path).exists():
            return False

        # Clear any previous state before attempting unlock
        self._key = None
        self._data = {}
        self._unlocked = False

        with open(self._file_path, "rb") as f:
            raw = f.read()

        salt = raw[:_SALT_SIZE]
        nonce = raw[_SALT_SIZE:_SALT_SIZE + _NONCE_SIZE]
        ciphertext = raw[_SALT_SIZE + _NONCE_SIZE:]

        key = self._derive_key(master_password, salt)
        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        except Exception:
            return False

        data = json.loads(plaintext.decode("utf-8"))
        # Backward compatibility: migrate old str format to new dict format
        for provider, value in data.items():
            if isinstance(value, str):
                data[provider] = {"api_key": value, "base_url": "", "model": ""}
        self._data = data
        self._key = key
        self._unlocked = True
        return True

    def lock(self) -> None:
        """Lock the credential store, clearing the key and data from memory."""
        self._key = None
        self._data = {}
        self._unlocked = False

    def store(self, provider: str, api_key: str, base_url: str = "", model: str = "") -> None:
        """Store or update credentials for a provider.

        Args:
            provider: The provider name (e.g. "openai", "deepseek").
            api_key: The API key to store.
            base_url: Optional base URL for the provider API endpoint.
            model: Optional model name to use with this provider.

        Raises:
            RuntimeError: If the manager is not unlocked.
        """
        if not self._unlocked:
            raise RuntimeError("Credential manager is locked. Call unlock() first.")
        self._data[provider] = {"api_key": api_key, "base_url": base_url, "model": model}
        self._persist()

    def get(self, provider: str) -> dict[str, str] | None:
        """Retrieve credentials for a provider.

        Args:
            provider: The provider name.

        Returns:
            A dict with "api_key", "base_url", "model" keys, or None if not found.

        Raises:
            RuntimeError: If the manager is not unlocked.
        """
        if not self._unlocked:
            raise RuntimeError("Credential manager is locked. Call unlock() first.")
        return self._data.get(provider)

    def get_api_key(self, provider: str) -> str | None:
        """Retrieve only the API key for a provider.

        Args:
            provider: The provider name.

        Returns:
            The API key string, or None if not found.

        Raises:
            RuntimeError: If the manager is not unlocked.
        """
        if not self._unlocked:
            raise RuntimeError("Credential manager is locked. Call unlock() first.")
        entry = self._data.get(provider)
        return entry.get("api_key") if entry else None

    def status(self) -> dict[str, dict[str, str | bool]]:
        """Return provider info without revealing API keys.

        Returns:
            A dict mapping provider names to their status info
            (api_key: True, base_url: str, model: str).

        Raises:
            RuntimeError: If the manager is not unlocked.
        """
        if not self._unlocked:
            raise RuntimeError("Credential manager is locked. Call unlock() first.")
        return {
            provider: {
                "api_key": True,
                "base_url": entry.get("base_url", ""),
                "model": entry.get("model", ""),
            }
            for provider, entry in self._data.items()
        }

    def delete(self, provider: str) -> None:
        """Delete a provider's key.

        Args:
            provider: The provider name.

        Raises:
            RuntimeError: If the manager is not unlocked.
        """
        if not self._unlocked:
            raise RuntimeError("Credential manager is locked. Call unlock() first.")
        self._data.pop(provider, None)
        self._persist()

    # ── Private helpers ────────────────────────────────────────────

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive a 256-bit key from password and salt using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=_KEY_SIZE,
            salt=salt,
            iterations=_KDF_ITERATIONS,
        )
        return kdf.derive(password.encode("utf-8"))

    def _write_file(self, salt: bytes, key: bytes, data: dict[str, dict[str, str]]) -> None:
        """Write encrypted credentials to file: salt + nonce + ciphertext."""
        nonce = os.urandom(_NONCE_SIZE)
        plaintext = json.dumps(data).encode("utf-8")
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
        with open(self._file_path, "wb") as f:
            f.write(salt + nonce + ciphertext)

    def _persist(self) -> None:
        """Re-encrypt and write the current data to file."""
        if self._key is None:
            raise RuntimeError("Cannot persist: no encryption key available.")
        # Read existing salt from file
        with open(self._file_path, "rb") as f:
            raw = f.read()
        salt = raw[:_SALT_SIZE]
        self._write_file(salt, self._key, self._data)

    def _set_file_permissions(self) -> None:
        """Set file permissions to 600 (owner read/write only)."""
        try:
            os.chmod(self._file_path, 0o600)
        except OSError:
            # On Windows, chmod may not fully work; ignore
            pass
