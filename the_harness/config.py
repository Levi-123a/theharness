"""Configuration dataclass for the-harness."""

from dataclasses import dataclass


@dataclass
class Config:
    """Global configuration for the agent harness.

    Attributes:
        max_rounds: Maximum number of feedback-loop rounds before giving up.
        llm_provider: LLM provider name (e.g. "openai", "anthropic").
        model: Default model identifier to use with the provider.
        workspace: Path to the workspace directory the agent operates in.
        test_timeout: Timeout in seconds for running tests.
        base_url: Optional base URL for the LLM API endpoint.
    """

    max_rounds: int = 5
    llm_provider: str = "openai"
    model: str = "gpt-4o-mini"
    workspace: str = "."
    test_timeout: int = 30
    base_url: str = ""
