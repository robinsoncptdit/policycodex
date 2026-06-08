"""Tests for ClaudeProvider."""
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from ai.claude_provider import ClaudeProvider
from ai.provider import CompletionResult, LLMProvider


def test_claude_provider_is_llm_provider():
    assert issubclass(ClaudeProvider, LLMProvider)


def test_default_model_and_max_tokens(monkeypatch):
    monkeypatch.delenv("POLICYCODEX_MODEL", raising=False)
    provider = ClaudeProvider(client=MagicMock())
    assert provider.model == "claude-opus-4-8"
    assert provider.default_max_tokens == 1024


def test_model_override_via_constructor():
    provider = ClaudeProvider(model="claude-opus-4-7", client=MagicMock())
    assert provider.model == "claude-opus-4-7"


def test_model_override_via_env(monkeypatch):
    monkeypatch.setenv("POLICYCODEX_MODEL", "claude-haiku-4-5-20251001")
    provider = ClaudeProvider(client=MagicMock())
    assert provider.model == "claude-haiku-4-5-20251001"


def test_constructor_arg_beats_env(monkeypatch):
    monkeypatch.setenv("POLICYCODEX_MODEL", "claude-haiku-4-5-20251001")
    provider = ClaudeProvider(model="claude-opus-4-7", client=MagicMock())
    assert provider.model == "claude-opus-4-7"


def _mock_anthropic_response(text: str, input_tokens=100, output_tokens=20) -> MagicMock:
    """Build a mock that mimics the SDK's response shape, including usage."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response


def test_complete_returns_text_from_response():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mock_anthropic_response("hello, world")
    provider = ClaudeProvider(client=fake_client)
    result = provider.complete("hi", max_tokens=128)
    assert isinstance(result, CompletionResult)
    assert result.text == "hello, world"


def test_complete_populates_usage():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mock_anthropic_response(
        "hello", input_tokens=4123, output_tokens=512
    )
    provider = ClaudeProvider(model="claude-opus-4-7", client=fake_client)
    result = provider.complete("hi", max_tokens=128)
    assert result.usage.provider == "claude"
    assert result.usage.model == "claude-opus-4-7"
    assert result.usage.input_tokens == 4123
    assert result.usage.output_tokens == 512
    parsed = datetime.fromisoformat(result.usage.timestamp)
    assert parsed.tzinfo is not None


def test_complete_passes_model_max_tokens_and_user_message():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mock_anthropic_response("ok")
    provider = ClaudeProvider(model="claude-opus-4-7", client=fake_client)
    provider.complete("the prompt", max_tokens=256)
    fake_client.messages.create.assert_called_once()
    kwargs = fake_client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-opus-4-7"
    assert kwargs["max_tokens"] == 256
    assert kwargs["messages"] == [{"role": "user", "content": "the prompt"}]


def test_complete_concatenates_multiple_text_blocks():
    fake_client = MagicMock()
    block_a = MagicMock(); block_a.type = "text"; block_a.text = "foo "
    block_b = MagicMock(); block_b.type = "text"; block_b.text = "bar"
    response = MagicMock(); response.content = [block_a, block_b]
    response.usage.input_tokens = 1
    response.usage.output_tokens = 2
    fake_client.messages.create.return_value = response
    provider = ClaudeProvider(client=fake_client)
    assert provider.complete("p", max_tokens=64).text == "foo bar"


def test_complete_ignores_non_text_blocks():
    """Tool-use or other block types must not contaminate the text output."""
    fake_client = MagicMock()
    text_block = MagicMock(); text_block.type = "text"; text_block.text = "answer"
    tool_block = MagicMock(); tool_block.type = "tool_use"  # has no .text
    response = MagicMock(); response.content = [tool_block, text_block]
    response.usage.input_tokens = 1
    response.usage.output_tokens = 2
    fake_client.messages.create.return_value = response
    provider = ClaudeProvider(client=fake_client)
    assert provider.complete("p", max_tokens=64).text == "answer"


def test_complete_propagates_sdk_errors():
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("rate limited")
    provider = ClaudeProvider(client=fake_client)
    with pytest.raises(RuntimeError, match="rate limited"):
        provider.complete("p", max_tokens=64)
