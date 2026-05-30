"""Tests for ModelRouter.resolve_fallback_chain."""

from api.model_router import ModelRouter
from config.settings import Settings


def _router(
    *, model: str = "groq/llama-3.3-70b-versatile", model_fallbacks: str = ""
) -> ModelRouter:
    return ModelRouter(
        Settings.model_construct(model=model, model_fallbacks=model_fallbacks)
    )


def test_chain_is_single_when_no_fallbacks():
    chain = _router(model_fallbacks="").resolve_fallback_chain("claude-sonnet-4")
    assert len(chain) == 1
    assert chain[0].provider_id == "groq"
    assert chain[0].provider_model == "llama-3.3-70b-versatile"


def test_chain_appends_fallbacks_in_order():
    router = _router(
        model_fallbacks="cerebras/qwen-3-coder-480b,nvidia_nim/z-ai/glm4.7"
    )
    chain = router.resolve_fallback_chain("claude-sonnet-4")
    assert [c.provider_id for c in chain] == ["groq", "cerebras", "nvidia_nim"]
    assert chain[1].provider_model == "qwen-3-coder-480b"
    assert chain[2].provider_model == "z-ai/glm4.7"


def test_chain_dedupes_primary_and_repeated_fallbacks():
    router = _router(
        model="groq/llama-3.3-70b-versatile",
        model_fallbacks=(
            "groq/llama-3.3-70b-versatile,cerebras/qwen,cerebras/qwen,zai/glm-5.1"
        ),
    )
    chain = router.resolve_fallback_chain("claude-opus-4")
    refs = [(c.provider_id, c.provider_model) for c in chain]
    assert refs == [
        ("groq", "llama-3.3-70b-versatile"),
        ("cerebras", "qwen"),
        ("zai", "glm-5.1"),
    ]
