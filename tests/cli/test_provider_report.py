"""Tests for the ``chakra-providers`` free-tier discovery report."""

from unittest.mock import MagicMock

from cli.provider_report import (
    EXAMPLE_MODELS,
    build_provider_report,
    render_provider_report,
)
from config.provider_catalog import FREE_TIER_PROVIDER_IDS


def _settings(configured: dict[str, tuple[str, ...]]) -> MagicMock:
    """Return a Settings stub whose ``api_keys_for`` reflects ``configured``."""
    settings = MagicMock()
    settings.api_keys_for.side_effect = lambda provider_id: configured.get(
        provider_id, ()
    )
    return settings


def test_every_free_provider_has_an_example_model():
    """Contract: the report can always suggest a model for a free provider."""
    missing = sorted(FREE_TIER_PROVIDER_IDS - set(EXAMPLE_MODELS))
    assert missing == [], f"free providers missing EXAMPLE_MODELS: {missing}"


def test_no_keys_means_empty_chain_and_available_hints():
    report = build_provider_report(_settings({}))

    assert report.suggested_fallback_chain == ""
    assert report.configured_free == ()
    # Cloud free providers with a key URL surface as "available" to enable.
    available_ids = {s.provider_id for s in report.available_free}
    assert "groq" in available_ids
    assert "github" in available_ids
    # Local runtimes are always "configured" (static credential), never available.
    assert "ollama" not in available_ids


def test_configured_free_providers_build_chain_in_catalog_order():
    report = build_provider_report(
        _settings(
            {
                "github": ("ghp_1",),
                "groq": ("gk_1",),
                "gemini": ("g_1", "g_2"),
            }
        )
    )

    configured_ids = [s.provider_id for s in report.configured_free]
    # PROVIDER_CATALOG order is nvidia_nim, groq, ..., gemini, ..., github.
    assert configured_ids == ["groq", "gemini", "github"]
    assert report.suggested_fallback_chain == (
        f"{EXAMPLE_MODELS['groq']},{EXAMPLE_MODELS['gemini']},{EXAMPLE_MODELS['github']}"
    )

    gemini = next(s for s in report.statuses if s.provider_id == "gemini")
    assert gemini.configured is True
    assert gemini.key_count == 2


def test_render_includes_ready_chain_and_key_counts():
    report = build_provider_report(
        _settings({"groq": ("gk_1",), "gemini": ("g_1", "g_2")})
    )
    text = render_provider_report(report)

    assert "MODEL_FALLBACKS=" in text
    assert EXAMPLE_MODELS["groq"] in text
    assert "2 keys" in text  # gemini pool size surfaced
    assert "FREE TIERS" in text


def test_render_when_nothing_configured_nudges_setup():
    text = render_provider_report(build_provider_report(_settings({})))
    assert "No free providers configured yet" in text
    assert "MODEL_FALLBACKS=" not in text


def test_providers_entrypoint_prints_report(monkeypatch, capsys):
    """The `chakra-providers` entrypoint renders without touching the network/FS."""
    import cli.entrypoints as entrypoints

    monkeypatch.setattr(entrypoints, "_migrate_legacy_env_if_missing", lambda: None)
    monkeypatch.setattr(
        entrypoints, "get_settings", lambda: _settings({"groq": ("gsk_1",)})
    )

    entrypoints.providers()

    out = capsys.readouterr().out
    assert "provider readiness" in out
    assert "MODEL_FALLBACKS=" in out
