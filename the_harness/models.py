"""Core data models for the-harness.

All data structures used across the agent harness: enums, action types,
test results, classified feedback, and aggregate result objects.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Enums ────────────────────────────────────────────────────────────


class ActionType(str, Enum):
    """Types of actions the agent can execute."""

    READ_FILE = "read_file"
    EDIT_FILE = "edit_file"
    WRITE_FILE = "write_file"
    RUN_SHELL = "run_shell"
    RUN_TESTS = "run_tests"
    GIVE_UP = "give_up"


class FeedbackType(str, Enum):
    """Classification of test failure feedback."""

    COMPILE_ERROR = "compile_error"
    ASSERTION_FAILURE = "assertion_failure"
    ENVIRONMENT_ERROR = "environment_error"
    TIMEOUT = "timeout"
    PASS = "pass"
    UNKNOWN = "unknown_failure"


# ── Dataclasses ──────────────────────────────────────────────────────


@dataclass
class Task:
    """A fix task for the agent to work on.

    Attributes:
        test_path: Path to the test file to make pass.
        workspace: Path to the workspace directory.
    """

    test_path: str
    workspace: str


@dataclass
class Action:
    """An action the agent wants to execute.

    Attributes:
        type: The type of action (read, edit, write, shell, tests, give_up).
        params: Parameters for the action (e.g. file_path, old_text, new_text).
        reasoning: The agent's reasoning for this action.
    """

    type: ActionType
    params: dict[str, Any]
    reasoning: str = ""


@dataclass
class ActionResult:
    """Result of executing an action.

    Attributes:
        success: Whether the action succeeded.
        output: Standard output or result text.
        error: Error message if the action failed, None otherwise.
    """

    success: bool
    output: str = ""
    error: str | None = None


@dataclass
class TestResult:
    """Result of running tests.

    Attributes:
        exit_code: The exit code of the test runner.
        stdout: Standard output from the test runner.
        stderr: Standard error from the test runner.
        passed: Whether all tests passed (exit_code == 0).
    """

    # Tell pytest this is not a test class (name starts with "Test")
    __test__ = False

    exit_code: int
    stdout: str
    stderr: str
    passed: bool


@dataclass
class ClassifiedFeedback:
    """Classified feedback from a test result.

    Attributes:
        type: The classified feedback type.
        location: File and line number where the error occurred, if available.
        message: The error message, if available.
        expected: Expected value for assertion failures, if available.
        actual: Actual value for assertion failures, if available.
        strategy_hint: A strategy hint for the LLM to use in the next round.
    """

    type: FeedbackType
    location: str | None = None
    message: str | None = None
    expected: str | None = None
    actual: str | None = None
    strategy_hint: str = ""


@dataclass
class Result:
    """Final result of an agent run.

    Attributes:
        success: Whether the agent successfully fixed the tests.
        rounds: Number of rounds the agent ran.
        reason: Why the agent stopped (success, max rounds, gave up, etc.).
        action_history: List of all actions the agent took.
    """

    success: bool
    rounds: int
    reason: str
    action_history: list[Action] = field(default_factory=list)


@dataclass
class GuardrailResult:
    """Result of a guardrail check.

    Attributes:
        blocked: Whether the action was blocked.
        reason: Why the action was blocked, if it was.
    """

    blocked: bool
    reason: str = ""
