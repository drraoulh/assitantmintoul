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

    app_name: str = "Cameroon AI Tour Guide"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "*"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/cameroon_tour_guide"
    )
    database_enabled: bool = False

    # Primary stack is Hugging Face Inference Providers.
    llm_provider: str = Field(
        default="huggingface",
        validation_alias=AliasChoices("LLM_PROVIDER", "AI_PROVIDER"),
    )
    llm_model: str = Field(
        default="Qwen/Qwen2.5-7B-Instruct",
        validation_alias=AliasChoices("LLM_MODEL", "OLLAMA_MODEL"),
    )
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = 120

    hf_model_id: str = Field(
        default="Qwen/Qwen2.5-7B-Instruct",
        validation_alias=AliasChoices("HF_MODEL_ID", "LLM_MODEL"),
    )
    hf_api_base_url: str = "https://router.huggingface.co/v1"
    hf_timeout_seconds: float = 120
    hf_embedding_model_id: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    hf_vision_model_id: str = "openai/clip-vit-base-patch32"
    hf_whisper_model_id: str = "openai/whisper-small"
    hf_tts_model_id: str = "piper"
    huggingface_hub_token: str = Field(
        default="",
        validation_alias=AliasChoices("HUGGINGFACE_HUB_TOKEN", "HF_TOKEN"),
    )
    hf_token: str = ""

    # Local tourism knowledge base (RAG). Lexical retrieval by default.
    rag_enabled: bool = True
    rag_top_k: int = 6
    rag_data_dir: str = ""

    # Live web enrichment (Wikipedia + DuckDuckGo).
    web_search_enabled: bool = True
    web_search_max_results: int = 4

    # Firebase / Firestore (cloud knowledge base). Local data/ remains the seed.
    firebase_enabled: bool = False
    firebase_project_id: str = ""
    firebase_credentials_file: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
