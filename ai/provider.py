"""Abstract interface for LLM providers."""
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for language model providers."""

    @abstractmethod
    def complete(self, prompt: str, max_tokens: int) -> str:
        """Generate a completion for the given prompt.

        Args:
            prompt: The input prompt to complete.
            max_tokens: Maximum tokens in the response.

        Returns:
            The model's text completion.
        """
        pass
