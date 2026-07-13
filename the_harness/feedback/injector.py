"""Feedback injector — converts ClassifiedFeedback into structured prompt fragments.

Each feedback type produces a different injection text that guides the LLM
in the next round. The strategy_hint is always appended.
"""

from the_harness.models import ClassifiedFeedback, FeedbackType


class FeedbackInjector:
    """Converts ClassifiedFeedback into structured prompt fragments.

    Only injects the current round's feedback summary, not full history.
    """

    def inject(self, feedback: ClassifiedFeedback) -> str:
        """Convert classified feedback into a prompt fragment for the next LLM round.

        Args:
            feedback: The ClassifiedFeedback from the classifier.

        Returns:
            A structured text prompt fragment including strategy_hint.
        """
        body = self._build_body(feedback)
        hint = feedback.strategy_hint
        if hint:
            return f"{body}\nStrategy: {hint}"
        return body

    def _build_body(self, feedback: ClassifiedFeedback) -> str:
        """Build the main injection text based on feedback type."""
        ft = feedback.type

        if ft == FeedbackType.PASS:
            return "All tests passed."

        if ft == FeedbackType.COMPILE_ERROR:
            loc = feedback.location or "unknown location"
            msg = feedback.message or "syntax error"
            return f"Syntax error at {loc}: {msg}. Fix the syntax error."

        if ft == FeedbackType.ASSERTION_FAILURE:
            exp = feedback.expected or "?"
            act = feedback.actual or "?"
            return f"Test failed: expected {exp}, got {act}. Check the logic."

        if ft == FeedbackType.ENVIRONMENT_ERROR:
            msg = feedback.message or "missing dependency"
            return f"Missing dependency: {msg}. Check if dependencies are installed."

        if ft == FeedbackType.TIMEOUT:
            msg = feedback.message or "test timed out"
            return f"Test timed out: {msg}. Check for infinite loops or performance issues."

        # UNKNOWN
        msg = feedback.message or "unknown error"
        return f"Test failed with unknown error: {msg}."
