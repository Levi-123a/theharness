"""Tests for MemoryStore — SQLite session history and failure patterns."""

import json
from pathlib import Path

from the_harness.memory.store import MemoryStore
from the_harness.models import Task


def test_scan_project(tmp_path):
    """scan_project() should detect test framework and save to project_context.json."""
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
    (tmp_path / "tests").mkdir()
    store = MemoryStore(str(tmp_path))
    ctx = store.scan_project()
    assert "test_framework" in ctx
    assert ctx["test_framework"] == "pytest"
    assert (tmp_path / ".harness" / "project_context.json").exists()


def test_save_and_get_session(tmp_path):
    """save_session() should persist to SQLite and get_sessions() should retrieve it."""
    store = MemoryStore(str(tmp_path))
    store.save_session({
        "test_path": "tests/test_foo.py",
        "success": True,
        "rounds": 2,
        "reason": "success",
        "actions": [
            {"round": 1, "action_type": "edit_file", "action_params": {}, "result": "ok"},
        ],
    })
    sessions = store.get_sessions()
    assert len(sessions) == 1
    assert sessions[0]["test_path"] == "tests/test_foo.py"
    assert sessions[0]["success"] is True
    assert sessions[0]["rounds"] == 2


def test_save_and_get_failure_pattern(tmp_path):
    """save_failure_pattern() and get_failure_pattern() should roundtrip."""
    store = MemoryStore(str(tmp_path))
    store.save_failure_pattern("assertion_failure", "Check boundary conditions")
    result = store.get_failure_pattern("assertion_failure")
    assert result == "Check boundary conditions"
    assert store.get_failure_pattern("nonexistent") is None


def test_build_context_includes_project_info(tmp_path):
    """build_context() should include project info from scan."""
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
    store = MemoryStore(str(tmp_path))
    store.scan_project()
    task = Task(test_path="tests/test_foo.py", workspace=str(tmp_path))
    ctx = store.build_context(task)
    assert "pytest" in ctx.lower()


def test_build_context_includes_failure_pattern(tmp_path):
    """build_context() should include relevant failure patterns."""
    store = MemoryStore(str(tmp_path))
    store.save_failure_pattern("compile_error", "Check for missing colons")
    task = Task(test_path="tests/test_foo.py", workspace=str(tmp_path))
    ctx = store.build_context(task)
    assert "compile_error" in ctx.lower() or "missing colons" in ctx.lower()


def test_empty_store_returns_minimal_context(tmp_path):
    """Empty store should still return a minimal context string."""
    store = MemoryStore(str(tmp_path))
    task = Task(test_path="tests/test_foo.py", workspace=str(tmp_path))
    ctx = store.build_context(task)
    assert isinstance(ctx, str)
    assert len(ctx) > 0
