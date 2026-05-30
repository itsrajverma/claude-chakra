"""Tests for cross-provider fallback streaming (api/fallback.py)."""

import json

import pytest

from api.fallback import _sse_event_type, stream_with_fallback
from api.model_router import ResolvedModel
from providers.exceptions import InvalidRequestError, RateLimitError


def _evt(event_type: str, data: dict | None = None) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data or {})}\n\n"


MSG_START = _evt("message_start", {"type": "message_start"})
PING = _evt("ping")
C_START = _evt("content_block_start", {"index": 0})
C_STOP = _evt("content_block_stop", {"index": 0})
MSG_DELTA = _evt("message_delta", {})
MSG_STOP = _evt("message_stop", {"type": "message_stop"})


def _c_delta(text: str) -> str:
    return _evt("content_block_delta", {"delta": {"text": text}})


class FakeRequest:
    """Minimal stand-in supporting the ``model_copy(update=..., deep=...)`` call."""

    def __init__(self, model: str = "claude-sonnet"):
        self.model = model

    def model_copy(self, *, update=None, deep=False):
        clone = FakeRequest(self.model)
        for key, value in (update or {}).items():
            setattr(clone, key, value)
        return clone


class FakeProvider:
    """Provider whose ``stream_response`` runs a scripted async behavior."""

    def __init__(self, behavior):
        self._behavior = behavior
        self.open_error_modes: list[str] = []

    async def stream_response(
        self,
        request,
        *,
        input_tokens=0,
        request_id=None,
        thinking_enabled=None,
        on_open_error="render",
    ):
        self.open_error_modes.append(on_open_error)
        async for event in self._behavior(request, on_open_error):
            yield event


async def _success(request, on_open_error):
    yield MSG_START
    yield PING
    yield C_START
    yield _c_delta("hi")
    yield C_STOP
    yield MSG_DELTA
    yield MSG_STOP


async def _raise_on_open(request, on_open_error):
    """Mimic a transport: emit message_start, then fail to open the upstream."""
    yield MSG_START
    if on_open_error == "raise":
        raise RateLimitError("all keys exhausted")
    # render mode: the transport renders the error as a text content block
    yield C_START
    yield _c_delta("upstream error")
    yield C_STOP
    yield MSG_DELTA
    yield MSG_STOP


async def _raise_before_any_event(request, on_open_error):
    """Mimic a build/convert failure that raises before yielding anything."""
    if False:
        yield ""
    raise InvalidRequestError("bad request")


def _getter(by_id):
    return lambda provider_id: by_id[provider_id]


def _candidate(provider_id: str, model: str) -> ResolvedModel:
    return ResolvedModel(
        original_model="claude-sonnet",
        provider_id=provider_id,
        provider_model=model,
        provider_model_ref=f"{provider_id}/{model}",
        thinking_enabled=False,
    )


async def _collect(chain, providers) -> list[str]:
    return [
        event
        async for event in stream_with_fallback(
            chain, FakeRequest(), provider_getter=_getter(providers)
        )
    ]


def test_sse_event_type_parsing():
    assert _sse_event_type(MSG_START) == "message_start"
    assert _sse_event_type(C_START) == "content_block_start"
    assert _sse_event_type(_c_delta("x")) == "content_block_delta"
    assert _sse_event_type("data: {}\n\n") == ""
    assert _sse_event_type(": keepalive\n\n") == ""


@pytest.mark.asyncio
async def test_first_candidate_success_skips_fallback():
    a, b = FakeProvider(_success), FakeProvider(_success)
    chain = [_candidate("groq", "m1"), _candidate("cerebras", "m2")]
    out = await _collect(chain, {"groq": a, "cerebras": b})

    assert a.open_error_modes == ["raise"]  # non-final candidate runs in raise mode
    assert b.open_error_modes == []  # never reached
    assert out.count(MSG_START) == 1
    assert any(_sse_event_type(e) == "content_block_delta" for e in out)


@pytest.mark.asyncio
async def test_falls_back_on_open_failure():
    a, b = FakeProvider(_raise_on_open), FakeProvider(_success)
    chain = [_candidate("groq", "m1"), _candidate("cerebras", "m2")]
    out = await _collect(chain, {"groq": a, "cerebras": b})

    assert a.open_error_modes == ["raise"]
    assert b.open_error_modes == ["render"]  # final candidate renders
    # The client sees exactly one message_start (B's); A's was buffered and discarded.
    assert out.count(MSG_START) == 1
    assert any("hi" in e for e in out)
    assert not any("upstream error" in e for e in out)


@pytest.mark.asyncio
async def test_commit_then_passthrough_preserves_order():
    a = FakeProvider(_success)
    chain = [_candidate("groq", "m1")]
    out = await _collect(chain, {"groq": a})

    assert out == [
        MSG_START,
        PING,
        C_START,
        _c_delta("hi"),
        C_STOP,
        MSG_DELTA,
        MSG_STOP,
    ]
    assert a.open_error_modes == ["render"]  # single candidate is final → render


@pytest.mark.asyncio
async def test_final_candidate_error_text_reaches_client():
    a, b = FakeProvider(_raise_on_open), FakeProvider(_raise_on_open)
    chain = [_candidate("groq", "m1"), _candidate("cerebras", "m2")]
    out = await _collect(chain, {"groq": a, "cerebras": b})

    assert b.open_error_modes == ["render"]
    assert any("upstream error" in e for e in out)
    assert out.count(MSG_START) == 1


@pytest.mark.asyncio
async def test_final_candidate_raise_synthesizes_terminal_error():
    a, b = FakeProvider(_raise_on_open), FakeProvider(_raise_before_any_event)
    chain = [_candidate("groq", "m1"), _candidate("cerebras", "m2")]
    out = await _collect(chain, {"groq": a, "cerebras": b})

    joined = "".join(out)
    # A well-formed terminal error stream is synthesized for the client.
    assert "message_start" in joined
    assert "message_stop" in joined


@pytest.mark.asyncio
async def test_all_providers_attempted_in_order():
    a = FakeProvider(_raise_on_open)
    b = FakeProvider(_raise_on_open)
    c = FakeProvider(_success)
    chain = [
        _candidate("groq", "m1"),
        _candidate("cerebras", "m2"),
        _candidate("nvidia_nim", "m3"),
    ]
    out = await _collect(chain, {"groq": a, "cerebras": b, "nvidia_nim": c})

    assert a.open_error_modes == ["raise"]
    assert b.open_error_modes == ["raise"]
    assert c.open_error_modes == ["render"]
    assert any("hi" in e for e in out)
    assert out.count(MSG_START) == 1
