"""Tests for the GitHub Models provider (OpenAI-compatible, free tier).

Covers the catalog-based ``list_model_ids`` override: the ``/inference`` chat base
has no OpenAI ``/models`` list, so the provider queries ``/catalog/models`` (a bare
JSON array of ``{id, ...}``) instead.
"""

from unittest.mock import MagicMock, patch

import pytest

from providers.base import ProviderConfig
from providers.exceptions import ModelListResponseError, ServiceUnavailableError
from providers.github import GITHUB_MODELS_DEFAULT_BASE, GitHubModelsProvider


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockRequest:
    def __init__(self, **kwargs):
        self.model = "openai/gpt-4o-mini"
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


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Minimal async-context HTTP client returning a fixed catalog payload."""

    def __init__(self, payload, **_kwargs):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def get(self, _url, headers=None):
        return _FakeResponse(self._payload)


@pytest.fixture
def github_config():
    return ProviderConfig(
        api_key="ghp_test_token",
        base_url=GITHUB_MODELS_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
        enable_thinking=True,
    )


def test_default_base_url():
    assert GITHUB_MODELS_DEFAULT_BASE == "https://models.github.ai/inference"


def test_init(github_config):
    provider = GitHubModelsProvider(github_config)
    assert provider._api_key == "ghp_test_token"
    assert provider._base_url == "https://models.github.ai/inference"


def test_pools_multiple_free_keys():
    config = ProviderConfig(
        api_key="ghp_token_1",
        api_keys=("ghp_token_1", "ghp_token_2"),
        base_url=GITHUB_MODELS_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
    )
    provider = GitHubModelsProvider(config)
    assert provider._key_pool.size == 2


def test_build_request_body_keeps_publisher_prefixed_model(github_config):
    provider = GitHubModelsProvider(github_config)
    body = provider._build_request_body(MockRequest())
    assert body["model"] == "openai/gpt-4o-mini"
    assert body["messages"][0]["role"] == "system"


@pytest.mark.asyncio
async def test_list_model_ids_reads_catalog_array(github_config):
    """Catalog returns a bare array of ``{id}`` objects; we surface those ids."""
    payload = [
        {"id": "openai/gpt-4o-mini", "publisher": "OpenAI"},
        {"id": "meta/Llama-3.3-70B-Instruct", "publisher": "Meta"},
    ]

    def _factory(**kwargs):
        return _FakeAsyncClient(payload, **kwargs)

    with patch("providers.github.client.httpx.AsyncClient", _factory):
        provider = GitHubModelsProvider(github_config)
        ids = await provider.list_model_ids()

    assert ids == frozenset({"openai/gpt-4o-mini", "meta/Llama-3.3-70B-Instruct"})


@pytest.mark.asyncio
async def test_list_model_ids_rejects_non_array_catalog(github_config):
    def _factory(**kwargs):
        return _FakeAsyncClient({"data": []}, **kwargs)

    with patch("providers.github.client.httpx.AsyncClient", _factory):
        provider = GitHubModelsProvider(github_config)
        with pytest.raises(ModelListResponseError):
            await provider.list_model_ids()


@pytest.mark.asyncio
async def test_list_model_ids_maps_http_errors(github_config):
    import httpx

    class _BoomClient(_FakeAsyncClient):
        async def get(self, _url, headers=None):
            raise httpx.ConnectError("boom")

    def _factory(**kwargs):
        return _BoomClient(None, **kwargs)

    with patch("providers.github.client.httpx.AsyncClient", _factory):
        provider = GitHubModelsProvider(github_config)
        with pytest.raises(ServiceUnavailableError):
            await provider.list_model_ids()
