"""Tests for the Chutes provider (OpenAI-compatible, free tier)."""

from unittest.mock import MagicMock

import pytest

from providers.base import ProviderConfig
from providers.chutes import CHUTES_DEFAULT_BASE, ChutesProvider


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockRequest:
    def __init__(self, **kwargs):
        self.model = "deepseek-ai/DeepSeek-V3-0324"
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
def chutes_config():
    return ProviderConfig(
        api_key="cpk_test_key",
        base_url=CHUTES_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
        enable_thinking=True,
    )


def test_default_base_url():
    assert CHUTES_DEFAULT_BASE == "https://llm.chutes.ai/v1"


def test_init(chutes_config):
    provider = ChutesProvider(chutes_config)
    assert provider._api_key == "cpk_test_key"
    assert provider._base_url == "https://llm.chutes.ai/v1"


def test_pools_multiple_free_keys():
    config = ProviderConfig(
        api_key="cpk_account_1",
        api_keys=("cpk_account_1", "cpk_account_2"),
        base_url=CHUTES_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
    )
    provider = ChutesProvider(config)
    assert provider._key_pool.size == 2


def test_build_request_body_basic(chutes_config):
    provider = ChutesProvider(chutes_config)
    body = provider._build_request_body(MockRequest())
    assert body["model"] == "deepseek-ai/DeepSeek-V3-0324"
    assert body["messages"][0]["role"] == "system"
