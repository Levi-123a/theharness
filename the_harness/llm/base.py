"""Abstract LLM provider interface."""

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract interface for LLM providers.

    All LLM providers (mock, OpenAI, Anthropic, etc.) must implement this
    interface so the agent loop can swap them without code changes.
    """

    @abstractmethod
    def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Process messages and return an action response.

        Args:
            messages: List of message dicts with "role" and "content" keys.

        Returns:
            A dict with keys "action", "params", and "reasoning".
        """
        ...

    def summarize_session(
        self,
        task_desc: str,
        action_summaries: list[str],
        success: bool,
        reason: str,
    ) -> str:
        """Generate a short one-line summary of the session.

        The summary is displayed in the sidebar session list so users can
        tell sessions apart at a glance, instead of seeing just '#5'.

        The base implementation derives a summary from the inputs without
        calling the LLM.  Subclasses (e.g. OpenAILLMProvider) override
        this to call the LLM for a more intelligent summary.

        Args:
            task_desc: The task description (test_path or user instruction).
            action_summaries: List of per-action reasoning strings.
            success: Whether the session succeeded.
            reason: The exit reason string.

        Returns:
            A short summary string.
        """
        outcome = "成功" if success else "失败"
        if action_summaries:
            return f"{action_summaries[-1]}（{outcome}）"
        return f"{task_desc} — {reason}" if task_desc else reason
