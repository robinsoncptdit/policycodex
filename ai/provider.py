"""Abstract interface for LLM providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Usage:
    """Per-call usage telemetry, assembled by the provider at call time.

    timestamp is ISO 8601 UTC, stamped when the completion returns (the moment
    the cost is incurred). Foundation for v0.2 spend ceilings (P2.11).
    """

    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    timestamp: str


@dataclass(frozen=True)
class CompletionResult:
    """A completion plus the usage record for the call that produced it."""

    text: str
    usage: Usage


class LLMProvider(ABC):
    """Abstract base class for language model providers."""

    @abstractmethod
    def complete(self, prompt: str, max_tokens: int) -> CompletionResult:
        """Generate a completion for the given prompt.

        Args:
            prompt: The input prompt to complete.
            max_tokens: Maximum tokens in the response.

        Returns:
            A CompletionResult carrying the model's text plus a Usage record.
        """
        pass
