"""Interactive CLI for first-run credential setup and management.

Provides guided, secure API key entry via hidden input (getpass).
Supports: first-run setup, unlock, status, update, delete, lock.

Usage:
    python -m the_harness.cli setup     # First-run guided setup
    python -m the_harness.cli status    # Show configured providers (no plaintext)
    python -m the_harness.cli store     # Add/update a provider key
    python -m the_harness.cli delete    # Remove a provider key
    python -m the_harness.cli unlock    # Unlock credential store
"""

import getpass
import os
import sys
from pathlib import Path

from the_harness.credentials.manager import CredentialManager

_DEFAULT_PATH = os.path.expanduser("~/.the-harness/credentials.enc")


def _get_manager() -> CredentialManager:
    """Return a CredentialManager pointing at the default path."""
    Path(_DEFAULT_PATH).parent.mkdir(parents=True, exist_ok=True)
    return CredentialManager(_DEFAULT_PATH)


def cmd_setup() -> int:
    """First-run guided credential setup.

    Prompts for master password (hidden), creates encrypted store,
    then optionally stores an API key (hidden input).
    """
    mgr = _get_manager()

    if Path(_DEFAULT_PATH).exists():
        print("Credential store already exists. Use 'unlock' then 'store' to update.")
        return 1

    print("=" * 50)
    print("  the-harness — First-Run Credential Setup")
    print("=" * 50)
    print()
    print("You will set a master password to encrypt your API keys.")
    print("The master password is NEVER stored to disk.")
    print("If you forget it, your encrypted keys cannot be recovered.")
    print()

    pw = getpass.getpass("Set master password: ")
    pw_confirm = getpass.getpass("Confirm master password: ")

    if pw != pw_confirm:
        print("Error: passwords do not match.")
        return 1
    if len(pw) < 8:
        print("Error: master password must be at least 8 characters.")
        return 1

    mgr.setup(pw)
    print()
    print("Encrypted credential store created at:")
    print(f"  {_DEFAULT_PATH}")
    print()

    # Optionally store an API key now
    key = getpass.getpass("Enter OpenAI API key (leave blank to skip): ")
    if key.strip():
        mgr.store("openai", key.strip())
        print("API key stored securely (encrypted with AES-256-GCM).")
    else:
        print("Skipped. You can add a key later with 'store'.")

    print()
    print("Setup complete. You can now run the-harness.")
    mgr.lock()
    return 0


def cmd_unlock() -> int:
    """Unlock the credential store with the master password."""
    mgr = _get_manager()

    if not Path(_DEFAULT_PATH).exists():
        print("No credential store found. Run 'setup' first.")
        return 1

    pw = getpass.getpass("Master password: ")
    if mgr.unlock(pw):
        print("Credential store unlocked.")
        # Keep it unlocked in this session by not locking
        return 0
    else:
        print("Error: incorrect master password.")
        return 1


def cmd_status() -> int:
    """Show which providers have keys stored (without revealing keys)."""
    mgr = _get_manager()

    if not Path(_DEFAULT_PATH).exists():
        print("No credential store found. Run 'setup' first.")
        return 1

    pw = getpass.getpass("Master password: ")
    if not mgr.unlock(pw):
        print("Error: incorrect master password.")
        return 1

    status = mgr.status()
    if not status:
        print("No API keys stored.")
    else:
        print("Configured providers:")
        for provider, configured in status.items():
            print(f"  {provider}: {'configured' if configured else 'not set'}")
    mgr.lock()
    return 0


def cmd_store() -> int:
    """Add or update an API key for a provider."""
    mgr = _get_manager()

    if not Path(_DEFAULT_PATH).exists():
        print("No credential store found. Run 'setup' first.")
        return 1

    pw = getpass.getpass("Master password: ")
    if not mgr.unlock(pw):
        print("Error: incorrect master password.")
        return 1

    provider = input("Provider name (e.g. openai): ").strip().lower()
    if not provider:
        print("Error: provider name cannot be empty.")
        mgr.lock()
        return 1

    key = getpass.getpass(f"API key for {provider}: ")
    if not key.strip():
        print("Error: API key cannot be empty.")
        mgr.lock()
        return 1

    mgr.store(provider, key.strip())
    print(f"API key for '{provider}' stored securely.")
    mgr.lock()
    return 0


def cmd_delete() -> int:
    """Delete a provider's API key."""
    mgr = _get_manager()

    if not Path(_DEFAULT_PATH).exists():
        print("No credential store found. Run 'setup' first.")
        return 1

    pw = getpass.getpass("Master password: ")
    if not mgr.unlock(pw):
        print("Error: incorrect master password.")
        return 1

    status = mgr.status()
    if not status:
        print("No API keys stored.")
        mgr.lock()
        return 0

    print("Configured providers:", ", ".join(status.keys()))
    provider = input("Provider to delete: ").strip().lower()
    if not provider:
        print("Error: provider name cannot be empty.")
        mgr.lock()
        return 1

    mgr.delete(provider)
    print(f"Deleted API key for '{provider}'.")
    mgr.lock()
    return 0


_COMMANDS = {
    "setup": cmd_setup,
    "unlock": cmd_unlock,
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
