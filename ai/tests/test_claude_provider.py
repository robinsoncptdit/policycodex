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
    provider = ClaudeProvider(client=MagicMock())
    assert provider.model == "claude-sonnet-4-6"
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
