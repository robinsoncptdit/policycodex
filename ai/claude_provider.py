"""Claude implementation of the LLMProvider abstraction."""
from __future__ import annotations

import os
from typing import Optional

from anthropic import Anthropic

from ai.provider import LLMProvider

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 1024


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

    def complete(self, prompt: str, max_tokens: int) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts)
