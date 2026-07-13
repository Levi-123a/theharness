"""Tests for AgentLoop — the harness kernel that orchestrates all components."""

from the_harness.agent_loop import AgentLoop
from the_harness.config import Config
from the_harness.feedback.classifier import FailureClassifier
from the_harness.feedback.injector import FeedbackInjector
from the_harness.guardrail.guardrail import Guardrail
from the_harness.llm.mock_provider import MockLLMProvider
from the_harness.memory.store import MemoryStore
from the_harness.models import TestResult, Task
from the_harness.tools.dispatcher import ToolDispatcher


class MockValidator:
    """Mock validator that returns preset TestResults sequentially."""
    __test__ = False

    def __init__(self, results):
        self._results = results
        self._index = 0

    def validate(self, test_path):
        if self._index >= len(self._results):
            return self._results[-1]
        r = self._results[self._index]
        self._index += 1
        return r


def _make_loop(tmp_path, llm_actions, validator_results, max_rounds=5):
    """Helper to create an AgentLoop with mock components."""
    config = Config(max_rounds=max_rounds, workspace=str(tmp_path))
    return AgentLoop(
        config=config,
        llm_provider=MockLLMProvider(llm_actions),
        guardrail=Guardrail(str(tmp_path)),
        tool_dispatcher=ToolDispatcher(str(tmp_path)),
        validator=MockValidator(validator_results),
        classifier=FailureClassifier(),
        injector=FeedbackInjector(),
        memory_store=MemoryStore(str(tmp_path)),
    )


def test_success_in_2_rounds(tmp_path):
    """Agent succeeds in 2 rounds: first action fails, second passes."""
    actions = [
        {"action": "write_file", "params": {"file_path": "a.py", "content": "x=1"}, "reasoning": "create"},
        {"action": "write_file", "params": {"file_path": "b.py", "content": "y=2"}, "reasoning": "fix"},
    ]
    results = [
        TestResult(exit_code=1, stdout="1 failed", stderr="err", passed=False),
        TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True),
    ]
    loop = _make_loop(tmp_path, actions, results)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is True
    assert result.rounds == 2


def test_give_up(tmp_path):
    """Agent stops when LLM returns give_up action."""
    actions = [{"action": "give_up", "params": {}, "reasoning": "can't fix"}]
    results = [TestResult(exit_code=1, stdout="fail", stderr="", passed=False)]
    loop = _make_loop(tmp_path, actions, results)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is False
    assert "gave up" in result.reason.lower()


def test_max_rounds_exceeded(tmp_path):
    """Agent stops after max_rounds without success."""
    actions = [
        {"action": "write_file", "params": {"file_path": f"f{i}.py", "content": str(i)}, "reasoning": f"attempt {i}"}
        for i in range(6)
    ]
    results = [TestResult(exit_code=1, stdout="fail", stderr="", passed=False)]
    loop = _make_loop(tmp_path, actions, results, max_rounds=3)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is False
    assert "max rounds" in result.reason.lower()


def test_repeated_action(tmp_path):
    """Agent stops when it repeats the same action twice."""
    action_dict = {"action": "write_file", "params": {"file_path": "same.py", "content": "x=1"}, "reasoning": "same"}
    actions = [action_dict, action_dict]
    results = [TestResult(exit_code=1, stdout="fail", stderr="", passed=False)]
    loop = _make_loop(tmp_path, actions, results, max_rounds=5)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is False
    assert "stuck" in result.reason.lower() or "repeated" in result.reason.lower()


def test_guardrail_blocks(tmp_path):
    """Guardrail blocks dangerous action, agent continues with safe action."""
    actions = [
        {"action": "run_shell", "params": {"command": "rm -rf /"}, "reasoning": "dangerous"},
        {"action": "write_file", "params": {"file_path": "safe.py", "content": "x=1"}, "reasoning": "safe"},
    ]
    results = [
        TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True),
    ]
    loop = _make_loop(tmp_path, actions, results, max_rounds=5)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is True


def test_feedback_drives_correction(tmp_path):
    """Feedback loop: first action causes compile error, second fixes it."""
    actions = [
        {"action": "write_file", "params": {"file_path": "bad.py", "content": "def (:"}, "reasoning": "bad edit"},
        {"action": "write_file", "params": {"file_path": "good.py", "content": "x = 1"}, "reasoning": "good edit"},
    ]
    results = [
        TestResult(exit_code=1, stdout="SyntaxError: invalid syntax", stderr="", passed=False),
        TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True),
    ]
    loop = _make_loop(tmp_path, actions, results, max_rounds=5)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is True
    assert result.rounds == 2
