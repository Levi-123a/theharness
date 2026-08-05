"""Credential manager — stores API keys in the OS keychain via keyring.

No master password, no plaintext files. Credentials are stored in the
operating system's native credential store (Windows Credential Manager,
macOS Keychain, Linux Secret Service).

环境变量作为辅助来源：当 keyring 中没有某 provider 的记录时，
可从 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL 等环境变量读取，
方便用户通过 .env 文件预配置（注意 .env 为明文，仅作开发便利）。
"""

import json
import os

import keyring

# 环境变量名约定：<PROVIDER>_API_KEY / <PROVIDER>_BASE_URL / <PROVIDER>_MODEL
# 目前仅 openai provider 支持环境变量回退（兼容 DeepSeek 等 OpenAI 兼容端点）
_ENV_VAR_MAP = {
    "openai": {
        "api_key": "OPENAI_API_KEY",
        "base_url": "OPENAI_BASE_URL",
        "model": "OPENAI_MODEL",
    },
}

# keyring 中存储 provider index 用的特殊 username
_INDEX_USERNAME = "__providers__"


class CredentialManager:
    """Manages API keys in the OS keychain via the keyring library.

    The keyring backend is selected automatically by the keyring library
    based on the host operating system. No file IO is performed.
    """

    def __init__(self, service_name: str) -> None:
        """Initialize the credential manager.

        Args:
            service_name: The keyring service name (namespace) under which
                credentials are stored.  Different service names produce
                isolated credential namespaces.
        """
        self._service_name = service_name

    # ── Public API ──────────────────────────────────────────────────

    def store(self, provider: str, api_key: str, base_url: str = "", model: str = "") -> None:
        """Store or update credentials for a provider in the OS keychain.

        Args:
            provider: The provider name (e.g. "openai", "deepseek").
            api_key: The API key to store.
            base_url: Optional base URL for the provider API endpoint.
            model: Optional model name to use with this provider.
        """
        data = {"api_key": api_key, "base_url": base_url, "model": model}
        keyring.set_password(
            self._service_name,
            f"provider:{provider}",
            json.dumps(data, ensure_ascii=False),
        )
        self._add_to_index(provider)

    def get(self, provider: str) -> dict[str, str] | None:
        """Retrieve credentials for a provider.

        查找顺序：OS keyring → 环境变量（仅 openai provider）。

        Args:
            provider: The provider name.

        Returns:
            A dict with "api_key", "base_url", "model" keys, or None if
            the provider is not configured in either keyring or env vars.
        """
        # 1. Try OS keyring
        raw = keyring.get_password(self._service_name, f"provider:{provider}")
        if raw:
            return json.loads(raw)

        # 2. Fallback to environment variables for supported providers
        env_map = _ENV_VAR_MAP.get(provider)
        if env_map:
            api_key = os.environ.get(env_map["api_key"], "").strip()
            if api_key:
                return {
                    "api_key": api_key,
                    "base_url": os.environ.get(env_map["base_url"], "").strip(),
                    "model": os.environ.get(env_map["model"], "").strip(),
                }

        return None

    def get_api_key(self, provider: str) -> str | None:
        """Retrieve only the API key for a provider.

        Args:
            provider: The provider name.

        Returns:
            The API key string, or None if not found.
        """
        entry = self.get(provider)
        return entry.get("api_key") if entry else None

    def status(self) -> dict[str, dict[str, str | bool]]:
        """Return provider info without revealing API keys.

        Returns:
            A dict mapping provider names to their status info
            (api_key: True, base_url: str, model: str).
        """
        result: dict[str, dict[str, str | bool]] = {}
        for provider in self._get_index():
            raw = keyring.get_password(self._service_name, f"provider:{provider}")
            if not raw:
                continue
            entry = json.loads(raw)
            result[provider] = {
                "api_key": True,
                "base_url": entry.get("base_url", ""),
                "model": entry.get("model", ""),
            }

        # Include providers available via environment variables
        for provider, env_map in _ENV_VAR_MAP.items():
            if provider in result:
                continue
            api_key = os.environ.get(env_map["api_key"], "").strip()
            if api_key:
                result[provider] = {
                    "api_key": True,
                    "base_url": os.environ.get(env_map["base_url"], "").strip(),
                    "model": os.environ.get(env_map["model"], "").strip(),
                }

        return result

    def delete(self, provider: str) -> None:
        """Delete a provider's key from the OS keychain.

        Args:
            provider: The provider name.
        """
        try:
            keyring.delete_password(self._service_name, f"provider:{provider}")
        except keyring.errors.PasswordDeleteError:
            pass
        self._remove_from_index(provider)

    # ── Private helpers: provider index ─────────────────────────────

    def _get_index(self) -> list[str]:
        """Read the provider index from the keyring."""
        raw = keyring.get_password(self._service_name, _INDEX_USERNAME)
        if not raw:
            return []
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []

    def _add_to_index(self, provider: str) -> None:
        """Add a provider to the index (idempotent)."""
        providers = self._get_index()
        if provider not in providers:
            providers.append(provider)
            keyring.set_password(
                self._service_name,
                _INDEX_USERNAME,
                json.dumps(providers, ensure_ascii=False),
            )

    def _remove_from_index(self, provider: str) -> None:
        """Remove a provider from the index."""
        providers = self._get_index()
        if provider in providers:
            providers.remove(provider)
            keyring.set_password(
                self._service_name,
                _INDEX_USERNAME,
                json.dumps(providers, ensure_ascii=False),
            )
