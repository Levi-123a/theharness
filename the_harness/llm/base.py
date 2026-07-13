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
