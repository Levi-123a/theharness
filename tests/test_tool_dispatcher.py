"""Tests for ToolDispatcher file operations and shell execution."""

from the_harness.tools.dispatcher import ToolDispatcher
from the_harness.models import Action, ActionType, ActionResult


def test_read_file(tmp_path):
    """read_file should return file content."""
    # Setup: create a file
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")

    dispatcher = ToolDispatcher(str(tmp_path))
    action = Action(
        type=ActionType.READ_FILE,
        params={"file_path": "src/main.py"},
    )
    result = dispatcher.execute(action)
    assert result.success is True
    assert "print('hello')" in result.output


def test_write_file(tmp_path):
    """write_file should create file and parent dirs."""
    dispatcher = ToolDispatcher(str(tmp_path))
    action = Action(
        type=ActionType.WRITE_FILE,
        params={"file_path": "new/dir/file.py", "content": "x = 42"},
    )
    result = dispatcher.execute(action)
    assert result.success is True
    assert (tmp_path / "new" / "dir" / "file.py").exists()
    assert (tmp_path / "new" / "dir" / "file.py").read_text() == "x = 42"


def test_edit_file(tmp_path):
    """edit_file should replace old_text with new_text."""
    (tmp_path / "app.py").write_text("old_value = 1\nother = 2")

    dispatcher = ToolDispatcher(str(tmp_path))
    action = Action(
        type=ActionType.EDIT_FILE,
        params={"file_path": "app.py", "old_text": "old_value = 1", "new_text": "new_value = 42"},
    )
    result = dispatcher.execute(action)
    assert result.success is True
    assert "new_value = 42" in (tmp_path / "app.py").read_text()
    assert "old_value" not in (tmp_path / "app.py").read_text()


def test_edit_text_not_found(tmp_path):
    """edit_file should fail if old_text is not found."""
    (tmp_path / "app.py").write_text("unchanged")

    dispatcher = ToolDispatcher(str(tmp_path))
    action = Action(
        type=ActionType.EDIT_FILE,
        params={"file_path": "app.py", "old_text": "nonexistent", "new_text": "replacement"},
    )
    result = dispatcher.execute(action)
    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error.lower() or "not found" in result.output.lower()


def test_shell_success(tmp_path):
    """run_shell should execute commands and return output."""
    dispatcher = ToolDispatcher(str(tmp_path))
    action = Action(
        type=ActionType.RUN_SHELL,
        params={"command": "echo hello_world"},
    )
    result = dispatcher.execute(action)
    assert result.success is True
    assert "hello_world" in result.output


def test_shell_failure(tmp_path):
    """run_shell should report failure on non-zero exit."""
    dispatcher = ToolDispatcher(str(tmp_path))
    action = Action(
        type=ActionType.RUN_SHELL,
        params={"command": "python -c \"exit(1)\""},
    )
    result = dispatcher.execute(action)
    assert result.success is False


def test_read_nonexistent(tmp_path):
    """read_file should fail gracefully on nonexistent file."""
    dispatcher = ToolDispatcher(str(tmp_path))
    action = Action(
        type=ActionType.READ_FILE,
        params={"file_path": "does_not_exist.py"},
    )
    result = dispatcher.execute(action)
    assert result.success is False
    assert result.error is not None


def test_give_up(tmp_path):
    """give_up should return success with 'gave up' message."""
    dispatcher = ToolDispatcher(str(tmp_path))
    action = Action(
        type=ActionType.GIVE_UP,
        params={},
    )
    result = dispatcher.execute(action)
    assert result.success is True
    assert "gave up" in result.output.lower()
