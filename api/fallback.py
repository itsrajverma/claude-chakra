"""Cross-provider fallback streaming for the Anthropic-compatible API.

Drains an ordered chain of provider/model candidates so a single request can spill
from an exhausted free provider onto the next one without the client ever seeing a
partial or failed response. This is what turns several free tiers into one resilient
pool: when a provider's whole key pool is cooling (or it returns 5xx/auth), the
request transparently advances to the next provider in the chain.

How a candidate is judged:

- Non-final candidates stream with ``on_open_error="raise"``, so an upstream *open*
  failure (429 / 5xx / auth / exhausted pool) raises a ``ProviderError`` we catch to
  advance — instead of the transport rendering that error as assistant text (which is
  indistinguishable from real output at the SSE level).
- We buffer a candidate's pre-content events (``message_start`` / ``ping``) and only
  *commit* — flush the buffer and stream the rest straight through — once the first
  real content event (``content_block_start`` / ``content_block_delta``) arrives. Once
  committed we cannot fall back (bytes are on the wire), exactly like intra-provider
  key rotation.
- The final candidate streams verbatim (``on_open_error="render"``), so the client
  always gets a well-formed terminal response even when every provider fails.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator, Callable, Sequence
from typing import Any, cast

from loguru import logger

from core.anthropic import (
    get_user_facing_error_message,
    iter_provider_stream_error_sse_events,
)
from core.trace import trace_event
from providers.base import BaseProvider
from providers.exceptions import ProviderError

from .model_router import ResolvedModel

# SSE event types that prove real assistant output has started (the commit point).
_CONTENT_COMMIT_EVENTS = frozenset({"content_block_start", "content_block_delta"})


def _sse_event_type(event: str) -> str:
    """Return the ``event:`` type of an Anthropic SSE chunk (``""`` when absent)."""
    if not event.startswith("event:"):
        return ""
    prefix_len = len("event:")
    newline = event.find("\n", prefix_len)
    raw = event[prefix_len:] if newline == -1 else event[prefix_len:newline]
    return raw.strip()


def _trace_fallback(
    failed: ResolvedModel,
    nxt: ResolvedModel,
    exc: ProviderError,
    request_id: str | None,
) -> None:
    logger.warning(
        "Provider fallback: {}/{} -> {}/{} ({} {})",
        failed.provider_id,
        failed.provider_model,
        nxt.provider_id,
        nxt.provider_model,
        getattr(exc, "status_code", "?"),
        type(exc).__name__,
    )
    trace_event(
        stage="routing",
        event="api.fallback.advanced",
        source="api",
        request_id=request_id,
        from_provider=failed.provider_id,
        from_model=failed.provider_model,
        to_provider=nxt.provider_id,
        to_model=nxt.provider_model,
        status_code=getattr(exc, "status_code", None),
        reason=type(exc).__name__,
    )


async def stream_with_fallback(
    chain: Sequence[ResolvedModel],
    base_request: Any,
    *,
    provider_getter: Callable[[str], BaseProvider],
    input_tokens: int = 0,
    request_id: str | None = None,
) -> AsyncIterator[str]:
    """Stream ``base_request`` across ``chain``, advancing on pre-content failures."""
    last_index = len(chain) - 1
    for index, candidate in enumerate(chain):
        is_last = index == last_index
        request = base_request.model_copy(
            update={"model": candidate.provider_model}, deep=True
        )
        provider = provider_getter(candidate.provider_id)
        # stream_response is always an async generator (it has aclose); the abstract
        # base just annotates the looser AsyncIterator.
        generator = cast(
            AsyncGenerator[str],
            provider.stream_response(
                request,
                input_tokens=input_tokens,
                request_id=request_id,
                thinking_enabled=candidate.thinking_enabled,
                on_open_error="render" if is_last else "raise",
            ),
        )
        buffered: list[str] = []
        committed = False
        try:
            async for event in generator:
                if committed:
                    yield event
                    continue
                if _sse_event_type(event) in _CONTENT_COMMIT_EVENTS:
                    committed = True
                    for held in buffered:
                        yield held
                    buffered.clear()
                    yield event
                else:
                    buffered.append(event)
            # Stream ended. If we never hit content it was a clean (possibly empty)
            # completion, or the final candidate's already-rendered error — surface it.
            if not committed:
                for held in buffered:
                    yield held
            return
        except GeneratorExit, KeyboardInterrupt:
            raise
        except ProviderError as exc:
            if committed or is_last:
                # Committed: bytes already sent, cannot retry. Final candidate: its
                # failure is the request's failure. Either way, emit a clean error.
                for event in iter_provider_stream_error_sse_events(
                    request=request,
                    input_tokens=input_tokens,
                    error_message=get_user_facing_error_message(exc),
                    sent_any_event=committed,
                    log_raw_sse_events=False,
                ):
                    yield event
                return
            _trace_fallback(candidate, chain[index + 1], exc, request_id)
        finally:
            await generator.aclose()
