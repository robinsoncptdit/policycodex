# AI-16 Usage Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record provider name, model id, input/output token counts, and call timestamp for every per-policy inventory extraction, surfaced into `policies/<slug>.audit.yaml` alongside the existing confidence values.

**Architecture:** `LLMProvider.complete()` changes its return type from `str` to a frozen `CompletionResult(text, usage)` dataclass. `ClaudeProvider` assembles the full `Usage` record inside `complete()`. The inventory call site attaches the usage as a private `_usage` dict (mirroring the existing `_source_file` convention); the audit emitter renders it as a `usage:` block; `emit.py` strips `_usage` from the human-readable policy markdown. The retention call site adapts to the new return type but discards usage (out of scope for v0.1).

**Tech Stack:** Python 3.14, dataclasses, PyYAML, pytest, Anthropic SDK.

**Test runner:** `ai/venv/bin/python -m pytest` (no root venv exists; system python lacks pytest).

**Spec:** `internal/superpowers/specs/2026-06-08-ai-16-usage-capture-design.md`

---

## File Structure

- `ai/provider.py` — add `Usage` + `CompletionResult` dataclasses; change `complete()` return annotation to `CompletionResult`.
- `ai/claude_provider.py` — build and return `CompletionResult` with a populated `Usage`; add `PROVIDER_NAME` constant.
- `ai/inventory_extract.py` — read `result.text`, attach `metadata["_usage"] = asdict(result.usage)`.
- `ai/retention_extract.py` — read `result.text`, ignore `result.usage`.
- `ai/audit.py` — emit a `usage:` block from `extraction.get("_usage")`.
- `ai/emit.py` — add `_usage` to `_PRIVATE_FIELDS`.
- Tests: `test_provider.py`, `test_claude_provider.py`, `test_inventory_extract.py`, `test_retention_extract.py`, `test_audit.py`, `test_emit.py`.

---

## Task 1: CompletionResult + Usage dataclasses

**Files:**
- Modify: `ai/provider.py`
- Test: `ai/tests/test_provider.py`

- [ ] **Step 1: Write the failing test**

Add to `ai/tests/test_provider.py` (keep the existing tests; update the two concrete fakes and the signature test to the new return type):

```python
from dataclasses import FrozenInstanceError

from ai.provider import CompletionResult, Usage


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
```

Then update the two existing concrete-subclass tests so their fakes return the new type:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ai/tests/test_provider.py -v`
Expected: FAIL with `ImportError: cannot import name 'CompletionResult' from 'ai.provider'`

- [ ] **Step 3: Write minimal implementation**

Replace the contents of `ai/provider.py` with:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ai/tests/test_provider.py -v`
Expected: PASS (all tests, including the updated fakes)

- [ ] **Step 5: Commit**

```bash
git add ai/provider.py ai/tests/test_provider.py
git commit -m "feat(ai-16): add CompletionResult + Usage to the provider contract"
```

---

## Task 2: ClaudeProvider returns CompletionResult

**Files:**
- Modify: `ai/claude_provider.py`
- Test: `ai/tests/test_claude_provider.py`

- [ ] **Step 1: Write the failing test**

In `ai/tests/test_claude_provider.py`, update the `_mock_anthropic_response` helper to attach a usage shape, and rewrite the four `complete()`-result assertions to the new return type. Replace the helper and the affected tests:

```python
from ai.provider import CompletionResult


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
    # timestamp is ISO 8601 UTC; parseable and tz-aware.
    from datetime import datetime
    parsed = datetime.fromisoformat(result.usage.timestamp)
    assert parsed.tzinfo is not None


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
```

Note: `test_complete_passes_model_max_tokens_and_user_message` and `test_complete_propagates_sdk_errors` keep working unchanged — the first inspects call kwargs (not the return), the second triggers `side_effect` before any return. Leave them as-is.

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ai/tests/test_claude_provider.py -v`
Expected: FAIL — `test_complete_returns_text_from_response` errors because `complete()` returns a `str`, so `isinstance(result, CompletionResult)` is False / `result.text` raises `AttributeError`.

- [ ] **Step 3: Write minimal implementation**

Edit `ai/claude_provider.py`. Update imports and the model-emit constant, and rewrite `complete()`:

```python
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
```

Then replace the `complete` method body:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ai/tests/test_claude_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai/claude_provider.py ai/tests/test_claude_provider.py
git commit -m "feat(ai-16): ClaudeProvider returns CompletionResult with usage"
```

---

## Task 3: inventory_extract threads usage into _usage

**Files:**
- Modify: `ai/inventory_extract.py:147-153`
- Test: `ai/tests/test_inventory_extract.py`

- [ ] **Step 1: Write the failing test**

In `ai/tests/test_inventory_extract.py`, update `FakeProvider` to return a `CompletionResult`, and adjust the two extraction tests (which currently assert raw-dict equality) to account for the attached `_usage`. Add imports and replace the fake + affected tests:

```python
from dataclasses import asdict

from ai.provider import CompletionResult, Usage

USAGE = Usage("fake", "m", 11, 22, "2026-06-08T00:00:00+00:00")


class FakeProvider:
    """Stands in for ai.provider.LLMProvider. Returns canned text + usage."""
    def __init__(self, text, usage=USAGE):
        self._text = text
        self._usage = usage
        self.last_prompt = None
        self.last_max_tokens = None

    def complete(self, prompt, max_tokens):
        self.last_prompt = prompt
        self.last_max_tokens = max_tokens
        return CompletionResult(text=self._text, usage=self._usage)


def test_extract_policy_metadata_calls_provider_and_parses():
    provider = FakeProvider(json.dumps(VALID_EXTRACTION))
    result = extract_policy_metadata(provider, "document body text", TAXONOMY)
    # All parsed fields survive; _usage is attached on top.
    assert {k: v for k, v in result.items() if k != "_usage"} == VALID_EXTRACTION
    assert provider.last_max_tokens == EXTRACTION_MAX_TOKENS
    assert "document body text" in provider.last_prompt
    assert "taxonomy reference" in provider.last_prompt


def test_extract_policy_metadata_attaches_usage():
    provider = FakeProvider(json.dumps(VALID_EXTRACTION))
    result = extract_policy_metadata(provider, "body", TAXONOMY)
    assert result["_usage"] == asdict(USAGE)
```

`test_extract_truncates_long_document` keeps working unchanged (it only inspects `provider.last_prompt`).

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ai/tests/test_inventory_extract.py -v`
Expected: FAIL — `extract_policy_metadata` passes a `CompletionResult` to `parse_inventory_response`, which calls `.strip()` on it and raises `AttributeError`; `test_extract_policy_metadata_attaches_usage` fails on the missing `_usage` key.

- [ ] **Step 3: Write minimal implementation**

Edit `ai/inventory_extract.py`. Add the import near the top:

```python
from dataclasses import asdict
```

Replace `extract_policy_metadata` (currently lines 147-153):

```python
def extract_policy_metadata(
    provider: LLMProvider, document_text: str, taxonomy: dict[str, Any] | None
) -> dict[str, Any]:
    """Run the extraction prompt against a single document's text.

    Attaches the call's usage telemetry as the private ``_usage`` key (a plain
    dict), mirroring the ``_source_file`` convention: stripped from the policy
    markdown by ai/emit.py, surfaced in the audit sidecar by ai/audit.py.
    """
    prompt = build_inventory_prompt(taxonomy) + document_text[:MAX_DOCUMENT_CHARS]
    result = provider.complete(prompt, EXTRACTION_MAX_TOKENS)
    metadata = parse_inventory_response(result.text)
    metadata["_usage"] = asdict(result.usage)
    return metadata
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ai/tests/test_inventory_extract.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai/inventory_extract.py ai/tests/test_inventory_extract.py
git commit -m "feat(ai-16): attach call usage to inventory extraction as _usage"
```

---

## Task 4: retention_extract adapts to CompletionResult (no metering)

**Files:**
- Modify: `ai/retention_extract.py:85-89`
- Test: `ai/tests/test_retention_extract.py`

- [ ] **Step 1: Write the failing test**

In `ai/tests/test_retention_extract.py`, update `FakeProvider` to return a `CompletionResult`. The existing assertions stay valid (retention discards usage). Replace the fake and add an import:

```python
from ai.provider import CompletionResult, Usage


class FakeProvider:
    """Stands in for ai.provider.LLMProvider. Returns canned text + usage."""
    def __init__(self, text):
        self._text = text
        self.last_prompt = None
        self.last_max_tokens = None

    def complete(self, prompt, max_tokens):
        self.last_prompt = prompt
        self.last_max_tokens = max_tokens
        return CompletionResult(
            text=self._text,
            usage=Usage("fake", "m", 1, 2, "2026-06-08T00:00:00+00:00"),
        )
```

Add one test asserting the bundle dict carries no usage telemetry (retention stays unmetered in v0.1):

```python
def test_extract_bundle_does_not_carry_usage():
    provider = FakeProvider(json.dumps(VALID_BUNDLE))
    result = extract_retention_bundle(provider, "PDF TEXT HERE")
    assert "_usage" not in result
    assert result == VALID_BUNDLE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ai/tests/test_retention_extract.py -v`
Expected: FAIL — `extract_retention_bundle` passes a `CompletionResult` to `parse_bundle_response`, which calls `.strip()` on it and raises `AttributeError`.

- [ ] **Step 3: Write minimal implementation**

Edit `ai/retention_extract.py`, replace `extract_retention_bundle` (lines 85-89):

```python
def extract_retention_bundle(provider: LLMProvider, document_text: str) -> dict[str, Any]:
    """Run the extraction prompt against the retention document text.

    Uses only the completion text; per AI-16 scope the retention-bundle call
    stays unmetered in v0.1 (it has no audit sidecar to carry usage).
    """
    prompt = RETENTION_BUNDLE_PROMPT + document_text[:MAX_DOCUMENT_CHARS]
    result = provider.complete(prompt, EXTRACTION_MAX_TOKENS)
    return parse_bundle_response(result.text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ai/tests/test_retention_extract.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai/retention_extract.py ai/tests/test_retention_extract.py
git commit -m "feat(ai-16): retention extraction adapts to CompletionResult"
```

---

## Task 5: audit.py emits the usage block

**Files:**
- Modify: `ai/audit.py`
- Test: `ai/tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

Add to `ai/tests/test_audit.py`:

```python
from ai.audit import USAGE_FIELD_ORDER


def test_usage_block_rendered_from_private_key():
    extraction = {
        "title": "T",
        "category_confidence": "high",
        "_usage": {
            "provider": "claude",
            "model": "claude-opus-4-8",
            "input_tokens": 4123,
            "output_tokens": 512,
            "timestamp": "2026-06-08T18:03:00+00:00",
        },
    }
    doc = _load(to_audit_yaml(extraction))
    assert doc["usage"] == {
        "provider": "claude",
        "model": "claude-opus-4-8",
        "input_tokens": 4123,
        "output_tokens": 512,
        "timestamp": "2026-06-08T18:03:00+00:00",
    }


def test_usage_block_all_null_when_absent():
    doc = _load(to_audit_yaml({"title": "T", "category_confidence": "high"}))
    assert list(doc["usage"].keys()) == list(USAGE_FIELD_ORDER)
    assert all(v is None for v in doc["usage"].values())


def test_usage_key_not_leaked_as_top_level_underscore():
    doc = _load(to_audit_yaml({"_usage": {"provider": "claude"}}))
    # The private key itself never appears; only the rendered usage block.
    assert "_usage" not in doc
    assert doc["usage"]["provider"] == "claude"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ai/tests/test_audit.py -v`
Expected: FAIL with `ImportError: cannot import name 'USAGE_FIELD_ORDER' from 'ai.audit'`

- [ ] **Step 3: Write minimal implementation**

Edit `ai/audit.py`. Add the field-order constant after `_CONFIDENCE_SUFFIX`:

```python
# Canonical order of the per-call usage telemetry (AI-16). Always emitted as a
# top-level `usage:` block; absent fields render null, mirroring the confidence
# map, so audit diffs stay stable across runs.
USAGE_FIELD_ORDER: tuple[str, ...] = (
    "provider",
    "model",
    "input_tokens",
    "output_tokens",
    "timestamp",
)
```

Add a helper after `_confidence_map`:

```python
def _usage_map(extraction: dict[str, Any]) -> dict[str, Any]:
    """Return the usage sub-map: canonical fields in order, null when absent."""
    usage = extraction.get("_usage") or {}
    return {field: usage.get(field) for field in USAGE_FIELD_ORDER}
```

Update `to_audit_yaml`'s `doc` to add the `usage` block after `confidence`:

```python
    doc: dict[str, Any] = {
        "title": extraction.get("title"),
        "source_file": extraction.get("_source_file"),
        "confidence": _confidence_map(extraction),
        "usage": _usage_map(extraction),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ai/tests/test_audit.py -v`
Expected: PASS (new tests plus all existing audit tests — the added `usage:` block does not disturb `title`/`source_file`/`confidence`)

- [ ] **Step 5: Commit**

```bash
git add ai/audit.py ai/tests/test_audit.py
git commit -m "feat(ai-16): emit usage block in the audit sidecar"
```

---

## Task 6: emit.py strips _usage from policy markdown

**Files:**
- Modify: `ai/emit.py:48`
- Test: `ai/tests/test_emit.py`

- [ ] **Step 1: Write the failing test**

Add to `ai/tests/test_emit.py`:

```python
def test_usage_metadata_excluded_from_frontmatter():
    """_usage is per-call telemetry and must not leak into policy markdown."""
    extraction = {
        "title": "T",
        "summary": "S",
        "_usage": {
            "provider": "claude",
            "model": "claude-opus-4-8",
            "input_tokens": 4123,
            "output_tokens": 512,
            "timestamp": "2026-06-08T18:03:00+00:00",
        },
    }
    md = to_markdown(extraction)
    fm, _ = _split_frontmatter(md)

    assert "_usage" not in fm
    # No telemetry value leaks anywhere in the rendered markdown.
    assert "claude-opus-4-8" not in md
    assert "4123" not in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ai/venv/bin/python -m pytest ai/tests/test_emit.py::test_usage_metadata_excluded_from_frontmatter -v`
Expected: FAIL — `_usage` is not in the `_PRIVATE_FIELDS` whitelist, so it is appended to the front matter as an extra key and its nested values render in the markdown.

- [ ] **Step 3: Write minimal implementation**

Edit `ai/emit.py:48`, extend `_PRIVATE_FIELDS`:

```python
# Spike-internal / private fields excluded from output entirely.
_PRIVATE_FIELDS: frozenset[str] = frozenset({"_source_file", "_usage"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ai/venv/bin/python -m pytest ai/tests/test_emit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai/emit.py ai/tests/test_emit.py
git commit -m "feat(ai-16): strip _usage telemetry from policy markdown"
```

---

## Final verification

- [ ] **Run the full suite**

Run: `ai/venv/bin/python -m pytest`
Expected: PASS, suite count up by the new tests (513 -> ~522). No regressions in `test_inventory.py` (the orchestrator emits whatever dict it receives; the added `_usage` flows into the audit sidecar and is stripped from markdown).

- [ ] **Confirm no PT leakage**

The provider name is the generic string `"claude"` (the LLM, not a diocese). No diocese-specific values introduced. Consistent with ship-generic.

---

## Self-review notes

- **Spec coverage:** scope (per-policy only) — Tasks 3 + 4; richer return type — Tasks 1 + 2; provider stamps timestamp — Task 2; usage block always-emit-with-null (sub-decision A) — Task 5; emit leak guard — Task 6. All five spec components covered.
- **Type consistency:** `CompletionResult(text, usage)` and `Usage(provider, model, input_tokens, output_tokens, timestamp)` are referenced identically across Tasks 1-6; `_usage` is the dict form (`asdict(result.usage)`) everywhere it appears; `USAGE_FIELD_ORDER` defined in Task 5 and imported by its test.
- **No placeholders:** every code step shows complete code; every run step shows the exact command and expected outcome.
