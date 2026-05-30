"""OpenAIChatTransport ``on_open_error`` contract (used by cross-provider fallback).

When the upstream stream fails to open, ``on_open_error="raise"`` must re-raise a
ProviderError (so the fallback layer can advance), while the default ``"render"``
must emit an Anthropic error SSE (so a single-provider client sees the failure).
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from providers.base import ProviderConfig
from providers.exceptions import ProviderError, RateLimitError
from providers.fireworks import FIREWORKS_BASE_URL, FireworksProvider


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockRequest:
    def __init__(self):
        self.model = "accounts/fireworks/models/glm-5p1"
        self.messages = [MockMessage("user", "Hello")]
        self.max_tokens = 100
        self.temperature = 0.5
        self.top_p = 0.9
        self.system = None
        self.stop_sequences = None
        self.tools = []
        self.extra_body = {}
        self.thinking = None


@pytest.fixture(autouse=True)
def _no_rate_limit():
    @asynccontextmanager
    async def _slot():
        yield

    with patch("providers.openai_compat.GlobalRateLimiter") as mock:
        instance = mock.get_scoped_instance.return_value
        instance.concurrency_slot.side_effect = _slot
        instance.wait_if_blocked = AsyncMock()
        yield instance


@pytest.fixture
def provider():
    return FireworksProvider(
        ProviderConfig(
            api_key="k", base_url=FIREWORKS_BASE_URL, rate_limit=10, rate_window=60
        )
    )


@pytest.mark.asyncio
async def test_raise_mode_reraises_open_failure(provider):
    with (
        patch.object(
            provider,
            "_create_stream",
            new=AsyncMock(side_effect=RateLimitError("all keys exhausted")),
        ),
        pytest.raises(ProviderError),
    ):
        async for _ in provider.stream_response(MockRequest(), on_open_error="raise"):
            pass


@pytest.mark.asyncio
async def test_render_mode_emits_error_sse_without_raising(provider):
    with patch.object(
        provider,
        "_create_stream",
        new=AsyncMock(side_effect=RateLimitError("all keys exhausted")),
    ):
        events = [
            event
            async for event in provider.stream_response(
                MockRequest(), on_open_error="render"
            )
        ]
    joined = "".join(events)
    assert "message_start" in joined
    assert "message_stop" in joined
