"""Tool dispatcher: file operations and shell execution with workspace isolation."""

import subprocess
from pathlib import Path

from the_harness.models import Action, ActionType, ActionResult


class ToolDispatcher:
    """Executes file and shell actions within a workspace boundary.

    All file paths are resolved relative to the workspace directory.
    Shell commands run with cwd set to the workspace.

    Attributes:
        _workspace: The resolved workspace directory path.
    """

    def __init__(self, workspace: str) -> None:
        """Initialize the tool dispatcher with a workspace path.

        Args:
            workspace: Path to the workspace directory.
        """
        self._workspace = Path(workspace).resolve()

    def execute(self, action: Action) -> ActionResult:
        """Execute an action and return the result.

        Args:
            action: The action to execute.

        Returns:
            ActionResult with success status, output, and optional error.
        """
        dispatch = {
            ActionType.READ_FILE: self._read_file,
            ActionType.WRITE_FILE: self._write_file,
            ActionType.EDIT_FILE: self._edit_file,
            ActionType.RUN_SHELL: self._run_shell,
            ActionType.RUN_TESTS: self._run_shell,
            ActionType.GIVE_UP: self._give_up,
        }
        handler = dispatch.get(action.type)
        if handler is None:
            return ActionResult(success=False, error=f"Unknown action type: {action.type}")
        return handler(action)

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve a file path relative to the workspace."""
        p = Path(file_path)
        if not p.is_absolute():
            p = self._workspace / p
        return p.resolve()

    def _read_file(self, action: Action) -> ActionResult:
        """Read file content."""
        file_path = action.params.get("file_path", "")
        resolved = self._resolve_path(file_path)
        if not resolved.exists():
            return ActionResult(success=False, error=f"File not found: {file_path}")
        try:
            content = resolved.read_text(encoding="utf-8")
            return ActionResult(success=True, output=content)
        except Exception as e:
            return ActionResult(success=False, error=str(e))

    def _write_file(self, action: Action) -> ActionResult:
        """Create or overwrite a file, creating parent dirs."""
        file_path = action.params.get("file_path", "")
        content = action.params.get("content", "")
        resolved = self._resolve_path(file_path)
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            return ActionResult(success=True, output=f"Wrote {file_path}")
        except Exception as e:
            return ActionResult(success=False, error=str(e))

    def _edit_file(self, action: Action) -> ActionResult:
        """Exact string replacement in a file."""
        file_path = action.params.get("file_path", "")
        old_text = action.params.get("old_text", "")
        new_text = action.params.get("new_text", "")
        resolved = self._resolve_path(file_path)
        if not resolved.exists():
            return ActionResult(success=False, error=f"File not found: {file_path}")
        try:
            content = resolved.read_text(encoding="utf-8")
            if old_text not in content:
                return ActionResult(success=False, error=f"Text not found: {old_text[:50]}")
            new_content = content.replace(old_text, new_text, 1)
            resolved.write_text(new_content, encoding="utf-8")
            return ActionResult(success=True, output=f"Edited {file_path}")
        except Exception as e:
            return ActionResult(success=False, error=str(e))

    def _run_shell(self, action: Action) -> ActionResult:
        """Execute a shell command in the workspace."""
        command = action.params.get("command", "")
        if not command:
            return ActionResult(success=False, error="No command provided")
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = proc.stdout + proc.stderr
            if proc.returncode == 0:
                return ActionResult(success=True, output=output)
            return ActionResult(
                success=False,
                output=output,
                error=f"Exit code: {proc.returncode}",
            )
        except subprocess.TimeoutExpired:
            return ActionResult(success=False, error="Command timed out (30s)")
        except Exception as e:
            return ActionResult(success=False, error=str(e))

    def _give_up(self, action: Action) -> ActionResult:
        """Return a give-up result."""
        return ActionResult(success=True, output="Agent gave up")
