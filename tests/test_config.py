"""Tests for Config dataclass."""
from the_harness.config import Config


def test_default_config_values():
    """Config with no arguments should have all default values."""
    config = Config()
    assert config.max_rounds == 5
    assert config.llm_provider == "openai"
    assert config.model == "gpt-4o-mini"
    assert config.workspace == "."
    assert config.test_timeout == 30


def test_custom_config_values():
    """Config should allow overriding all default values."""
    config = Config(
        max_rounds=10,
        llm_provider="anthropic",
        model="claude-3-sonnet",
        workspace="/tmp/project",
        test_timeout=60,
    )
    assert config.max_rounds == 10
    assert config.llm_provider == "anthropic"
    assert config.model == "claude-3-sonnet"
    assert config.workspace == "/tmp/project"
    assert config.test_timeout == 60
