"""Memory store — SQLite session history, project context, and failure patterns.

Provides cross-session memory for the agent: project metadata, past session
results, and successful failure-resolution strategies.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from the_harness.models import Task


class MemoryStore:
    """Stores and retrieves project context, session history, and failure patterns.

    Attributes:
        workspace: The workspace directory path.
    """

    def __init__(self, workspace: str) -> None:
        self._workspace = Path(workspace)
        self._data_dir = self._workspace / ".harness"
        self._db_path = self._data_dir / "sessions.db"
        self._context_path = self._data_dir / "project_context.json"
        self._patterns_path = self._data_dir / "failure_patterns.json"
        self._init_db()

    def _init_db(self) -> None:
        """Create the SQLite database and tables if they don't exist."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_path TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    rounds INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    reason TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    round INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    action_params TEXT,
                    result TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def scan_project(self) -> dict[str, Any]:
        """Scan workspace for project metadata and save to project_context.json.

        Returns:
            Dict with keys like test_framework, language, has_tests_dir.
        """
        ctx: dict[str, Any] = {}

        # Detect test framework
        pyproject = self._workspace / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            if "[tool.pytest]" in content or "pytest" in content:
                ctx["test_framework"] = "pytest"
            ctx["language"] = "python"
        elif (self._workspace / "conftest.py").exists():
            ctx["test_framework"] = "pytest"
            ctx["language"] = "python"
        elif (self._workspace / "requirements.txt").exists():
            ctx["language"] = "python"

        # Detect tests directory
        if (self._workspace / "tests").is_dir():
            ctx["has_tests_dir"] = True

        # Save to file
        self._context_path.write_text(json.dumps(ctx, indent=2))
        return ctx

    def save_session(self, session_data: dict[str, Any]) -> int:
        """Save a session and its actions to the SQLite database.

        Args:
            session_data: Dict with keys test_path, success, rounds, reason,
                           and optionally actions (list of dicts).

        Returns:
            The session ID.
        """
        created_at = datetime.now().isoformat()
        conn = sqlite3.connect(str(self._db_path))
        try:
            cur = conn.execute(
                "INSERT INTO sessions (test_path, success, rounds, created_at, reason) VALUES (?, ?, ?, ?, ?)",
                (
                    session_data["test_path"],
                    1 if session_data["success"] else 0,
                    session_data["rounds"],
                    created_at,
                    session_data.get("reason", ""),
                ),
            )
            session_id = cur.lastrowid
            for action in session_data.get("actions", []):
                conn.execute(
                    "INSERT INTO actions (session_id, round, action_type, action_params, result) VALUES (?, ?, ?, ?, ?)",
                    (
                        session_id,
                        action.get("round", 0),
                        action.get("action_type", ""),
                        json.dumps(action.get("action_params", {})),
                        action.get("result", ""),
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        return session_id  # type: ignore[return-value]

    def get_sessions(self) -> list[dict[str, Any]]:
        """Retrieve all past sessions from the database.

        Returns:
            List of session dicts with keys id, test_path, success, rounds, created_at, reason.
        """
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        finally:
            conn.close()
        return [
            {
                "id": row["id"],
                "test_path": row["test_path"],
                "success": bool(row["success"]),
                "rounds": row["rounds"],
                "created_at": row["created_at"],
                "reason": row["reason"],
            }
            for row in rows
        ]

    def save_failure_pattern(self, failure_type: str, strategy: str) -> None:
        """Save or update a failure pattern strategy.

        Args:
            failure_type: The type of failure (e.g. "assertion_failure").
            strategy: The successful strategy for resolving this failure type.
        """
        patterns = self._load_patterns()
        patterns[failure_type] = strategy
        self._patterns_path.write_text(json.dumps(patterns, indent=2))

    def get_failure_pattern(self, failure_type: str) -> str | None:
        """Look up a successful strategy for a failure type.

        Args:
            failure_type: The type of failure to look up.

        Returns:
            The strategy string, or None if not found.
        """
        patterns = self._load_patterns()
        return patterns.get(failure_type)

    def build_context(self, task: Task) -> str:
        """Assemble relevant context fragments for the LLM.

        Includes project info and relevant failure patterns.

        Args:
            task: The current task.

        Returns:
            A context string for the LLM.
        """
        parts: list[str] = []

        # Project context
        if self._context_path.exists():
            ctx = json.loads(self._context_path.read_text())
            if ctx:
                parts.append(f"Project: {ctx.get('language', 'unknown')}, "
                             f"tests: {ctx.get('test_framework', 'unknown')}")

        # Failure patterns
        patterns = self._load_patterns()
        if patterns:
            hints = [f"  - {k}: {v}" for k, v in patterns.items()]
            parts.append("Known failure patterns:\n" + "\n".join(hints))

        # Task info
        parts.append(f"Task: make {task.test_path} pass")

        return "\n\n".join(parts) if parts else f"Task: make {task.test_path} pass"

    def _load_patterns(self) -> dict[str, str]:
        """Load failure patterns from JSON file."""
        if self._patterns_path.exists():
            try:
                return json.loads(self._patterns_path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}
