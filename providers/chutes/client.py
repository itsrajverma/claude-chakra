"""Chutes provider implementation (OpenAI-compatible Chat Completions).

Chutes (https://llm.chutes.ai/v1) is a serverless inference platform on the Bittensor
network with an OpenAI-compatible endpoint and a free prototyping tier. It serves open
models such as DeepSeek V3/R1, Llama, Qwen, and GLM. Free limits are per key, so pool
several in ``CHUTES_API_KEYS``. Keys look like ``cpk_…``.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from core.anthropic import ReasoningReplayMode, build_base_request_body
from core.anthropic.conversion import OpenAIConversionError
from providers.base import ProviderConfig
from providers.defaults import CHUTES_DEFAULT_BASE
from providers.exceptions import InvalidRequestError
from providers.openai_compat import OpenAIChatTransport


class ChutesProvider(OpenAIChatTransport):
    """Chutes via the OpenAI-compatible ``/v1/chat/completions`` endpoint."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="CHUTES",
            base_url=config.base_url or CHUTES_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        thinking_enabled = self._is_thinking_enabled(request, thinking_enabled)
        logger.debug(
            "CHUTES_REQUEST: conversion start model={} msgs={}",
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
            "CHUTES_REQUEST: conversion done model={} msgs={} tools={}",
            body.get("model"),
            len(body.get("messages", [])),
            len(body.get("tools", [])),
        )
        return body
