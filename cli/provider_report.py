"""Free-tier provider discovery report for the ``chakra-providers`` command.

Pure, network-free helpers that inspect :class:`~config.settings.Settings` and the
provider catalog to answer "which free providers are ready, and what ``MODEL`` /
``MODEL_FALLBACKS`` should I paste to use them?". Kept import-light (no provider
adapters) so it stays cheap to call from the CLI and easy to unit test.
"""

from __future__ import annotations

from dataclasses import dataclass

from config.provider_catalog import (
    FREE_TIER_PROVIDER_IDS,
    PROVIDER_CATALOG,
    ProviderDescriptor,
)
from config.settings import Settings

# Presentation-only example slugs (the README provider matrix is the canonical list).
# Every free provider id must appear here; a contract test enforces that.
EXAMPLE_MODELS: dict[str, str] = {
    "nvidia_nim": "nvidia_nim/z-ai/glm4.7",
    "groq": "groq/llama-3.3-70b-versatile",
    "cerebras": "cerebras/qwen-3-coder-480b",
    "gemini": "gemini/gemini-2.5-flash",
    "mistral": "mistral/mistral-small-latest",
    "sambanova": "sambanova/Meta-Llama-3.3-70B-Instruct",
    "github": "github/openai/gpt-4o-mini",
    "huggingface": "huggingface/meta-llama/Llama-3.3-70B-Instruct",
    "chutes": "chutes/deepseek-ai/DeepSeek-V3-0324",
    "open_router": "open_router/deepseek/deepseek-chat:free",
    "opencode": "opencode/big-pickle",
}


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    """One row of the provider report."""

    provider_id: str
    free_tier: bool
    is_local: bool
    configured: bool
    key_count: int
    example_model: str | None
    credential_url: str | None


@dataclass(frozen=True, slots=True)
class ProviderReport:
    """Snapshot of provider readiness plus a ready-to-paste fallback chain."""

    statuses: tuple[ProviderStatus, ...]
    suggested_fallback_chain: str

    @property
    def configured_free(self) -> tuple[ProviderStatus, ...]:
        return tuple(s for s in self.statuses if s.free_tier and s.configured)

    @property
    def available_free(self) -> tuple[ProviderStatus, ...]:
        """Free providers with a key URL that are not yet configured."""
        return tuple(
            s
            for s in self.statuses
            if s.free_tier and not s.configured and not s.is_local
        )


def _is_local(descriptor: ProviderDescriptor) -> bool:
    return (
        "local" in descriptor.capabilities or descriptor.static_credential is not None
    )


def _configured_key_count(descriptor: ProviderDescriptor, settings: Settings) -> int:
    if descriptor.static_credential is not None:
        return 1
    return len(settings.api_keys_for(descriptor.provider_id))


def build_provider_report(settings: Settings) -> ProviderReport:
    """Inspect ``settings`` against the catalog and return a readiness snapshot."""
    statuses: list[ProviderStatus] = []
    chain: list[str] = []
    for provider_id, descriptor in PROVIDER_CATALOG.items():
        key_count = _configured_key_count(descriptor, settings)
        free_tier = provider_id in FREE_TIER_PROVIDER_IDS
        example = EXAMPLE_MODELS.get(provider_id)
        status = ProviderStatus(
            provider_id=provider_id,
            free_tier=free_tier,
            is_local=_is_local(descriptor),
            configured=key_count > 0,
            key_count=key_count,
            example_model=example,
            credential_url=descriptor.credential_url,
        )
        statuses.append(status)
        if free_tier and status.configured and example:
            chain.append(example)

    return ProviderReport(
        statuses=tuple(statuses),
        suggested_fallback_chain=",".join(chain),
    )


def _status_symbol(status: ProviderStatus) -> str:
    if status.configured:
        keys = f" ({status.key_count} key{'s' if status.key_count != 1 else ''})"
        return f"[ready]{keys}"
    if status.is_local:
        return "[local]"
    return "[ no key ]"


def render_provider_report(report: ProviderReport) -> str:
    """Render a human-friendly, copy-pasteable provider report for the terminal."""
    lines: list[str] = []
    lines.append("Claude Chakra - provider readiness")
    lines.append("=" * 38)

    free = [s for s in report.statuses if s.free_tier]
    ready_free = report.configured_free
    lines.append("")
    lines.append(
        f"Free providers: {len(ready_free)}/{len(free)} configured "
        f"({len(report.available_free)} more available with a free key)."
    )
    lines.append("")

    lines.append("FREE TIERS")
    lines.append("-" * 38)
    for status in free:
        symbol = _status_symbol(status)
        line = f"  {status.provider_id:<13} {symbol:<14} {status.example_model or ''}"
        lines.append(line.rstrip())
        if not status.configured and status.credential_url:
            lines.append(f"  {'':<13} get a key: {status.credential_url}")

    local = [s for s in report.statuses if s.is_local and not s.free_tier]
    if local:
        lines.append("")
        lines.append("LOCAL (no key, runs on your machine)")
        lines.append("-" * 38)
        lines.extend(
            f"  {status.provider_id:<13} {status.example_model or ''}".rstrip()
            for status in local
        )

    paid = [s for s in report.statuses if not s.free_tier and not s.is_local]
    if paid:
        lines.append("")
        lines.append("PAID / CREDITS")
        lines.append("-" * 38)
        for status in paid:
            symbol = _status_symbol(status)
            lines.append(f"  {status.provider_id:<13} {symbol}")

    lines.append("")
    lines.append("=" * 38)
    if report.suggested_fallback_chain:
        lines.append("Paste this into your config to chain every configured free tier")
        lines.append("(spills to the next provider the moment one runs out of quota):")
        lines.append("")
        first = report.suggested_fallback_chain.split(",", 1)[0]
        lines.append(f"  MODEL={first}")
        lines.append(f"  MODEL_FALLBACKS={report.suggested_fallback_chain}")
    else:
        lines.append("No free providers configured yet. Add a key for one of the")
        lines.append("FREE TIERS above (Groq / Cerebras / Gemini need no credit card),")
        lines.append("then re-run `chakra-providers` for a ready-made fallback chain.")
    lines.append("")
    return "\n".join(lines)
