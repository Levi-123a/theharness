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
