"""Per-provider API key pool with round-robin selection and per-key cooldown.

Multiple keys can be configured for a single provider (e.g. several NVIDIA NIM
keys, each with its own 40 req/min quota). The pool picks the next non-cooling
key for every outbound call; when an upstream returns 429 the caller marks the
current key as cooling for ``cooldown_seconds`` and rotates to the next live
key. This lets an in-flight stream attempt rotate before the upstream returns
any tokens, so the client never sees a partial response.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from loguru import logger


class KeyPool:
    """Hold N API keys, hand out the next live one, cool keys that hit 429."""

    def __init__(
        self,
        keys: Sequence[str],
        *,
        scope: str,
        default_cooldown_seconds: float = 60.0,
    ) -> None:
        cleaned = tuple(key for key in keys if key)
        if not cleaned:
            raise ValueError(f"KeyPool {scope!r} requires at least one non-empty key")
        self._keys = cleaned
        self._scope = scope
        self._cooldown_until: dict[str, float] = {}
        self._cursor = 0
        self._default_cooldown = default_cooldown_seconds
        if len(cleaned) > 1:
            logger.info(
                "KeyPool initialized scope={} keys={} (multi-key rotation enabled)",
                scope,
                len(cleaned),
            )

    @property
    def size(self) -> int:
        return len(self._keys)

    @property
    def scope(self) -> str:
        return self._scope

    def keys(self) -> tuple[str, ...]:
        return self._keys

    def next_live_key(self) -> str:
        """Return the next key not in cooldown; fall back to soonest-expiring key."""
        now = time.monotonic()
        n = len(self._keys)
        for _ in range(n):
            key = self._keys[self._cursor % n]
            self._cursor += 1
            if self._cooldown_until.get(key, 0.0) <= now:
                return key
        soonest = min(
            self._keys, key=lambda k: self._cooldown_until.get(k, 0.0)
        )
        logger.warning(
            "KeyPool scope={} all {} keys cooling; reusing soonest-free key",
            self._scope,
            n,
        )
        return soonest

    def report_rate_limit(
        self, key: str, *, cooldown_seconds: float | None = None
    ) -> None:
        """Mark ``key`` as cooling for ``cooldown_seconds`` (default 60s)."""
        cooldown = (
            self._default_cooldown
            if cooldown_seconds is None
            else max(0.0, cooldown_seconds)
        )
        self._cooldown_until[key] = time.monotonic() + cooldown
        if len(self._keys) > 1:
            logger.warning(
                "KeyPool scope={} key cooling {:.1f}s; rotating to next key",
                self._scope,
                cooldown,
            )

    def all_cooling(self) -> bool:
        """Return whether every key is currently in cooldown."""
        now = time.monotonic()
        return all(
            self._cooldown_until.get(key, 0.0) > now for key in self._keys
        )

    def remaining_live_keys(self) -> int:
        now = time.monotonic()
        return sum(
            1 for key in self._keys if self._cooldown_until.get(key, 0.0) <= now
        )
