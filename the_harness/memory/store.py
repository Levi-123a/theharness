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
                    reason TEXT,
                    summary TEXT,
                    description TEXT,
                    final_reply TEXT
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
                    reasoning TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            # Add reasoning column to existing databases (added in a later
            # version than the original schema).  ALTER ... ADD COLUMN errors
            # if the column already exists, so we introspect first.
            cols = {row[1] for row in conn.execute("PRAGMA table_info(actions)").fetchall()}
            if "reasoning" not in cols:
                conn.execute("ALTER TABLE actions ADD COLUMN reasoning TEXT")
            # Add summary column to existing sessions tables (added in a
            # later version). Same introspect-first pattern.
            session_cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
            if "summary" not in session_cols:
                conn.execute("ALTER TABLE sessions ADD COLUMN summary TEXT")
            if "description" not in session_cols:
                conn.execute("ALTER TABLE sessions ADD COLUMN description TEXT")
            if "final_reply" not in session_cols:
                conn.execute("ALTER TABLE sessions ADD COLUMN final_reply TEXT")
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
                "INSERT INTO sessions (test_path, success, rounds, created_at, reason, summary, description, final_reply) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_data["test_path"],
                    1 if session_data["success"] else 0,
                    session_data["rounds"],
                    created_at,
                    session_data.get("reason", ""),
                    session_data.get("summary", ""),
                    session_data.get("description", ""),
                    session_data.get("final_reply", ""),
                ),
            )
            session_id = cur.lastrowid
            for action in session_data.get("actions", []):
                conn.execute(
                    "INSERT INTO actions (session_id, round, action_type, action_params, result, reasoning) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        session_id,
                        action.get("round", 0),
                        action.get("action_type", ""),
                        json.dumps(action.get("action_params", {})),
                        action.get("result", ""),
                        action.get("reasoning", ""),
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
                "summary": row["summary"] or "",
                "description": row["description"] or "",
                "final_reply": row["final_reply"] or "",
            }
            for row in rows
        ]

    def get_session(self, session_id: int) -> dict[str, Any] | None:
        """Retrieve a single session with its full actions list by ID.

        Unlike ``get_sessions`` (which returns summary rows for the sidebar
        list), this returns the complete session including the ``actions``
        list, which the WebUI renders as conversation bubbles when a past
        session is opened.

        Args:
            session_id: The session ID to look up.

        Returns:
            The session dict with an ``actions`` key, or None if not found.
        """
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.row_factory = sqlite3.Row
            session_row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not session_row:
                return None
            session = dict(session_row)
            session["success"] = bool(session["success"])
            session["summary"] = session.get("summary") or ""
            session["description"] = session.get("description") or ""
            session["final_reply"] = session.get("final_reply") or ""
            action_rows = conn.execute(
                "SELECT * FROM actions WHERE session_id = ? ORDER BY round",
                (session_id,),
            ).fetchall()
            session["actions"] = [
                {
                    "round": a["round"],
                    "action_type": a["action_type"],
                    "action_params": json.loads(a["action_params"] or "{}"),
                    "result": a["result"],
                    "reasoning": a["reasoning"],
                }
                for a in action_rows
            ]
            return session
        finally:
            conn.close()

    def delete_session(self, session_id: int) -> bool:
        """Delete a single session and its actions by ID.

        Args:
            session_id: The session ID to delete.

        Returns:
            True if a row was deleted, False if the session didn't exist.
        """
        conn = sqlite3.connect(str(self._db_path))
        try:
            # FK ON DELETE is not enforced by default in sqlite without
            # PRAGMA foreign_keys=ON, so explicitly delete actions first.
            conn.execute("DELETE FROM actions WHERE session_id = ?", (session_id,))
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete_sessions(self, session_ids: list[int]) -> int:
        """Delete multiple sessions and their actions in one transaction.

        Args:
            session_ids: List of session IDs to delete.

        Returns:
            The number of sessions actually deleted (unknown ids are skipped).
        """
        if not session_ids:
            return 0
        conn = sqlite3.connect(str(self._db_path))
        try:
            placeholders = ",".join("?" for _ in session_ids)
            conn.execute(
                f"DELETE FROM actions WHERE session_id IN ({placeholders})",
                session_ids,
            )
            cur = conn.execute(
                f"DELETE FROM sessions WHERE id IN ({placeholders})",
                session_ids,
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

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
