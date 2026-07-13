"""Tests for core data models."""

from the_harness.models import (
    ActionType,
    FeedbackType,
    Task,
    Action,
    ActionResult,
    TestResult,
    ClassifiedFeedback,
    Result,
    GuardrailResult,
)


# ── Enum tests ──────────────────────────────────────────────────────


def test_action_type_values():
    """ActionType enum should have correct lowercase string values."""
    assert ActionType.READ_FILE == "read_file"
    assert ActionType.EDIT_FILE == "edit_file"
    assert ActionType.WRITE_FILE == "write_file"
    assert ActionType.RUN_SHELL == "run_shell"
    assert ActionType.RUN_TESTS == "run_tests"
    assert ActionType.GIVE_UP == "give_up"


def test_feedback_type_values():
    """FeedbackType enum should have correct lowercase string values."""
    assert FeedbackType.COMPILE_ERROR == "compile_error"
    assert FeedbackType.ASSERTION_FAILURE == "assertion_failure"
    assert FeedbackType.ENVIRONMENT_ERROR == "environment_error"
    assert FeedbackType.TIMEOUT == "timeout"
    assert FeedbackType.PASS == "pass"
    assert FeedbackType.UNKNOWN == "unknown_failure"


# ── Dataclass tests ─────────────────────────────────────────────────


def test_task_dataclass():
    """Task should have test_path and workspace, no defaults."""
    task = Task(test_path="tests/test_foo.py", workspace="/tmp/project")
    assert task.test_path == "tests/test_foo.py"
    assert task.workspace == "/tmp/project"


def test_action_dataclass():
    """Action should have type, params, and optional reasoning."""
    action = Action(
        type=ActionType.EDIT_FILE,
        params={"file_path": "foo.py", "old_text": "a", "new_text": "b"},
        reasoning="Fix the import",
    )
    assert action.type == ActionType.EDIT_FILE
    assert action.params == {"file_path": "foo.py", "old_text": "a", "new_text": "b"}
    assert action.reasoning == "Fix the import"

    # reasoning has default
    action2 = Action(type=ActionType.RUN_TESTS, params={})
    assert action2.reasoning == ""


def test_action_result_dataclass():
    """ActionResult should have success, output, and optional error."""
    result = ActionResult(success=True, output="All good")
    assert result.success is True
    assert result.output == "All good"
    assert result.error is None

    result2 = ActionResult(success=False, output="", error="File not found")
    assert result2.success is False
    assert result2.error == "File not found"


def test_test_result_dataclass():
    """TestResult should have exit_code, stdout, stderr, passed — no defaults."""
    tr = TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True)
    assert tr.exit_code == 0
    assert tr.stdout == "1 passed"
    assert tr.stderr == ""
    assert tr.passed is True

    tr2 = TestResult(exit_code=1, stdout="", stderr="AssertionError", passed=False)
    assert tr2.exit_code == 1
    assert tr2.passed is False


def test_classified_feedback_dataclass():
    """ClassifiedFeedback should have type and optional fields."""
    cf = ClassifiedFeedback(type=FeedbackType.COMPILE_ERROR)
    assert cf.type == FeedbackType.COMPILE_ERROR
    assert cf.location is None
    assert cf.message is None
    assert cf.expected is None
    assert cf.actual is None
    assert cf.strategy_hint == ""

    cf2 = ClassifiedFeedback(
        type=FeedbackType.ASSERTION_FAILURE,
        location="test_foo.py:10",
        message="assert 1 == 2",
        expected="1",
        actual="2",
        strategy_hint="Check the comparison logic",
    )
    assert cf2.location == "test_foo.py:10"
    assert cf2.expected == "1"
    assert cf2.actual == "2"
    assert cf2.strategy_hint == "Check the comparison logic"


def test_result_dataclass():
    """Result should have success, rounds, reason, and action_history."""
    r = Result(success=True, rounds=3, reason="All tests passed")
    assert r.success is True
    assert r.rounds == 3
    assert r.reason == "All tests passed"
    assert r.action_history == []

    actions = [Action(type=ActionType.EDIT_FILE, params={})]
    r2 = Result(success=False, rounds=5, reason="max rounds exceeded", action_history=actions)
    assert len(r2.action_history) == 1
    assert r2.action_history[0].type == ActionType.EDIT_FILE


def test_guardrail_result_dataclass():
    """GuardrailResult should have blocked and optional reason."""
    gr = GuardrailResult(blocked=True, reason="Dangerous action")
    assert gr.blocked is True
    assert gr.reason == "Dangerous action"

    gr2 = GuardrailResult(blocked=False)
    assert gr2.blocked is False
    assert gr2.reason == ""
