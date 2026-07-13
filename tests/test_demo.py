"""Tests for demo.py — 3 deterministic mechanism demonstrations."""

import subprocess
import sys
from pathlib import Path

from the_harness.feedback.classifier import FailureClassifier
from the_harness.feedback.injector import FeedbackInjector
from the_harness.guardrail.guardrail import Guardrail
from the_harness.models import Action, ActionType, TestResult


DEMO_PATH = Path(__file__).parent.parent / "demo.py"


def test_demo_guardrail_interception(tmp_path):
    """Demo 1: Guardrail intercepts dangerous action, then safe action executes."""
    # Setup: MockLLM returns rm -rf / then a safe write_file
    from the_harness.agent_loop import AgentLoop
    from the_harness.config import Config
    from the_harness.feedback.classifier import FailureClassifier
    from the_harness.feedback.injector import FeedbackInjector
    from the_harness.llm.mock_provider import MockLLMProvider
    from the_harness.memory.store import MemoryStore
    from the_harness.models import Task, TestResult
    from the_harness.tools.dispatcher import ToolDispatcher

    class _MockValidator:
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

    actions = [
        {"action": "run_shell", "params": {"command": "rm -rf /"}, "reasoning": "dangerous"},
        {"action": "write_file", "params": {"file_path": "safe.py", "content": "x=1"}, "reasoning": "safe"},
    ]
    results = [TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True)]

    loop = AgentLoop(
        config=Config(max_rounds=5, workspace=str(tmp_path)),
        llm_provider=MockLLMProvider(actions),
        guardrail=Guardrail(str(tmp_path)),
        tool_dispatcher=ToolDispatcher(str(tmp_path)),
        validator=_MockValidator(results),
        classifier=FailureClassifier(),
        injector=FeedbackInjector(),
        memory_store=MemoryStore(str(tmp_path)),
    )
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))

    # Guardrail blocked the dangerous action, agent continued with safe action
    assert result.success is True
    assert len(result.action_history) == 1  # only the safe action was executed


def test_demo_feedback_self_correction(tmp_path):
    """Demo 2: Feedback loop drives self-correction in 2 rounds."""
    from the_harness.agent_loop import AgentLoop
    from the_harness.config import Config
    from the_harness.feedback.classifier import FailureClassifier
    from the_harness.feedback.injector import FeedbackInjector
    from the_harness.llm.mock_provider import MockLLMProvider
    from the_harness.memory.store import MemoryStore
    from the_harness.models import Task, TestResult
    from the_harness.tools.dispatcher import ToolDispatcher

    class _MockValidator:
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

    actions = [
        {"action": "write_file", "params": {"file_path": "bad.py", "content": "def (:"}, "reasoning": "bad"},
        {"action": "write_file", "params": {"file_path": "good.py", "content": "x = 1"}, "reasoning": "fix"},
    ]
    results = [
        TestResult(exit_code=1, stdout="SyntaxError: invalid syntax", stderr="", passed=False),
        TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True),
    ]

    loop = AgentLoop(
        config=Config(max_rounds=5, workspace=str(tmp_path)),
        llm_provider=MockLLMProvider(actions),
        guardrail=Guardrail(str(tmp_path)),
        tool_dispatcher=ToolDispatcher(str(tmp_path)),
        validator=_MockValidator(results),
        classifier=FailureClassifier(),
        injector=FeedbackInjector(),
        memory_store=MemoryStore(str(tmp_path)),
    )
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))

    assert result.success is True
    assert result.rounds == 2


def test_demo_failure_classification_routing():
    """Demo 3: 4 different TestResults produce 4 different types + strategy hints."""
    classifier = FailureClassifier()
    injector = FeedbackInjector()

    test_cases = [
        (
            TestResult(exit_code=1, stdout="SyntaxError: invalid syntax", stderr="", passed=False),
            "compile_error",
        ),
        (
            TestResult(exit_code=1, stdout="assert 5 == 3", stderr="", passed=False),
            "assertion_failure",
        ),
        (
            TestResult(exit_code=1, stdout="ModuleNotFoundError: No module named 'foo'", stderr="", passed=False),
            "environment_error",
        ),
        (
            TestResult(exit_code=-1, stdout="", stderr="timed out after 30s", passed=False),
            "timeout",
        ),
    ]

    for test_result, expected_type in test_cases:
        feedback = classifier.classify(test_result)
        assert feedback.type.value == expected_type
        injection = injector.inject(feedback)
        assert feedback.strategy_hint in injection
