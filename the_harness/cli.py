"""Interactive CLI for credential management.

No master password — API keys are stored in the OS keychain via keyring
(Windows Credential Manager / macOS Keychain / Linux Secret Service).
Commands work directly without setup/unlock.

Usage:
    python -m the_harness.cli status    # Show configured providers (no plaintext)
    python -m the_harness.cli store     # Add/update a provider key
    python -m the_harness.cli delete    # Remove a provider key
"""

import getpass
import sys

from the_harness.credentials.manager import CredentialManager

_SERVICE_NAME = "the-harness"


def _get_manager() -> CredentialManager:
    """Return a CredentialManager bound to the default service name."""
    return CredentialManager(_SERVICE_NAME)


def cmd_status() -> int:
    """Show which providers have keys stored (without revealing keys)."""
    mgr = _get_manager()
    status = mgr.status()
    if not status:
        print("No API keys stored. Use 'store' to add one.")
    else:
        print("Configured providers:")
        for provider, info in status.items():
            url_str = f" | URL: {info['base_url']}" if info.get("base_url") else ""
            model_str = f" | Model: {info['model']}" if info.get("model") else ""
            print(f"  {provider}: configured{url_str}{model_str}")
    return 0


def cmd_store() -> int:
    """Add or update an API key for a provider."""
    mgr = _get_manager()

    provider = input("Provider name (e.g. openai): ").strip().lower()
    if not provider:
        print("Error: provider name cannot be empty.")
        return 1

    key = getpass.getpass(f"API key for {provider}: ")
    if not key.strip():
        print("Error: API key cannot be empty.")
        return 1

    base_url = input("Base URL (leave empty for default): ").strip()
    model = input("Model name (leave empty for default): ").strip()

    mgr.store(provider, key.strip(), base_url, model)
    print(f"API key for '{provider}' stored.")
    if base_url:
        print(f"  Base URL: {base_url}")
    if model:
        print(f"  Model: {model}")
    return 0


def cmd_delete() -> int:
    """Delete a provider's API key."""
    mgr = _get_manager()

    status = mgr.status()
    if not status:
        print("No API keys stored.")
        return 0

    print("Configured providers:", ", ".join(status.keys()))
    provider = input("Provider to delete: ").strip().lower()
    if not provider:
        print("Error: provider name cannot be empty.")
        return 1

    mgr.delete(provider)
    print(f"Deleted API key for '{provider}'.")
    return 0


_COMMANDS = {
    "status": cmd_status,
    "store": cmd_store,
    "delete": cmd_delete,
}


def main() -> int:
    """CLI entry point. Dispatches to subcommands."""
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("Usage: python -m the_harness.cli <command>")
        print()
        print("Commands:")
        for cmd in _COMMANDS:
            print(f"  {cmd}")
        return 0

    cmd = sys.argv[1].lower()
    if cmd not in _COMMANDS:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(_COMMANDS)}")
        return 1

    return _COMMANDS[cmd]()


if __name__ == "__main__":
    sys.exit(main())
