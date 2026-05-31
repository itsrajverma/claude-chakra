"""Hugging Face provider implementation (OpenAI-compatible Chat Completions).

The Hugging Face Inference Providers router (https://router.huggingface.co/v1) is a
drop-in OpenAI-compatible surface that fans requests out across partner backends
(Cerebras, Together, Nebius, Novita, …). New accounts get monthly inference credits
for free; HF PRO adds more. Free limits are per token, so pool several in
``HUGGINGFACE_API_KEYS``. Models use their canonical repo ids, e.g.
``meta-llama/Llama-3.3-70B-Instruct``.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from core.anthropic import ReasoningReplayMode, build_base_request_body
from core.anthropic.conversion import OpenAIConversionError
from providers.base import ProviderConfig
from providers.defaults import HUGGINGFACE_DEFAULT_BASE
from providers.exceptions import InvalidRequestError
from providers.openai_compat import OpenAIChatTransport


class HuggingFaceProvider(OpenAIChatTransport):
    """Hugging Face router via the OpenAI-compatible ``/v1/chat/completions`` endpoint."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="HUGGINGFACE",
            base_url=config.base_url or HUGGINGFACE_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        thinking_enabled = self._is_thinking_enabled(request, thinking_enabled)
        logger.debug(
            "HUGGINGFACE_REQUEST: conversion start model={} msgs={}",
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
            "HUGGINGFACE_REQUEST: conversion done model={} msgs={} tools={}",
            body.get("model"),
            len(body.get("messages", [])),
            len(body.get("tools", [])),
        )
        return body
