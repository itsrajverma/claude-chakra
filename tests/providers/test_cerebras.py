"""Tests for the Cerebras provider (OpenAI-compatible, free tier)."""

from unittest.mock import MagicMock

import pytest

from providers.base import ProviderConfig
from providers.cerebras import CEREBRAS_DEFAULT_BASE, CerebrasProvider


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockRequest:
    def __init__(self, **kwargs):
        self.model = "qwen-3-coder-480b"
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
def cerebras_config():
    return ProviderConfig(
        api_key="test_cerebras_key",
        base_url=CEREBRAS_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
        enable_thinking=True,
    )


def test_default_base_url():
    assert CEREBRAS_DEFAULT_BASE == "https://api.cerebras.ai/v1"


def test_init(cerebras_config):
    provider = CerebrasProvider(cerebras_config)
    assert provider._api_key == "test_cerebras_key"
    assert provider._base_url == "https://api.cerebras.ai/v1"


def test_pools_multiple_free_keys():
    """Two+ free keys (e.g. one per account) round-robin through one KeyPool."""
    config = ProviderConfig(
        api_key="key_account_1",
        api_keys=("key_account_1", "key_account_2"),
        base_url=CEREBRAS_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
    )
    provider = CerebrasProvider(config)
    assert provider._key_pool.size == 2


def test_build_request_body_basic(cerebras_config):
    provider = CerebrasProvider(cerebras_config)
    body = provider._build_request_body(MockRequest())

    assert body["model"] == "qwen-3-coder-480b"
    assert body["messages"][0]["role"] == "system"


def test_build_request_body_request_disable_blocks_thinking(cerebras_config):
    provider = CerebrasProvider(cerebras_config)
    req = MockRequest()
    req.thinking.enabled = False
    body = provider._build_request_body(req)

    assert "extra_body" not in body or "thinking" not in body.get("extra_body", {})
