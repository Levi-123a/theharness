"""Tests for FeedbackInjector — converts ClassifiedFeedback into prompt fragments."""

from the_harness.feedback.injector import FeedbackInjector
from the_harness.models import ClassifiedFeedback, FeedbackType


def test_inject_compile_error():
    """COMPILE_ERROR injection should include location."""
    injector = FeedbackInjector()
    feedback = ClassifiedFeedback(
        type=FeedbackType.COMPILE_ERROR,
        location="foo.py, line 5",
        message="SyntaxError: invalid syntax",
        strategy_hint="Fix the syntax error at the indicated location.",
    )
    text = injector.inject(feedback)
    assert "foo.py" in text
    assert "line 5" in text
    assert "SyntaxError" in text


def test_inject_assertion_failure():
    """ASSERTION_FAILURE injection should include expected and actual."""
    injector = FeedbackInjector()
    feedback = ClassifiedFeedback(
        type=FeedbackType.ASSERTION_FAILURE,
        expected="4",
        actual="3",
        message="assert 3 == 4",
        strategy_hint="Check the logic.",
    )
    text = injector.inject(feedback)
    assert "4" in text
    assert "3" in text


def test_inject_environment_error():
    """ENVIRONMENT_ERROR injection should include missing module."""
    injector = FeedbackInjector()
    feedback = ClassifiedFeedback(
        type=FeedbackType.ENVIRONMENT_ERROR,
        message="No module named 'missing_pkg'",
        strategy_hint="Install the missing dependency.",
    )
    text = injector.inject(feedback)
    assert "missing_pkg" in text


def test_inject_timeout():
    """TIMEOUT injection should include timeout info."""
    injector = FeedbackInjector()
    feedback = ClassifiedFeedback(
        type=FeedbackType.TIMEOUT,
        message="Timed out after 30s",
        strategy_hint="Check for infinite loops.",
    )
    text = injector.inject(feedback)
    assert "30" in text or "timed out" in text.lower()


def test_inject_unknown():
    """UNKNOWN injection should include error message."""
    injector = FeedbackInjector()
    feedback = ClassifiedFeedback(
        type=FeedbackType.UNKNOWN,
        message="some weird error",
        strategy_hint="Investigate the error.",
    )
    text = injector.inject(feedback)
    assert "weird" in text.lower() or "unknown" in text.lower()


def test_inject_pass():
    """PASS injection should indicate all tests passed."""
    injector = FeedbackInjector()
    feedback = ClassifiedFeedback(
        type=FeedbackType.PASS,
        strategy_hint="All tests passed. No action needed.",
    )
    text = injector.inject(feedback)
    assert "passed" in text.lower()


def test_inject_includes_strategy_hint():
    """Every injection should include the strategy_hint in the output."""
    injector = FeedbackInjector()
    feedback = ClassifiedFeedback(
        type=FeedbackType.COMPILE_ERROR,
        location="foo.py, line 5",
        message="SyntaxError: invalid syntax",
        strategy_hint="Fix the syntax error at the indicated location.",
    )
    text = injector.inject(feedback)
    assert "Strategy:" in text
    assert feedback.strategy_hint in text
