"""Guardrail: dangerous action interception with regex patterns and workspace path checking."""

import re
from pathlib import Path

from the_harness.models import Action, ActionType, GuardrailResult


# 14 dangerous command regex patterns
_DANGEROUS_PATTERNS = [
    (re.compile(r"\brm\s+-rf\b", re.IGNORECASE), "rm -rf: recursive force delete"),
    (re.compile(r"\bdel\s+/s\b", re.IGNORECASE), "del /s: Windows recursive delete"),
    (re.compile(r"\bgit\s+push\s+--force\b", re.IGNORECASE), "git push --force: force push"),
    (re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE), "git reset --hard: hard reset"),
    (re.compile(r"\bgit\s+push\s+origin\b", re.IGNORECASE), "git push origin: push to remote"),
    (re.compile(r"curl\s.*\|\s*(sh|bash)", re.IGNORECASE), "curl|sh: remote script execution"),
    (re.compile(r"wget\s.*\|\s*(sh|bash)", re.IGNORECASE), "wget|sh: remote script execution"),
    (re.compile(r"\bscp\b", re.IGNORECASE), "scp: remote copy"),
    (re.compile(r"\brsync\b", re.IGNORECASE), "rsync: remote sync"),
    (re.compile(r"\bsudo\b", re.IGNORECASE), "sudo: privileged execution"),
    (re.compile(r"\bchmod\s+777\b", re.IGNORECASE), "chmod 777: world-writable permissions"),
    (re.compile(r"\bgit\s+clean\s+-fd\b", re.IGNORECASE), "git clean -fd: force clean"),
    (re.compile(r"\brm\s+-r\b", re.IGNORECASE), "rm -r: recursive delete"),
    (re.compile(r"\brmdir\s+/s\b", re.IGNORECASE), "rmdir /s: Windows recursive rmdir"),
]

# System paths that should never be accessed
_SYSTEM_PATHS = [
    "/etc/",
    "C:\\Windows\\",
    "/sys/",
    "/proc/",
]


class Guardrail:
    """Intercepts dangerous actions before execution.

    Checks actions against:
    1. 14 dangerous command regex patterns (rm -rf, git push --force, etc.)
    2. System path access (/etc/, C:\\Windows\\, /sys/, /proc/)
    3. Workspace boundary (all file operations must stay within workspace)

    Attributes:
        _workspace: The resolved workspace directory path.
    """

    def __init__(self, workspace: str) -> None:
        """Initialize the guardrail with a workspace path.

        Args:
            workspace: Path to the workspace directory.
        """
        self._workspace = Path(workspace).resolve()

    def check(self, action: Action) -> GuardrailResult:
        """Check if an action is safe to execute.

        Args:
            action: The action to check.

        Returns:
            GuardrailResult with blocked=True if the action is dangerous.
        """
        # Check shell commands for dangerous patterns
        if action.type in (ActionType.RUN_SHELL, ActionType.RUN_TESTS):
            command = action.params.get("command", "")
            if command:
                blocked, reason = self._check_command(command)
                if blocked:
                    return GuardrailResult(blocked=True, reason=reason)

        # Check file operations for path safety
        if action.type in (ActionType.READ_FILE, ActionType.WRITE_FILE, ActionType.EDIT_FILE):
            file_path = action.params.get("file_path", "")
            if file_path:
                blocked, reason = self._check_path(file_path)
                if blocked:
                    return GuardrailResult(blocked=True, reason=reason)

        # Give_up is always safe
        return GuardrailResult(blocked=False, reason="")

    def _check_command(self, command: str) -> tuple[bool, str]:
        """Check a shell command against dangerous patterns.

        Args:
            command: The shell command string.

        Returns:
            A tuple of (blocked, reason).
        """
        for pattern, description in _DANGEROUS_PATTERNS:
            if pattern.search(command):
                return True, f"Blocked: {description}"
        return False, ""

    def _check_path(self, file_path: str) -> tuple[bool, str]:
        """Check a file path for system access and workspace boundary.

        Args:
            file_path: The file path to check.

        Returns:
            A tuple of (blocked, reason).
        """
        # Check for system path access
        normalized = file_path.replace("\\", "/")
        for sys_path in _SYSTEM_PATHS:
            check_path = sys_path.replace("\\", "/")
            if check_path in normalized:
                return True, f"Blocked: access to system path {sys_path}"

        # Check workspace boundary
        try:
            resolved = Path(file_path)
            if not resolved.is_absolute():
                resolved = self._workspace / resolved
            resolved = resolved.resolve()
            # Check if the resolved path is within the workspace
            resolved.relative_to(self._workspace)
        except ValueError:
            return True, f"Blocked: path '{file_path}' is outside workspace boundary"
        except Exception:
            # If path resolution fails for any reason, block it
            return True, f"Blocked: cannot resolve path '{file_path}'"

        return False, ""
