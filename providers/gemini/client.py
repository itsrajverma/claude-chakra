"""Google Gemini provider implementation (OpenAI-compatible Chat Completions).

Gemini's free tier (https://aistudio.google.com/apikey) offers one of the largest
free request-per-day allowances. The proxy talks to Gemini's OpenAI-compatible
surface at ``/v1beta/openai``. Free limits are per key, so pool several in
``GEMINI_API_KEYS``.

Quirk handled here: Gemini's OpenAI-compatible ``/models`` endpoint returns ids
prefixed with ``models/`` (e.g. ``models/gemini-2.5-flash``) while its chat endpoint
expects the bare name (``gemini-2.5-flash``). We strip the prefix in
:meth:`list_model_ids` so a configured ``gemini/<name>`` model both validates at
startup and routes correctly.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from core.anthropic import ReasoningReplayMode, build_base_request_body
from core.anthropic.conversion import OpenAIConversionError
from providers.base import ProviderConfig
from providers.defaults import GEMINI_DEFAULT_BASE
from providers.exceptions import InvalidRequestError
from providers.openai_compat import OpenAIChatTransport


class GeminiProvider(OpenAIChatTransport):
    """Google Gemini via the OpenAI-compatible ``/v1beta/openai`` endpoint."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="GEMINI",
            base_url=config.base_url or GEMINI_DEFAULT_BASE,
            api_key=config.api_key,
        )

    async def list_model_ids(self) -> frozenset[str]:
        """Return advertised model ids with Gemini's ``models/`` prefix stripped."""
        ids = await super().list_model_ids()
        return frozenset(model_id.removeprefix("models/") for model_id in ids)

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        thinking_enabled = self._is_thinking_enabled(request, thinking_enabled)
        logger.debug(
            "GEMINI_REQUEST: conversion start model={} msgs={}",
            getattr(request, "model", "?"),
            len(getattr(request, "messages", [])),
        )
        try:
            body = build_base_request_body(
                request,
                reasoning_replay=ReasoningReplayMode.REASONING_CONTENT
                if thinking_enabled
                else ReasoningReplayMode.DISABLED,
            )
        except OpenAIConversionError as exc:
            raise InvalidRequestError(str(exc)) from exc

        logger.debug(
            "GEMINI_REQUEST: conversion done model={} msgs={} tools={}",
            body.get("model"),
            len(body.get("messages", [])),
            len(body.get("tools", [])),
        )
        return body
