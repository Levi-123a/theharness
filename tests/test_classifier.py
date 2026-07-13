"""Tests for FailureClassifier — pure regex-based classification of TestResult."""

from the_harness.feedback.classifier import FailureClassifier
from the_harness.models import TestResult, FeedbackType


def _result(exit_code=1, stdout="", stderr="", passed=False):
    """Helper to create a TestResult."""
    return TestResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        passed=passed,
    )


def test_classify_pass():
    """Passed test should classify as PASS."""
    classifier = FailureClassifier()
    tr = _result(exit_code=0, stdout="1 passed", stderr="", passed=True)
    feedback = classifier.classify(tr)
    assert feedback.type == FeedbackType.PASS


def test_classify_syntax_error():
    """SyntaxError should classify as COMPILE_ERROR with location."""
    classifier = FailureClassifier()
    tr = _result(
        stdout="SyntaxError: invalid syntax\n  File 'foo.py', line 5\n    def (:",
        stderr="",
    )
    feedback = classifier.classify(tr)
    assert feedback.type == FeedbackType.COMPILE_ERROR
    assert feedback.location is not None
    assert "foo.py" in feedback.location or "line 5" in feedback.location


def test_classify_assertion_failure():
    """AssertionError should classify as ASSERTION_FAILURE with expected/actual."""
    classifier = FailureClassifier()
    tr = _result(
        stdout="AssertionError: assert 3 == 4\nE       assert 3 == 4",
        stderr="",
    )
    feedback = classifier.classify(tr)
    assert feedback.type == FeedbackType.ASSERTION_FAILURE
    assert feedback.expected is not None
    assert feedback.actual is not None


def test_classify_import_error():
    """ModuleNotFoundError should classify as ENVIRONMENT_ERROR."""
    classifier = FailureClassifier()
    tr = _result(
        stdout="ModuleNotFoundError: No module named 'missing_pkg'",
        stderr="",
    )
    feedback = classifier.classify(tr)
    assert feedback.type == FeedbackType.ENVIRONMENT_ERROR
    assert feedback.message is not None
    assert "missing_pkg" in feedback.message


def test_classify_file_not_found():
    """FileNotFoundError should classify as ENVIRONMENT_ERROR."""
    classifier = FailureClassifier()
    tr = _result(
        stdout="FileNotFoundError: [Errno 2] No such file: 'config.json'",
        stderr="",
    )
    feedback = classifier.classify(tr)
    assert feedback.type == FeedbackType.ENVIRONMENT_ERROR
    assert feedback.message is not None


def test_classify_timeout():
    """Timeout (exit_code=-1 or 'timed out' in stderr) should classify as TIMEOUT."""
    classifier = FailureClassifier()
    tr = _result(exit_code=-1, stdout="", stderr="Test timed out after 30s")
    feedback = classifier.classify(tr)
    assert feedback.type == FeedbackType.TIMEOUT


def test_classify_timeout_by_stderr_only():
    """Timeout detected via 'timeout' in stderr (exit_code != -1) should classify as TIMEOUT."""
    classifier = FailureClassifier()
    tr = _result(exit_code=1, stdout="", stderr="timeout occurred")
    feedback = classifier.classify(tr)
    assert feedback.type == FeedbackType.TIMEOUT


def test_classify_unknown():
    """Unrecognized failure should classify as UNKNOWN."""
    classifier = FailureClassifier()
    tr = _result(exit_code=1, stdout="some weird error", stderr="weird stuff")
    feedback = classifier.classify(tr)
    assert feedback.type == FeedbackType.UNKNOWN


def test_deterministic_same_input_same_output():
    """Same input should always produce same output."""
    classifier = FailureClassifier()
    tr = _result(
        stdout="AssertionError: assert 1 == 2",
        stderr="",
    )
    f1 = classifier.classify(tr)
    f2 = classifier.classify(tr)
    assert f1.type == f2.type
    assert f1.location == f2.location
    assert f1.expected == f2.expected
    assert f1.actual == f2.actual
    assert f1.strategy_hint == f2.strategy_hint


def test_strategy_hint_present():
    """Every classification should include a non-empty strategy_hint."""
    classifier = FailureClassifier()
    cases = [
        _result(exit_code=0, stdout="1 passed", passed=True),
        _result(stdout="SyntaxError: invalid syntax\n  File 'foo.py', line 5"),
        _result(stdout="AssertionError: assert 3 == 4"),
        _result(stdout="ModuleNotFoundError: No module named 'x'"),
        _result(exit_code=-1, stderr="timed out"),
        _result(stdout="weird error"),
    ]
    for tr in cases:
        feedback = classifier.classify(tr)
        assert feedback.strategy_hint != ""
