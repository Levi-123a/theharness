"""Mock LLM provider for deterministic testing."""

from typing import Any

from the_harness.llm.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """A mock LLM provider that returns preset actions sequentially.

    This provider enables deterministic unit testing of the agent loop
    without any network calls or real LLM access.

    Attributes:
        _actions: The preset list of action dicts to return.
        _index: Current position in the action list.
    """

    def __init__(self, actions: list[dict[str, Any]]) -> None:
        """Initialize with a list of preset actions.

        Args:
            actions: List of dicts, each with "action", "params", "reasoning" keys.
        """
        self._actions = actions
        self._index = 0

    def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Return the next preset action.

        Args:
            messages: Ignored (mock provider doesn't use message context).

        Returns:
            The next action dict from the preset list.

        Raises:
            IndexError: If all preset actions have been consumed.
        """
        if self._index >= len(self._actions):
            raise IndexError("No more preset actions available")
        action = self._actions[self._index]
        self._index += 1
        return action

    def reset(self) -> None:
        """Reset the provider to return actions from the beginning."""
        self._index = 0
