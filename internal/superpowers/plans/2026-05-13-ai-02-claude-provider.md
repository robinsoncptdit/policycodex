# AI-02 Claude Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a concrete `ClaudeProvider` implementation of the `LLMProvider` abstraction from AI-01 so AI-05 (multi-field eval sets) and the inventory pass orchestrator (AI-10) have a real LLM client to call.

**Architecture:** Single class `ClaudeProvider(LLMProvider)` in `ai/claude_provider.py` wrapping the Anthropic Python SDK's `messages.create` API. Model and max-tokens are configurable per-instance, with sensible defaults (`claude-sonnet-4-6`, 1024). API key flows through the standard `ANTHROPIC_API_KEY` env var that the SDK already reads — we do not re-read it ourselves. Errors from the SDK propagate unwrapped; the caller decides whether to retry. Unit tests mock the SDK client to avoid network calls and to keep tests deterministic.

**Tech Stack:** Python 3.12, `anthropic>=0.40` (already in `ai/requirements.txt`), pytest.

**Ticket reference:** `PolicyWonk-v0.1-Tickets.md` AI-02 ("Claude implementation of the provider interface"). Depends on AI-01 (landed at d837279).

**Convention note:** The spike (`spike/extract.py`) uses `POLICYWONK_MODEL` as an env var. AI-02 introduces `POLICYCODEX_MODEL` for the renamed project. The spike will be updated separately; this plan does **not** touch the spike.

---

## File Structure

- Create: `ai/claude_provider.py` — `ClaudeProvider` class.
- Create: `ai/tests/test_claude_provider.py` — unit tests (mocked SDK).
- Modify: `ai/__init__.py` — re-export `ClaudeProvider` alongside `LLMProvider`.

---

## Task 1: ClaudeProvider with constructor defaults

**Files:**
- Create: `ai/claude_provider.py`
- Create: `ai/tests/test_claude_provider.py`

- [ ] **Step 1: Write the failing test**

Create `ai/tests/test_claude_provider.py`:

```python
"""Tests for ClaudeProvider."""
import os
from unittest.mock import MagicMock, patch

import pytest

from ai.claude_provider import ClaudeProvider
from ai.provider import LLMProvider


def test_claude_provider_is_llm_provider():
    assert issubclass(ClaudeProvider, LLMProvider)


def test_default_model_and_max_tokens(monkeypatch):
    monkeypatch.delenv("POLICYCODEX_MODEL", raising=False)
    provider = ClaudeProvider()
    assert provider.model == "claude-sonnet-4-6"
    assert provider.default_max_tokens == 1024


def test_model_override_via_constructor():
    provider = ClaudeProvider(model="claude-opus-4-7")
    assert provider.model == "claude-opus-4-7"


def test_model_override_via_env(monkeypatch):
    monkeypatch.setenv("POLICYCODEX_MODEL", "claude-haiku-4-5-20251001")
    provider = ClaudeProvider()
    assert provider.model == "claude-haiku-4-5-20251001"


def test_constructor_arg_beats_env(monkeypatch):
    monkeypatch.setenv("POLICYCODEX_MODEL", "claude-haiku-4-5-20251001")
    provider = ClaudeProvider(model="claude-opus-4-7")
    assert provider.model == "claude-opus-4-7"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest ai/tests/test_claude_provider.py -v
```

Expected: ImportError / module-not-found, all 5 fail.

- [ ] **Step 3: Implement the class skeleton**

Create `ai/claude_provider.py`:

```python
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

    The Anthropic SDK reads ANTHROPIC_API_KEY from the environment by
    default; this class does not duplicate that responsibility. To use
    a different model, pass `model=` or set POLICYCODEX_MODEL.
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
        raise NotImplementedError  # implemented in Task 2
```

- [ ] **Step 4: Run tests to verify the 5 constructor tests pass**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest ai/tests/test_claude_provider.py -v
```

Expected: 5 passed (`complete` is not yet tested).

- [ ] **Step 5: Commit**

```bash
git add ai/claude_provider.py ai/tests/test_claude_provider.py
git commit -m "feat(AI-02): ClaudeProvider scaffold with model + env-var resolution"
```

---

## Task 2: Implement `complete()` with a mocked SDK in tests

**Files:**
- Modify: `ai/claude_provider.py` (implement `complete`)
- Modify: `ai/tests/test_claude_provider.py` (add `complete` tests)

- [ ] **Step 1: Write the failing tests**

Append to `ai/tests/test_claude_provider.py`:

```python
def _mock_anthropic_response(text: str) -> MagicMock:
    """Build a mock that mimics the SDK's response shape."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def test_complete_returns_text_from_response():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mock_anthropic_response("hello, world")
    provider = ClaudeProvider(client=fake_client)
    result = provider.complete("hi", max_tokens=128)
    assert result == "hello, world"


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
    fake_client.messages.create.return_value = response
    provider = ClaudeProvider(client=fake_client)
    assert provider.complete("p", max_tokens=64) == "foo bar"


def test_complete_ignores_non_text_blocks():
    """Tool-use or other block types must not contaminate the text output."""
    fake_client = MagicMock()
    text_block = MagicMock(); text_block.type = "text"; text_block.text = "answer"
    tool_block = MagicMock(); tool_block.type = "tool_use"  # has no .text
    response = MagicMock(); response.content = [tool_block, text_block]
    fake_client.messages.create.return_value = response
    provider = ClaudeProvider(client=fake_client)
    assert provider.complete("p", max_tokens=64) == "answer"


def test_complete_propagates_sdk_errors():
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("rate limited")
    provider = ClaudeProvider(client=fake_client)
    with pytest.raises(RuntimeError, match="rate limited"):
        provider.complete("p", max_tokens=64)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest ai/tests/test_claude_provider.py -v
```

Expected: the 5 new tests fail with `NotImplementedError`.

- [ ] **Step 3: Implement `complete()`**

Replace the `complete` stub in `ai/claude_provider.py` with:

```python
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
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest ai/tests/test_claude_provider.py -v
```

Expected: 10 passed (5 constructor + 5 complete).

- [ ] **Step 5: Commit**

```bash
git add ai/claude_provider.py ai/tests/test_claude_provider.py
git commit -m "feat(AI-02): implement ClaudeProvider.complete via Anthropic SDK"
```

---

## Task 3: Re-export from `ai/__init__.py`

**Files:**
- Modify: `ai/__init__.py`

- [ ] **Step 1: Inspect the current `ai/__init__.py`**

```bash
cat /Users/chuck/PolicyWonk/ai/__init__.py
```

- [ ] **Step 2: Add the export**

Ensure `ai/__init__.py` re-exports both symbols. If currently empty, set it to:

```python
"""PolicyCodex AI lane (LLM provider abstraction and implementations)."""
from ai.claude_provider import ClaudeProvider
from ai.provider import LLMProvider

__all__ = ["LLMProvider", "ClaudeProvider"]
```

If non-empty, add the `ClaudeProvider` import and append `"ClaudeProvider"` to `__all__`. Do not remove existing exports.

- [ ] **Step 3: Verify the import path works**

```bash
cd /Users/chuck/PolicyWonk && python -c "from ai import ClaudeProvider, LLMProvider; print(ClaudeProvider.__mro__)"
```

Expected: prints the MRO showing `ClaudeProvider -> LLMProvider -> ABC -> object`.

- [ ] **Step 4: Run all AI tests**

```bash
cd /Users/chuck/PolicyWonk && python -m pytest ai/ -v
```

Expected: all pass (existing 4 from AI-01 + 10 new).

- [ ] **Step 5: Commit**

```bash
git add ai/__init__.py
git commit -m "feat(AI-02): re-export ClaudeProvider from ai/"
```

---

## Definition of Done

- `python -m pytest ai/ -v` → 14 passed (4 AI-01 + 10 AI-02), 0 failed, 0 network calls.
- `from ai import ClaudeProvider` works.
- `ClaudeProvider` honors `model=` constructor arg, then `POLICYCODEX_MODEL` env, then default `claude-sonnet-4-6`.
- `complete()` returns a single string composed of all `text` blocks from the SDK response, in order, ignoring tool-use or other non-text blocks.
- No new entries in `ai/requirements.txt` (the SDK is already pinned at `>=0.40`).
- No changes to `spike/` or `app/`.
