"""SambaNova provider implementation (OpenAI-compatible Chat Completions).

SambaNova Cloud (https://cloud.sambanova.ai/apis) offers a persistent free tier
with very fast inference for Llama 3.3 70B, Llama 3.1 (up to 405B), Qwen, and
DeepSeek models. Free limits are per key, so pool several in ``SAMBANOVA_API_KEYS``.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from core.anthropic import ReasoningReplayMode, build_base_request_body
from core.anthropic.conversion import OpenAIConversionError
from providers.base import ProviderConfig
from providers.defaults import SAMBANOVA_DEFAULT_BASE
from providers.exceptions import InvalidRequestError
from providers.openai_compat import OpenAIChatTransport


class SambaNovaProvider(OpenAIChatTransport):
    """SambaNova Cloud via the OpenAI-compatible ``/v1/chat/completions`` endpoint."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="SAMBANOVA",
            base_url=config.base_url or SAMBANOVA_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        thinking_enabled = self._is_thinking_enabled(request, thinking_enabled)
        logger.debug(
            "SAMBANOVA_REQUEST: conversion start model={} msgs={}",
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
            "SAMBANOVA_REQUEST: conversion done model={} msgs={} tools={}",
            body.get("model"),
            len(body.get("messages", [])),
            len(body.get("tools", [])),
        )
        return body
