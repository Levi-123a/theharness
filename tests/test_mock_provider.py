"""Tests for MockLLMProvider and LLMProvider interface."""

import pytest

from the_harness.llm.base import LLMProvider
from the_harness.llm.mock_provider import MockLLMProvider


def test_returns_preset_actions_in_order():
    """MockLLMProvider should return preset actions sequentially."""
    actions = [
        {"action": "edit_file", "params": {"file_path": "foo.py"}, "reasoning": "fix import"},
        {"action": "run_tests", "params": {}, "reasoning": "verify fix"},
    ]
    provider = MockLLMProvider(actions)

    msg1 = provider.complete([{"role": "user", "content": "fix the test"}])
    assert msg1["action"] == "edit_file"
    assert msg1["params"] == {"file_path": "foo.py"}
    assert msg1["reasoning"] == "fix import"

    msg2 = provider.complete([{"role": "user", "content": "continue"}])
    assert msg2["action"] == "run_tests"
    assert msg2["params"] == {}
    assert msg2["reasoning"] == "verify fix"


def test_raises_index_error_when_exhausted():
    """MockLLMProvider should raise IndexError when preset actions are exhausted."""
    actions = [{"action": "give_up", "params": {}, "reasoning": "done"}]
    provider = MockLLMProvider(actions)

    provider.complete([{"role": "user", "content": "go"}])  # consumes the only action

    with pytest.raises(IndexError):
        provider.complete([{"role": "user", "content": "again"}])


def test_reset_restarts_sequence():
    """MockLLMProvider.reset() should restart the action sequence from the beginning."""
    actions = [
        {"action": "edit_file", "params": {}, "reasoning": "first"},
        {"action": "run_tests", "params": {}, "reasoning": "second"},
    ]
    provider = MockLLMProvider(actions)

    # Consume both actions
    provider.complete([])
    provider.complete([])

    # Should be exhausted
    with pytest.raises(IndexError):
        provider.complete([])

    # Reset and verify we get the first action again
    provider.reset()
    msg = provider.complete([])
    assert msg["action"] == "edit_file"
    assert msg["reasoning"] == "first"


def test_summarize_session_returns_string():
    """summarize_session() should return a non-empty summary string.

    The session list sidebar displays this summary so users can tell
    sessions apart at a glance, instead of seeing just '#5'.
    """
    provider = MockLLMProvider([])
    summary = provider.summarize_session(
        task_desc="修复 tests/test_foo.py",
        action_summaries=["读取了 src/foo.py", "修改了变量赋值"],
        success=True,
        reason="All tests passed",
    )
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_summarize_session_does_not_consume_preset_actions():
    """summarize_session() must NOT consume preset actions from complete().

    The mock provider returns actions sequentially; if summarize_session
    accidentally called complete(), it would eat an action and break
    the agent loop's expectations.
    """
    actions = [
        {"action": "edit_file", "params": {}, "reasoning": "fix"},
        {"action": "done", "params": {}, "reasoning": "finished"},
    ]
    provider = MockLLMProvider(actions)

    provider.summarize_session(
        task_desc="task",
        action_summaries=["did something"],
        success=True,
        reason="done",
    )

    # Both preset actions should still be available
    msg = provider.complete([])
    assert msg["action"] == "edit_file"
    msg2 = provider.complete([])
    assert msg2["action"] == "done"
