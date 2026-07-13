"""Failure classifier — pure regex-based classification of TestResult.

Categorizes test failures into 5 types using deterministic regex matching.
Same input always produces same output — no LLM, no randomness.
"""

import re

from the_harness.models import TestResult, ClassifiedFeedback, FeedbackType


# ── Strategy hints ───────────────────────────────────────────────────

_HINTS: dict[FeedbackType, str] = {
    FeedbackType.PASS: "All tests passed. No action needed.",
    FeedbackType.COMPILE_ERROR: "Fix the syntax error at the indicated location.",
    FeedbackType.ASSERTION_FAILURE: "Check the logic — the actual value does not match the expected value.",
    FeedbackType.ENVIRONMENT_ERROR: "Install the missing dependency or fix the file path.",
    FeedbackType.TIMEOUT: "Check for infinite loops or performance issues.",
    FeedbackType.UNKNOWN: "Investigate the error message and fix the root cause.",
}

# ── Regex patterns ──────────────────────────────────────────────────

# SyntaxError / IndentationError
_RE_SYNTAX = re.compile(
    r"(SyntaxError|IndentationError):\s*(.+)",
)
_RE_LOCATION = re.compile(
    r"File\s+['\"]([^'\"]+)['\"],\s*line\s+(\d+)",
)

# AssertionError / assert with expected/actual
_RE_ASSERT = re.compile(
    r"assert\s+(\S+)\s*==\s*(\S+)",
)

# ModuleNotFoundError / ImportError with module name
_RE_MODULE = re.compile(
    r"(?:ModuleNotFoundError|ImportError):\s*No module named\s+['\"]([^'\"]+)['\"]",
)

# FileNotFoundError with file name
_RE_FILE_NOT_FOUND = re.compile(
    r"FileNotFoundError:.*?['\"]([^'\"]+)['\"]",
)

# Timeout info
_RE_TIMEOUT = re.compile(r"timed out after\s+(\d+)s?", re.IGNORECASE)


class FailureClassifier:
    """Classifies a TestResult into a ClassifiedFeedback using regex.

    Classification priority order:
    1. passed == True → PASS
    2. SyntaxError|IndentationError → COMPILE_ERROR
    3. AssertionError|assert → ASSERTION_FAILURE
    4. ModuleNotFoundError|ImportError|FileNotFoundError → ENVIRONMENT_ERROR
    5. exit_code == -1 or "timeout" in stderr → TIMEOUT
    6. fallback → UNKNOWN
    """

    def classify(self, result: TestResult) -> ClassifiedFeedback:
        """Classify a test result into structured feedback.

        Args:
            result: The TestResult from running tests.

        Returns:
            ClassifiedFeedback with type, extracted fields, and strategy_hint.
        """
        combined = (result.stdout or "") + "\n" + (result.stderr or "")

        # 1. Pass
        if result.passed:
            return ClassifiedFeedback(
                type=FeedbackType.PASS,
                strategy_hint=_HINTS[FeedbackType.PASS],
            )

        # 2. Syntax / Indentation error
        m = _RE_SYNTAX.search(combined)
        if m:
            error_type = m.group(1)
            message = m.group(2).strip()
            loc_m = _RE_LOCATION.search(combined)
            location_parts = []
            if loc_m:
                location_parts.append(loc_m.group(1))
                location_parts.append(f"line {loc_m.group(2)}")
            location = ", ".join(location_parts) if location_parts else None
            return ClassifiedFeedback(
                type=FeedbackType.COMPILE_ERROR,
                location=location,
                message=f"{error_type}: {message}",
                strategy_hint=_HINTS[FeedbackType.COMPILE_ERROR],
            )

        # 3. Assertion failure
        m = _RE_ASSERT.search(combined)
        if m:
            actual = m.group(1)
            expected = m.group(2)
            return ClassifiedFeedback(
                type=FeedbackType.ASSERTION_FAILURE,
                expected=expected,
                actual=actual,
                message=f"assert {actual} == {expected}",
                strategy_hint=_HINTS[FeedbackType.ASSERTION_FAILURE],
            )

        # 4. Environment error (module not found or file not found)
        m = _RE_MODULE.search(combined)
        if m:
            missing_module = m.group(1)
            return ClassifiedFeedback(
                type=FeedbackType.ENVIRONMENT_ERROR,
                message=f"No module named '{missing_module}'",
                strategy_hint=_HINTS[FeedbackType.ENVIRONMENT_ERROR],
            )

        m = _RE_FILE_NOT_FOUND.search(combined)
        if m:
            missing_file = m.group(1)
            return ClassifiedFeedback(
                type=FeedbackType.ENVIRONMENT_ERROR,
                message=f"File not found: '{missing_file}'",
                strategy_hint=_HINTS[FeedbackType.ENVIRONMENT_ERROR],
            )

        # 5. Timeout
        lower_stderr = (result.stderr or "").lower()
        if result.exit_code == -1 or "timeout" in lower_stderr or "timed out" in lower_stderr:
            m = _RE_TIMEOUT.search(combined)
            timeout_limit = m.group(1) if m else None
            return ClassifiedFeedback(
                type=FeedbackType.TIMEOUT,
                message=f"Timed out after {timeout_limit}s" if timeout_limit else "Test timed out",
                strategy_hint=_HINTS[FeedbackType.TIMEOUT],
            )

        # 6. Unknown fallback
        return ClassifiedFeedback(
            type=FeedbackType.UNKNOWN,
            message=combined.strip()[:200] or None,
            strategy_hint=_HINTS[FeedbackType.UNKNOWN],
        )
