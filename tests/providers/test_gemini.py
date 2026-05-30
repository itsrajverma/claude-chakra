"""Tests for the Google Gemini provider (OpenAI-compatible, free tier)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.base import ProviderConfig
from providers.gemini import GEMINI_DEFAULT_BASE, GeminiProvider
from providers.openai_compat import OpenAIChatTransport


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockRequest:
    def __init__(self, **kwargs):
        self.model = "gemini-2.5-flash"
        self.messages = [MockMessage("user", "Hello")]
        self.max_tokens = 100
        self.temperature = 0.5
        self.top_p = 0.9
        self.system = "System prompt"
        self.stop_sequences = None
        self.tools = []
        self.extra_body = {}
        self.thinking = MagicMock()
        self.thinking.enabled = True
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def gemini_config():
    return ProviderConfig(
        api_key="test_gemini_key",
        base_url=GEMINI_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
        enable_thinking=True,
    )


def test_default_base_url():
    assert (
        GEMINI_DEFAULT_BASE == "https://generativelanguage.googleapis.com/v1beta/openai"
    )


def test_init(gemini_config):
    provider = GeminiProvider(gemini_config)
    assert provider._api_key == "test_gemini_key"
    assert provider._base_url == GEMINI_DEFAULT_BASE


def test_build_request_body_basic(gemini_config):
    provider = GeminiProvider(gemini_config)
    body = provider._build_request_body(MockRequest())
    assert body["model"] == "gemini-2.5-flash"
    assert body["messages"][0]["role"] == "system"


@pytest.mark.asyncio
async def test_list_model_ids_strips_models_prefix(gemini_config):
    """Gemini's /models returns ``models/<name>`` ids; we must strip the prefix
    so a configured ``gemini/<name>`` model validates and routes correctly."""
    raw = frozenset({"models/gemini-2.5-flash", "models/gemini-2.5-pro", "bare-id"})
    with patch.object(
        OpenAIChatTransport, "list_model_ids", new=AsyncMock(return_value=raw)
    ):
        provider = GeminiProvider(gemini_config)
        ids = await provider.list_model_ids()

    assert ids == frozenset({"gemini-2.5-flash", "gemini-2.5-pro", "bare-id"})
    assert not any(model_id.startswith("models/") for model_id in ids)
