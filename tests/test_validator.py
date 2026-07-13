"""Tests for TestValidator with mocked subprocess."""

from unittest.mock import patch, MagicMock
from subprocess import TimeoutExpired

from the_harness.feedback.validator import TestValidator
from the_harness.models import TestResult


def _mock_completed_process(returncode, stdout="", stderr=""):
    """Create a mock CompletedProcess."""
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


def test_validate_pass(tmp_path):
    """validate() should return passed=True when exit_code is 0."""
    validator = TestValidator(str(tmp_path))
    with patch("the_harness.feedback.validator.subprocess.run") as mock_run:
        mock_run.return_value = _mock_completed_process(0, stdout="1 passed", stderr="")
        result = validator.validate("tests/test_foo.py")
    assert result.passed is True
    assert result.exit_code == 0
    assert "1 passed" in result.stdout


def test_validate_fail(tmp_path):
    """validate() should return passed=False when exit_code is non-zero."""
    validator = TestValidator(str(tmp_path))
    with patch("the_harness.feedback.validator.subprocess.run") as mock_run:
        mock_run.return_value = _mock_completed_process(1, stdout="1 failed", stderr="AssertionError")
        result = validator.validate("tests/test_foo.py")
    assert result.passed is False
    assert result.exit_code == 1
    assert "AssertionError" in result.stderr


def test_validate_syntax_error(tmp_path):
    """validate() should capture syntax errors in stdout."""
    validator = TestValidator(str(tmp_path))
    syntax_output = "SyntaxError: invalid syntax\n  File 'foo.py', line 5\n    def (:"
    with patch("the_harness.feedback.validator.subprocess.run") as mock_run:
        mock_run.return_value = _mock_completed_process(1, stdout=syntax_output, stderr="")
        result = validator.validate("tests/test_foo.py")
    assert result.passed is False
    assert "SyntaxError" in result.stdout


def test_validate_timeout(tmp_path):
    """validate() should handle timeout gracefully."""
    validator = TestValidator(str(tmp_path), timeout=5)
    with patch("the_harness.feedback.validator.subprocess.run") as mock_run:
        mock_run.side_effect = TimeoutExpired(cmd="pytest", timeout=5)
        result = validator.validate("tests/test_foo.py")
    assert result.passed is False
    assert "timed out" in result.stderr.lower()


def test_validate_pytest_not_found(tmp_path):
    """validate() should handle FileNotFoundError when pytest is not installed."""
    validator = TestValidator(str(tmp_path))
    with patch("the_harness.feedback.validator.subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("python")
        result = validator.validate("tests/test_foo.py")
    assert result.passed is False
    assert "pytest not found" in result.stderr.lower()
