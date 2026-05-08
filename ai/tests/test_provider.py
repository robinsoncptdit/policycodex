"""Tests for LLMProvider abstraction."""
import pytest
from ai.provider import LLMProvider


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
        def complete(self, prompt: str, max_tokens: int) -> str:
            return "response"

    provider = ConcreteProvider()
    assert provider is not None


def test_complete_method_signature():
    """Verify complete method accepts correct parameters and returns string."""

    class ConcreteProvider(LLMProvider):
        def complete(self, prompt: str, max_tokens: int) -> str:
            return f"mock: {prompt[:20]}... (max_tokens={max_tokens})"

    provider = ConcreteProvider()
    result = provider.complete("test prompt", 100)
    assert isinstance(result, str)
    assert "test prom" in result
