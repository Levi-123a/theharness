"""OpenAI LLM provider — real LLM integration via the OpenAI API."""

import json
import os
from typing import Any

from the_harness.llm.base import LLMProvider

_SYSTEM_PROMPT = """\
You are a coding agent that fixes failing tests. You must respond with a JSON object containing exactly three keys:

- "action": one of "read_file", "edit_file", "write_file", "run_shell", "run_tests", "give_up"
- "params": a dict of parameters for the action
    - read_file: {"file_path": "..."}
    - edit_file: {"file_path": "...", "old_text": "...", "new_text": "..."}
    - write_file: {"file_path": "...", "content": "..."}
    - run_shell: {"command": "..."}
    - run_tests: {"command": "..."}
    - give_up: {}
- "reasoning": a short string explaining why you chose this action

Respond with ONLY the JSON object, no markdown, no explanation."""


class OpenAILLMProvider(LLMProvider):
    """LLM provider that calls the OpenAI Chat Completions API.

    Attributes:
        _api_key: The OpenAI API key.
        _model: The model name (e.g. "gpt-4o-mini").
    """

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini") -> None:
        """Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key. If None, falls back to OPENAI_API_KEY env var.
            model: The model name to use.
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model

    def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Call the OpenAI API and parse the response into an action dict.

        Args:
            messages: List of message dicts with "role" and "content" keys.

        Returns:
            A dict with "action", "params", and "reasoning" keys.

        Raises:
            RuntimeError: If the API call fails or the response is unparseable.
        """
        if not self._api_key:
            raise RuntimeError(
                "No OpenAI API key. Set OPENAI_API_KEY env var or use CredentialManager."
            )

        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("openai package not installed. Run: pip install openai") from e

        client = OpenAI(api_key=self._api_key)

        # Prepend system prompt if not already present
        full_messages: list[dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]
        full_messages.extend(messages)

        response = client.chat.completions.create(
            model=self._model,
            messages=full_messages,
            temperature=0,
        )

        content = response.choices[0].message.content or ""

        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last line (fences)
            lines = [l for l in lines[1:] if not l.strip().startswith("```")]
            content = "\n".join(lines)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"LLM response was not valid JSON: {content[:200]}") from e

        return {
            "action": parsed.get("action", "give_up"),
            "params": parsed.get("params", {}),
            "reasoning": parsed.get("reasoning", ""),
        }
