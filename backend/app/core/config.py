from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Smartmboa Tour"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "*"

    # Supabase Postgres: use the "URI" connection string and swap the driver for
    # postgresql+asyncpg://. Keep DATABASE_ENABLED=false to stay in memory.
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/cameroon_tour_guide"
    )
    database_enabled: bool = False
    database_echo: bool = False
    # Turns kept as LLM context; the full thread stays readable in the database.
    conversation_context_messages: int = 16

    # Primary stack is Hugging Face Inference Providers.
    llm_provider: str = Field(
        default="huggingface",
        validation_alias=AliasChoices("LLM_PROVIDER", "AI_PROVIDER"),
    )
    llm_model: str = Field(
        default="Qwen/Qwen3.5-9B",
        validation_alias=AliasChoices("LLM_MODEL", "OLLAMA_MODEL"),
    )
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = 90

    hf_model_id: str = Field(
        default="Qwen/Qwen3.5-9B:fastest",
        validation_alias=AliasChoices("HF_MODEL_ID", "LLM_MODEL"),
    )
    hf_api_base_url: str = "https://router.huggingface.co/v1"
    hf_timeout_seconds: float = 60

    # Generation budgets. Shorter answers = faster TTFT + TTS.
    llm_max_tokens: int = Field(
        default=320,
        validation_alias=AliasChoices("LLM_MAX_TOKENS"),
    )
    llm_voice_max_tokens: int = Field(
        default=140,
        validation_alias=AliasChoices("LLM_VOICE_MAX_TOKENS"),
    )
    # How many prior turns to send to the LLM (lower = faster TTFT).
    # Phase 1: trimmed from 8/4 → 6/3 while keeping short conversation continuity.
    llm_history_messages: int = Field(
        default=6,
        validation_alias=AliasChoices("LLM_HISTORY_MESSAGES"),
    )
    llm_voice_history_messages: int = Field(
        default=3,
        validation_alias=AliasChoices("LLM_VOICE_HISTORY_MESSAGES"),
    )
    hf_embedding_model_id: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    hf_vision_model_id: str = "openai/clip-vit-base-patch32"
    hf_whisper_model_id: str = "openai/whisper-large-v3-turbo"
    hf_tts_model_id: str = "s2.1-pro-free"
    huggingface_hub_token: str = Field(
        default="",
        validation_alias=AliasChoices("HUGGINGFACE_HUB_TOKEN", "HF_TOKEN"),
    )
    hf_token: str = ""
    hf_inference_base_url: str = Field(
        default="https://router.huggingface.co/hf-inference",
        validation_alias=AliasChoices(
            "HF_INFERENCE_BASE_URL",
            "HUGGINGFACE_INFERENCE_BASE_URL",
        ),
    )
    hf_speech_timeout_seconds: float = Field(
        default=120,
        validation_alias=AliasChoices("HF_SPEECH_TIMEOUT_SECONDS"),
    )

    # Local tourism knowledge base (RAG). Lexical retrieval by default.
    rag_enabled: bool = True
    rag_top_k: int = 4
    rag_data_dir: str = ""
    # Optional HF remote embeddings merged with lexical (no local model).
    rag_vector_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("RAG_VECTOR_ENABLED"),
    )
    rag_cache_ttl_seconds: float = Field(
        default=300.0,
        validation_alias=AliasChoices("RAG_CACHE_TTL_SECONDS"),
    )
    redis_url: str = Field(
        default="",
        validation_alias=AliasChoices("REDIS_URL"),
    )
    # Live web enrichment: providers run in parallel; hard budget aborts the leg.
    web_search_enabled: bool = True
    web_search_max_results: int = 3
    # Phase 1: tighter budgets — KB already covers most tourism questions.
    web_search_timeout_seconds: float = Field(
        default=2.5,
        validation_alias=AliasChoices("WEB_SEARCH_TIMEOUT_SECONDS"),
    )
    voice_web_search_timeout_seconds: float = Field(
        default=1.5,
        validation_alias=AliasChoices("VOICE_WEB_SEARCH_TIMEOUT_SECONDS"),
    )

    # Speech STT: huggingface (cloud Whisper) | whisper (local) | placeholder
    speech_provider: str = Field(
        default="huggingface",
        validation_alias=AliasChoices("SPEECH_PROVIDER"),
    )
    whisper_device: str = Field(
        default="cpu",
        validation_alias=AliasChoices("WHISPER_DEVICE"),
    )
    whisper_compute_type: str = Field(
        default="int8",
        validation_alias=AliasChoices("WHISPER_COMPUTE_TYPE"),
    )

    # TTS: fish (Fish Audio S2.1) | none (mobile falls back to expo-speech)
    tts_provider: str = Field(
        default="fish",
        validation_alias=AliasChoices("TTS_PROVIDER"),
    )
    fish_audio_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("FISH_AUDIO_API_KEY", "FISH_API_KEY"),
    )
    fish_audio_base_url: str = Field(
        default="https://api.fish.audio",
        validation_alias=AliasChoices("FISH_AUDIO_BASE_URL"),
    )
    fish_audio_model: str = Field(
        default="s2.1-pro-free",
        validation_alias=AliasChoices("FISH_AUDIO_MODEL"),
    )
    fish_audio_reference_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FISH_AUDIO_REFERENCE_ID",
            "FISH_AUDIO_VOICE_ID",
        ),
    )
    fish_audio_timeout_seconds: float = Field(
        default=90,
        validation_alias=AliasChoices("FISH_AUDIO_TIMEOUT_SECONDS"),
    )

    # Vision: gemini (Google Gemini multimodal) | placeholder
    vision_provider: str = Field(
        default="gemini",
        validation_alias=AliasChoices("VISION_PROVIDER"),
    )
    gemini_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    gemini_api_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        validation_alias=AliasChoices("GEMINI_API_BASE_URL"),
    )
    gemini_vision_model: str = Field(
        default="gemini-3.6-flash",
        validation_alias=AliasChoices("GEMINI_VISION_MODEL", "GEMINI_MODEL"),
    )
    gemini_timeout_seconds: float = Field(
        default=90,
        validation_alias=AliasChoices("GEMINI_TIMEOUT_SECONDS"),
    )

    # Phase 2.1 Agent 1 — Intent & Router (progressive). Default OFF so the
    # Phase-1 voice path is unchanged. When observe=true, classify_intent runs
    # alongside route_query for metrics only (no routing behavior change).
    intent_router_observe: bool = Field(
        default=False,
        validation_alias=AliasChoices("INTENT_ROUTER_OBSERVE"),
    )
    # Phase 2.2 Agent 2 — Knowledge & Retrieval (progressive). Default OFF.
    knowledge_agent_observe: bool = Field(
        default=False,
        validation_alias=AliasChoices("KNOWLEDGE_AGENT_OBSERVE"),
    )
    knowledge_agent_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("KNOWLEDGE_AGENT_ENABLED"),
    )

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
