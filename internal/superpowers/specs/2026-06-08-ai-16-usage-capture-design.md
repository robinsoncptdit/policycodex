# AI-16: Usage capture in the inventory audit sidecar

Date: 2026-06-08
Ticket: AI-16 (S, 5 pts; deps AI-07, AI-10)
Status: design approved 2026-06-08

## Goal

Record provider name, model identifier, input token count, output token count,
and call timestamp for every per-policy inventory extraction, alongside the
existing confidence values in `policies/<slug>.audit.yaml`. This is the data
foundation for v0.2 spend ceilings (P2.11).

## Scope

Per-policy inventory pass only. The retention-bundle extraction
(`retention_extract.extract_retention_bundle`) is also a metered AI call, but it
writes `data.yaml`, not an audit sidecar, so it has no home for usage data in
v0.1. It stays unmetered until v0.2 gives it one. The provider contract still
changes uniformly, so the retention call adapts mechanically but discards usage.

## Contract shape

`LLMProvider.complete()` returns a richer type instead of a bare `str`. All five
usage fields are knowable inside `complete()` (provider name and model are
provider state, token counts are on the SDK response, timestamp is call time),
so the provider assembles the whole record and callers never compute usage.

Rejected alternatives: a parallel `complete_with_usage()` method (grows the ABC
to two methods, easy to call the wrong one) and last-call state on the provider
(stateful, not reentrancy-safe, decouples the usage read from the call).

## Components

### 1. New types (`ai/provider.py`)

```python
@dataclass(frozen=True)
class Usage:
    provider: str        # "claude"
    model: str           # "claude-opus-4-8"
    input_tokens: int
    output_tokens: int
    timestamp: str       # ISO 8601 UTC, stamped at call time

@dataclass(frozen=True)
class CompletionResult:
    text: str
    usage: Usage
```

`LLMProvider.complete()` return annotation changes `str` -> `CompletionResult`;
docstring updated.

### 2. ClaudeProvider (`ai/claude_provider.py`)

Add a `PROVIDER_NAME = "claude"` constant. After the SDK call, build:

- `provider` from `PROVIDER_NAME`
- `model` from `self.model`
- `input_tokens` / `output_tokens` from `response.usage.input_tokens` /
  `response.usage.output_tokens`
- `timestamp` from `datetime.now(timezone.utc).isoformat()`

Return `CompletionResult(text="".join(parts), usage=Usage(...))`.

### 3. Call-site threading

Both production callers adapt to the new return type:

- `inventory_extract.extract_policy_metadata`: `result = provider.complete(...)`;
  parse `result.text`; attach `metadata["_usage"] = asdict(result.usage)` before
  returning. This mirrors the existing `_source_file` private-key convention.
  `inventory.py` is unchanged; it already emits whatever dict it receives.
- `retention_extract.extract_retention_bundle`: use `result.text` only; ignore
  `result.usage` per scope.

### 4. Audit schema (`ai/audit.py`)

Add a top-level `usage:` block after `confidence:`, read from
`extraction.get("_usage")`:

```yaml
title: ...
source_file: ...
confidence: { ... }
usage:
  provider: claude
  model: claude-opus-4-8
  input_tokens: 4123
  output_tokens: 512
  timestamp: 2026-06-08T18:03:00+00:00
```

The `usage:` block always renders. When `_usage` is absent, the five sub-keys
emit as `null`, matching how `confidence:` already always renders its canonical
keys with null so audit diffs stay stable across runs.

### 5. Markdown leak guard (`ai/emit.py`)

Add `_usage` to `_PRIVATE_FIELDS`. Today that set is a whitelist holding only
`_source_file`, so without this one-line addition the attached `_usage` key
would leak into the human-readable policy markdown front matter.

## Data flow

```
ClaudeProvider.complete(prompt, max_tokens)
  -> CompletionResult(text, usage=Usage(provider, model, in, out, ts))
     |
     v
extract_policy_metadata(provider, text, taxonomy)
  parse result.text -> metadata dict
  metadata["_usage"] = asdict(result.usage)
     |
     v
inventory.run_inventory_pass
  metadata["_source_file"] = name        (existing)
  emit.to_markdown(metadata)             -> policies/<slug>.md   (_usage stripped)
  audit.to_audit_yaml(metadata)          -> policies/<slug>.audit.yaml (usage block)
```

## Error handling

Usage is assembled from the SDK response before parsing. If
`parse_inventory_response` raises `InventoryExtractionError`, the orchestrator
already skips that file and writes no audit, so the unparsed-extraction path is
unchanged. No new failure modes: a failed extraction produces no usage record
because it produces no sidecar.

## Testing

- `test_provider.py`: fakes return `CompletionResult`; signature test asserts the
  new return type.
- `test_claude_provider.py`: mocked SDK response gains `.usage`; assert
  `result.text` plus all five `result.usage` fields.
- `test_inventory_extract.py`: fake returns `CompletionResult`; assert `_usage`
  attached with the right values.
- `test_retention_extract.py`: fake returns `CompletionResult`; assert the
  `.text` path is intact and nothing is metered.
- `test_audit.py`: assert the `usage:` block renders, including the absent ->
  null case.
- `test_emit.py`: assert `_usage` is stripped from front matter.

## Blast radius

Source: `ai/provider.py`, `ai/claude_provider.py`, `ai/inventory_extract.py`,
`ai/retention_extract.py`, `ai/audit.py`, `ai/emit.py` (6 files). Tests: the six
listed above. No new files. All mechanical except the two new dataclasses.

## Decisions

- Scope per-policy inventory only; retention stays unmetered for v0.1.
- Richer return type (`CompletionResult`), not a parallel method or provider state.
- `usage:` block always emits; absent fields render null (sub-decision A).
- Provider stamps `timestamp` at call time, not at audit-write time (sub-decision B).
