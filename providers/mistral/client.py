"""Mistral provider implementation (OpenAI-compatible Chat Completions).

Mistral's free "Experiment" tier (https://console.mistral.ai/api-keys) grants
access to all Mistral models at a low RPM with a generous monthly token budget.
Free limits are per key, so pool several in ``MISTRAL_API_KEYS``.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from core.anthropic import ReasoningReplayMode, build_base_request_body
from core.anthropic.conversion import OpenAIConversionError
from providers.base import ProviderConfig
from providers.defaults import MISTRAL_DEFAULT_BASE
from providers.exceptions import InvalidRequestError
from providers.openai_compat import OpenAIChatTransport


class MistralProvider(OpenAIChatTransport):
    """Mistral via the OpenAI-compatible ``/v1/chat/completions`` endpoint."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="MISTRAL",
            base_url=config.base_url or MISTRAL_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        thinking_enabled = self._is_thinking_enabled(request, thinking_enabled)
        logger.debug(
            "MISTRAL_REQUEST: conversion start model={} msgs={}",
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
            "MISTRAL_REQUEST: conversion done model={} msgs={} tools={}",
            body.get("model"),
            len(body.get("messages", [])),
            len(body.get("tools", [])),
        )
        return body
