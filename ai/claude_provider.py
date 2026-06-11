"""Claude implementation of the LLMProvider abstraction."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from anthropic import Anthropic

from ai.provider import CompletionResult, LLMProvider, Usage

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 1024
PROVIDER_NAME = "claude"


class ClaudeProvider(LLMProvider):
    """LLM provider backed by the Anthropic Python SDK.

    The SDK reads ANTHROPIC_API_KEY from the environment by default;
    this class does not duplicate that responsibility. To override the
    model, pass `model=` or set POLICYCODEX_MODEL.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        default_max_tokens: int = DEFAULT_MAX_TOKENS,
        client: Optional[Anthropic] = None,
    ) -> None:
        self.model = model or os.getenv("POLICYCODEX_MODEL", DEFAULT_MODEL)
        self.default_max_tokens = default_max_tokens
        self._client = client or Anthropic()

    @classmethod
    def test_key(cls, api_key: str) -> bool:
        """DISC-06: minimum-cost validation. Raises RuntimeError on any non-success."""
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        try:
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=5,
                messages=[{"role": "user", "content": "ok"}],
            )
        except anthropic.AuthenticationError as exc:
            raise RuntimeError(f"401 {exc}") from exc
        except anthropic.APIError as exc:
            raise RuntimeError(str(exc)) from exc
        return True

    def complete(self, prompt: str, max_tokens: int) -> CompletionResult:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        usage = Usage(
            provider=PROVIDER_NAME,
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        return CompletionResult(text="".join(parts), usage=usage)
