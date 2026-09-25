"""Central Gemini chat configuration. Call sites never hard-code the model."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
DEFAULT_GEMINI_FALLBACK_MODEL = "gemini-3.1-flash-lite"
DEFAULT_TOOL_NAMES = ("google_search", "google_maps")


@dataclass(frozen=True)
class GeminiRuntimeConfig:
    api_key: str
    base_url: str
    model: str
    fallback_model: str
    timeout_seconds: float
    fallback_to_qwen: bool
    chat_enabled: bool
    tools_enabled: bool
    voice_enabled: bool
    max_retries: int = 1

    @property
    def model_cascade(self) -> list[str]:
        models = [self.model.strip()]
        fallback = self.fallback_model.strip()
        if fallback and fallback not in models:
            models.append(fallback)
        return [item for item in models if item]


def load_gemini_config(settings: Settings | None = None) -> GeminiRuntimeConfig:
    cfg = settings or get_settings()
    return GeminiRuntimeConfig(
        api_key=(cfg.gemini_api_key or "").strip(),
        base_url=(cfg.gemini_api_base_url or "").rstrip("/"),
        model=(cfg.gemini_model or DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL,
        fallback_model=(
            cfg.gemini_fallback_model or DEFAULT_GEMINI_FALLBACK_MODEL
        ).strip()
        or DEFAULT_GEMINI_FALLBACK_MODEL,
        timeout_seconds=float(cfg.gemini_timeout_seconds or 45),
        fallback_to_qwen=bool(cfg.gemini_fallback_to_qwen),
        chat_enabled=bool(cfg.gemini_chat_enabled),
        tools_enabled=bool(cfg.gemini_tools_enabled),
        voice_enabled=bool(cfg.gemini_voice_enabled),
        max_retries=max(0, int(cfg.gemini_max_retries)),
    )
