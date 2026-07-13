"""the-harness mechanism demo — 3 deterministic demonstrations.

All demonstrations use MockLLMProvider (no network/real LLM required).
Exit code 0 if all demonstrations pass.
"""

import sys
import tempfile
from pathlib import Path

from the_harness.agent_loop import AgentLoop
from the_harness.config import Config
from the_harness.feedback.classifier import FailureClassifier
from the_harness.feedback.injector import FeedbackInjector
from the_harness.guardrail.guardrail import Guardrail
from the_harness.llm.mock_provider import MockLLMProvider
from the_harness.memory.store import MemoryStore
from the_harness.models import Task, TestResult
from the_harness.tools.dispatcher import ToolDispatcher


class _MockValidator:
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


def _make_loop(tmpdir, actions, results, max_rounds=5):
    """Create an AgentLoop with mock components."""
    return AgentLoop(
        config=Config(max_rounds=max_rounds, workspace=str(tmpdir)),
        llm_provider=MockLLMProvider(actions),
        guardrail=Guardrail(str(tmpdir)),
        tool_dispatcher=ToolDispatcher(str(tmpdir)),
        validator=_MockValidator(results),
        classifier=FailureClassifier(),
        injector=FeedbackInjector(),
        memory_store=MemoryStore(str(tmpdir)),
    )


def demo_guardrail_interception():
    """Demo 1: Guardrail intercepts dangerous action, then safe action executes.

    MockLLM returns run_shell("rm -rf /") -> guardrail blocks ->
    next mock action is safe write_file -> tests pass.
    """
    print("=" * 60)
    print("Demo 1: Guardrail Interception")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        actions = [
            {"action": "run_shell", "params": {"command": "rm -rf /"}, "reasoning": "dangerous"},
            {"action": "write_file", "params": {"file_path": "safe.py", "content": "x=1"}, "reasoning": "safe"},
        ]
        results = [TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True)]

        loop = _make_loop(tmpdir, actions, results)
        result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmpdir)))

        print(f"  Success: {result.success}")
        print(f"  Rounds: {result.rounds}")
        print(f"  Reason: {result.reason}")
        print(f"  Actions executed: {len(result.action_history)}")

        assert result.success is True, "Expected success"
        assert len(result.action_history) == 1, "Expected only 1 action (safe one)"
        print("  [PASS] Guardrail blocked dangerous action, safe action succeeded.\n")
        return True


def demo_feedback_self_correction():
    """Demo 2: Feedback loop drives self-correction in 2 rounds.

    MockLLM returns edit_file (introduces syntax error) -> validator returns
    compile_error -> injector generates feedback -> 2nd mock action fixes ->
    validator returns pass.
    """
    print("=" * 60)
    print("Demo 2: Feedback Loop Self-Correction")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        actions = [
            {"action": "write_file", "params": {"file_path": "bad.py", "content": "def (:"}, "reasoning": "bad edit"},
            {"action": "write_file", "params": {"file_path": "good.py", "content": "x = 1"}, "reasoning": "good edit"},
        ]
        results = [
            TestResult(exit_code=1, stdout="SyntaxError: invalid syntax", stderr="", passed=False),
            TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True),
        ]

        loop = _make_loop(tmpdir, actions, results)
        result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmpdir)))

        print(f"  Success: {result.success}")
        print(f"  Rounds: {result.rounds}")
        print(f"  Reason: {result.reason}")

        assert result.success is True, "Expected success"
        assert result.rounds == 2, f"Expected 2 rounds, got {result.rounds}"
        print("  [PASS] Feedback loop drove self-correction in 2 rounds.\n")
        return True


def demo_failure_classification_routing():
    """Demo 3: 4 different TestResults -> 4 types -> 4 strategy hints.

    Constructs 4 different TestResults, classifier produces 4 different
    FeedbackTypes, injector produces 4 different strategy hints.
    """
    print("=" * 60)
    print("Demo 3: Failure Classification + Strategy Routing")
    print("=" * 60)

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

    all_passed = True
    for i, (test_result, expected_type) in enumerate(test_cases, 1):
        feedback = classifier.classify(test_result)
        injection = injector.inject(feedback)

        print(f"  Case {i}: {expected_type}")
        print(f"    Type: {feedback.type.value}")
        print(f"    Strategy hint: {feedback.strategy_hint[:60]}...")
        print(f"    Injection (first 80 chars): {injection[:80]}...")

        if feedback.type.value != expected_type:
            print(f"    [FAIL] Expected {expected_type}, got {feedback.type.value}")
            all_passed = False
        elif feedback.strategy_hint not in injection:
            print(f"    [FAIL] Strategy hint not in injection")
            all_passed = False
        else:
            print(f"    [PASS]")

    print()
    return all_passed


def main():
    """Run all 3 demonstrations. Exit 0 if all pass."""
    print("\n" + "=" * 60)
    print("  the-harness — Mechanism Demonstrations")
    print("=" * 60 + "\n")

    results = []
    results.append(demo_guardrail_interception())
    results.append(demo_feedback_self_correction())
    results.append(demo_failure_classification_routing())

    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"  Results: {passed}/{total} demonstrations passed")
    print("=" * 60 + "\n")

    if passed == total:
        print("  All demonstrations passed!")
        sys.exit(0)
    else:
        print(f"  {total - passed} demonstration(s) failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
