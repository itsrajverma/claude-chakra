"""GitHub Models provider implementation (OpenAI-compatible Chat Completions).

GitHub Models (https://models.github.ai) gives every GitHub account free,
rate-limited access to a large catalog (OpenAI GPT, Llama, DeepSeek, Phi, Mistral,
Grok, …) via an OpenAI-compatible inference surface at ``/inference``. Authenticate
with a Personal Access Token carrying the ``models:read`` scope; pool several in
``GITHUB_API_KEYS`` to widen the per-token rate limits.

Quirk handled here: the OpenAI-compatible base does not expose an OpenAI ``/models``
list. The catalog lives at the sibling ``/catalog/models`` path and returns a *bare*
JSON array of objects whose publisher-prefixed ``id`` (e.g. ``openai/gpt-4.1``) is what
the chat endpoint expects. :meth:`list_model_ids` queries it directly so a configured
``github/<publisher>/<name>`` model validates at startup and routes correctly.
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from core.anthropic import ReasoningReplayMode, build_base_request_body
from core.anthropic.conversion import OpenAIConversionError
from providers.base import ProviderConfig
from providers.defaults import GITHUB_MODELS_DEFAULT_BASE
from providers.exceptions import InvalidRequestError, ServiceUnavailableError
from providers.model_listing import extract_github_catalog_model_ids
from providers.openai_compat import OpenAIChatTransport

# Catalog lives outside the ``/inference`` chat surface; pin the documented API version.
GITHUB_MODELS_CATALOG_URL = "https://models.github.ai/catalog/models"
GITHUB_MODELS_API_VERSION = "2026-03-10"


class GitHubModelsProvider(OpenAIChatTransport):
    """GitHub Models via the OpenAI-compatible ``/inference`` endpoint."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="GITHUB",
            base_url=config.base_url or GITHUB_MODELS_DEFAULT_BASE,
            api_key=config.api_key,
        )

    async def list_model_ids(self) -> frozenset[str]:
        """Return catalog model ids (the ``/inference`` base has no OpenAI ``/models``)."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_MODELS_API_VERSION,
        }
        try:
            async with httpx.AsyncClient(
                proxy=self._proxy or None, timeout=self._http_timeout
            ) as client:
                response = await client.get(GITHUB_MODELS_CATALOG_URL, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError(
                f"GitHub Models catalog query failed: {exc}"
            ) from exc
        return extract_github_catalog_model_ids(
            payload, provider_name=self._provider_name
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        thinking_enabled = self._is_thinking_enabled(request, thinking_enabled)
        logger.debug(
            "GITHUB_REQUEST: conversion start model={} msgs={}",
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
            "GITHUB_REQUEST: conversion done model={} msgs={} tools={}",
            body.get("model"),
            len(body.get("messages", [])),
            len(body.get("tools", [])),
        )
        return body
