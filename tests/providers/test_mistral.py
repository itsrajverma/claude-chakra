"""Tests for the Mistral provider (OpenAI-compatible, free tier)."""

from unittest.mock import MagicMock

import pytest

from providers.base import ProviderConfig
from providers.mistral import MISTRAL_DEFAULT_BASE, MistralProvider


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockRequest:
    def __init__(self, **kwargs):
        self.model = "mistral-small-latest"
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
def mistral_config():
    return ProviderConfig(
        api_key="test_mistral_key",
        base_url=MISTRAL_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
        enable_thinking=True,
    )


def test_default_base_url():
    assert MISTRAL_DEFAULT_BASE == "https://api.mistral.ai/v1"


def test_init(mistral_config):
    provider = MistralProvider(mistral_config)
    assert provider._api_key == "test_mistral_key"
    assert provider._base_url == "https://api.mistral.ai/v1"


def test_pools_multiple_free_keys():
    config = ProviderConfig(
        api_key="key_account_1",
        api_keys=("key_account_1", "key_account_2"),
        base_url=MISTRAL_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
    )
    provider = MistralProvider(config)
    assert provider._key_pool.size == 2


def test_build_request_body_basic(mistral_config):
    provider = MistralProvider(mistral_config)
    body = provider._build_request_body(MockRequest())
    assert body["model"] == "mistral-small-latest"
    assert body["messages"][0]["role"] == "system"
