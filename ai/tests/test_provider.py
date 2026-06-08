"""Tests for LLMProvider abstraction."""
import pytest
from dataclasses import FrozenInstanceError

from ai.provider import CompletionResult, LLMProvider, Usage


def test_llmprovider_abstract_class_cannot_instantiate():
    """Verify LLMProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        LLMProvider()


def test_concrete_subclass_requires_complete_implementation():
    """Verify concrete subclass must implement complete method."""

    class IncompleteProvider(LLMProvider):
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()


def test_concrete_subclass_with_complete_can_instantiate():
    """Verify concrete subclass with complete implementation can instantiate."""

    class ConcreteProvider(LLMProvider):
        def complete(self, prompt: str, max_tokens: int) -> CompletionResult:
            return CompletionResult(text="response", usage=Usage("fake", "m", 0, 0, "t"))

    provider = ConcreteProvider()
    assert provider is not None


def test_complete_method_signature():
    """Verify complete method accepts correct parameters and returns CompletionResult."""

    class ConcreteProvider(LLMProvider):
        def complete(self, prompt: str, max_tokens: int) -> CompletionResult:
            return CompletionResult(
                text=f"mock: {prompt[:20]}... (max_tokens={max_tokens})",
                usage=Usage("fake", "m", 0, 0, "t"),
            )

    provider = ConcreteProvider()
    result = provider.complete("test prompt", 100)
    assert isinstance(result, CompletionResult)
    assert "test prom" in result.text


def test_usage_holds_all_five_fields():
    usage = Usage(
        provider="claude",
        model="claude-opus-4-8",
        input_tokens=4123,
        output_tokens=512,
        timestamp="2026-06-08T18:03:00+00:00",
    )
    assert usage.provider == "claude"
    assert usage.model == "claude-opus-4-8"
    assert usage.input_tokens == 4123
    assert usage.output_tokens == 512
    assert usage.timestamp == "2026-06-08T18:03:00+00:00"


def test_usage_is_frozen():
    usage = Usage("claude", "m", 1, 2, "t")
    with pytest.raises(FrozenInstanceError):
        usage.input_tokens = 99


def test_completion_result_carries_text_and_usage():
    usage = Usage("claude", "m", 1, 2, "t")
    result = CompletionResult(text="hello", usage=usage)
    assert result.text == "hello"
    assert result.usage is usage


def test_completion_result_is_frozen():
    result = CompletionResult(text="hi", usage=Usage("claude", "m", 1, 2, "t"))
    with pytest.raises(FrozenInstanceError):
        result.text = "changed"
