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


def test_save_and_get_session_summary(tmp_path):
    """save_session() should store summary and get_sessions() should return it.

    The summary is an AI-generated one-line description of what the session
    did, displayed in the sidebar session list so users can tell sessions
    apart at a glance (instead of just '#5 tests/test_foo.py').
    """
    store = MemoryStore(str(tmp_path))
    session_id = store.save_session({
        "test_path": "tests/test_foo.py",
        "success": True,
        "rounds": 2,
        "reason": "All tests passed",
        "summary": "修复了 foo 模块中的变量赋值错误",
        "actions": [],
    })
    # get_sessions (list view) must include summary
    sessions = store.get_sessions()
    assert len(sessions) == 1
    assert sessions[0]["summary"] == "修复了 foo 模块中的变量赋值错误"
    # get_session (detail view) must also include summary
    detail = store.get_session(session_id)
    assert detail is not None
    assert detail["summary"] == "修复了 foo 模块中的变量赋值错误"


def test_save_session_without_summary_defaults_to_empty(tmp_path):
    """save_session() without a summary field should store empty string, not crash."""
    store = MemoryStore(str(tmp_path))
    store.save_session({
        "test_path": "tests/test_foo.py",
        "success": True,
        "rounds": 1,
        "reason": "done",
        "actions": [],
    })
    sessions = store.get_sessions()
    assert sessions[0]["summary"] == ""


def test_get_session_returns_actions(tmp_path):
    """get_session(id) should return the full session including its actions list.

    Bug: WebUI's session detail endpoint used get_sessions() (list) which
    doesn't include actions, so clicking a past session in the sidebar
    showed only the summary (success/rounds/reason) but no conversation
    bubbles.
    """
    store = MemoryStore(str(tmp_path))
    session_id = store.save_session({
        "test_path": "tests/test_foo.py",
        "success": True,
        "rounds": 2,
        "reason": "All tests passed",
        "actions": [
            {"round": 1, "action_type": "read_file",
             "action_params": {"file_path": "src/foo.py"},
             "result": "file contents..."},
            {"round": 2, "action_type": "edit_file",
             "action_params": {"file_path": "src/foo.py", "old_text": "x", "new_text": "y"},
             "result": "edited"},
        ],
    })
    session = store.get_session(session_id)
    assert session is not None
    assert session["id"] == session_id
    assert session["test_path"] == "tests/test_foo.py"
    assert session["success"] is True
    assert session["rounds"] == 2
    assert session["reason"] == "All tests passed"
    # actions list must be present with all stored fields
    assert "actions" in session
    assert len(session["actions"]) == 2
    a1 = session["actions"][0]
    assert a1["round"] == 1
    assert a1["action_type"] == "read_file"
    assert a1["action_params"] == {"file_path": "src/foo.py"}
    assert a1["result"] == "file contents..."
    a2 = session["actions"][1]
    assert a2["round"] == 2
    assert a2["action_type"] == "edit_file"


def test_get_session_returns_none_for_missing(tmp_path):
    """get_session(id) should return None for a non-existent session id."""
    store = MemoryStore(str(tmp_path))
    assert store.get_session(99999) is None


def test_delete_session_removes_session_and_actions(tmp_path):
    """delete_session(id) should remove the session and its actions.

    Must cascade-delete the associated actions rows so no orphaned
    action records remain. Returns True when a row was deleted.
    """
    store = MemoryStore(str(tmp_path))
    sid = store.save_session({
        "test_path": "tests/test_foo.py",
        "success": True,
        "rounds": 1,
        "reason": "ok",
        "actions": [
            {"round": 1, "action_type": "edit_file",
             "action_params": {}, "result": "done"},
        ],
    })
    # precondition: session + action exist
    assert store.get_session(sid) is not None

    deleted = store.delete_session(sid)
    assert deleted is True

    # session is gone
    assert store.get_session(sid) is None
    # not in list view either
    sessions = store.get_sessions()
    assert all(s["id"] != sid for s in sessions)


def test_delete_session_returns_false_for_missing(tmp_path):
    """delete_session(id) should return False when the session doesn't exist."""
    store = MemoryStore(str(tmp_path))
    assert store.delete_session(99999) is False


def test_delete_sessions_batch_removes_multiple(tmp_path):
    """delete_sessions([ids]) should remove all listed sessions at once.

    Batch delete is used by the UI's "批量删除" button. Returns the count
    of actually deleted rows. Unknown ids are silently skipped.
    """
    store = MemoryStore(str(tmp_path))
    sid1 = store.save_session({"test_path": "a", "success": True, "rounds": 1})
    sid2 = store.save_session({"test_path": "b", "success": False, "rounds": 2})
    sid3 = store.save_session({"test_path": "c", "success": True, "rounds": 1})

    count = store.delete_sessions([sid1, sid3, 99999])
    assert count == 2

    remaining = store.get_sessions()
    assert len(remaining) == 1
    assert remaining[0]["id"] == sid2


def test_save_and_get_session_description(tmp_path):
    """save_session() should store description and get_session() should return it.

    For freeform sessions, the user's original message (description) must be
    stored so it can be displayed as a user bubble when reopening the session.
    Without this, the session detail shows '目标: 无' instead of the user's
    actual question.
    """
    store = MemoryStore(str(tmp_path))
    session_id = store.save_session({
        "test_path": "",
        "description": "请读取 README.md 并总结项目用途",
        "success": True,
        "rounds": 1,
        "reason": "Task completed",
        "final_reply": "这是一个测试代理项目，用于自动修复失败的测试。",
        "actions": [],
    })
    detail = store.get_session(session_id)
    assert detail is not None
    assert detail["description"] == "请读取 README.md 并总结项目用途"
    assert detail["final_reply"] == "这是一个测试代理项目，用于自动修复失败的测试。"
    # get_sessions (list view) should also include description for sidebar
    sessions = store.get_sessions()
    assert sessions[0]["description"] == "请读取 README.md 并总结项目用途"


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
