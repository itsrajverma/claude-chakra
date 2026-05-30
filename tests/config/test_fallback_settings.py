"""Tests for MODEL_FALLBACKS settings parsing and validation."""

import pytest
from pydantic import ValidationError

from config.settings import Settings


def test_fallback_refs_empty_by_default(monkeypatch):
    monkeypatch.delenv("MODEL_FALLBACKS", raising=False)
    assert Settings().fallback_model_refs() == ()


def test_fallback_refs_comma_separated(monkeypatch):
    monkeypatch.setenv(
        "MODEL_FALLBACKS",
        "groq/llama-3.3-70b-versatile, cerebras/qwen-3-coder-480b",
    )
    assert Settings().fallback_model_refs() == (
        "groq/llama-3.3-70b-versatile",
        "cerebras/qwen-3-coder-480b",
    )


def test_fallback_refs_json_list_with_dedupe(monkeypatch):
    monkeypatch.setenv("MODEL_FALLBACKS", '["groq/m1","groq/m1","cerebras/m2"]')
    assert Settings().fallback_model_refs() == ("groq/m1", "cerebras/m2")


def test_fallbacks_appear_in_configured_chat_model_refs(monkeypatch):
    monkeypatch.setenv("MODEL", "groq/llama-3.3-70b-versatile")
    monkeypatch.setenv("MODEL_FALLBACKS", "cerebras/qwen-3-coder-480b")
    refs = {ref.model_ref for ref in Settings().configured_chat_model_refs()}
    assert "cerebras/qwen-3-coder-480b" in refs


def test_invalid_provider_rejected(monkeypatch):
    monkeypatch.setenv("MODEL_FALLBACKS", "notaprovider/model")
    with pytest.raises(ValidationError):
        Settings()


def test_missing_provider_prefix_rejected(monkeypatch):
    monkeypatch.setenv("MODEL_FALLBACKS", "justamodelname")
    with pytest.raises(ValidationError):
        Settings()
